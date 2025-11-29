from ..messaging import (
    PUBLIC_KEY,
    PUBLISHING_QUEUES,
    RABBITMQ_CONFIG,
)
from ..sql import (
    create_order,
    Message,
    OrderSchema,
)
from chassis.messaging import RabbitMQPublisher
from chassis.security import create_jwt_verifier
from chassis.sql import get_db
from fastapi import (
    APIRouter, 
    Depends, 
    status
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
import logging 


PIECE_PRICE: Dict[str, float] = {
    "pieza_1": 4.75
}

logger = logging.getLogger("order")

Router = APIRouter(prefix="/order", tags=["Order"])

# ----------------------------------------------------------------------
# Health check
# ----------------------------------------------------------------------
@Router.get(
    "/health",
    summary="Health check endpoint",
    response_model=Message,
)
async def health_check():
    logger.debug("GET '/order/health' called.")  
    return {"detail": "Order service is running"}


@Router.get(
    "/health/auth",
    summary="Health check endpoint (JWT protected)",
)
async def health_check_auth(
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger))
):
    logger.debug("GET '/order/health/auth' called.")

    user_id = token_data.get("sub")
    user_email = token_data.get("email")
    user_role = token_data.get("role")

    logger.info(f"Valid JWT → user_id={user_id}, email={user_email}, role={user_role}")

    logger.info(
        "Authenticated health check",
        extra={"client_id": user_id}
    )


    return {
        "detail": f"Order service is running. Authenticated as {user_email} (id={user_id}, role={user_role})"
    }


# ----------------------------------------------------------------------
# Create Order
# ----------------------------------------------------------------------
@Router.post(
    "/create_order",
    response_model=OrderSchema,
    summary="Create a new order",
    status_code=status.HTTP_201_CREATED,
)
async def create_order_endpoint(
    piece_amount: int,
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger)),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"POST '/order/create_order' called (piece_amount={piece_amount})")

    client_id = int(token_data["sub"])

    logger.debug(
        "Create order request received",
        extra={"client_id": client_id}
    )

    # Create order inside DB
    db_order = await create_order(db, client_id, piece_amount)

    # --------------------
    # QUEUE: Payment Request
    # --------------------
    payment_data = {
        "client_id": client_id,
        "order_id": db_order.id,
        "amount": piece_amount * PIECE_PRICE["pieza_1"]
    }

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["payment_request"],
        rabbitmq_config=RABBITMQ_CONFIG,
    ) as publisher:
        publisher.publish(payment_data)

    logger.info(
        "Payment request sent",
        extra={"client_id": client_id, "order_id": db_order.id}
    )


    # --------------------
    # EVENT: order.created (Topic)
    # --------------------
    with RabbitMQPublisher(
        queue="",
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="order.created",
        rabbitmq_config=RABBITMQ_CONFIG,
    ) as publisher:
        publisher.publish({
            "service_name": "order",
            "event_type": "order.created",
            "message": f"Order created → {payment_data}",
        })

    logger.info(
        f"Event published: order.created (order_id={db_order.id})",
        extra={"client_id": db_order.client_id, "order_id": db_order.id}
    )


    return OrderSchema(
        id=db_order.id,
        piece_amount=db_order.piece_amount,
        status=db_order.status,
        client_id=db_order.client_id,
    )