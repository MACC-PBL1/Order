from ..messaging import (
    PUBLIC_KEY,
    PUBLISHING_QUEUES,
    RABBITMQ_CONFIG,
)
from ..saga import (
    StateContext,
    Saga,
)
from ..sql import (
    create_order,
    Message,
    Order,
    OrderCreationRequest,
    OrderCreationResponse,
    update_order_status,
)
from chassis.routers import raise_and_log_error
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

logger = logging.getLogger(__name__)

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
    "/create",
    response_model=OrderCreationResponse,
    summary="Create a new order",
    status_code=status.HTTP_201_CREATED,
)
async def create_order_endpoint(
    order_data: OrderCreationRequest,
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger)),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"POST '/order/create' called (piece_amount={order_data.piece_count})")

    client_id = int(token_data["sub"])

    logger.debug(
        "Create order request received",
        extra={"client_id": client_id}
    )

    db_order = await create_order(
        db=db, 
        client_id=client_id, 
        piece_amount=order_data.piece_count,
        city=order_data.city,
        street=order_data.street,
        zip=order_data.zip
    )

    ctx = StateContext(
        order_id=db_order.id,
        client_id=db_order.client_id,
        total_amount=db_order.piece_amount * PIECE_PRICE["pieza_1"],
        zipcode=db_order.zip
    )
    saga = Saga(ctx)

    if saga.process() == False:
        await update_order_status(
            db=db,
            order_id=db_order.id,
            status=Order.STATUS_CANCELLED,
        )
        logger.error(
            f"Failed to process payment for (client_id={db_order.client_id}, order_id={db_order.id})"
        )
        raise_and_log_error(
            logger=logger, 
            status_code=status.HTTP_400_BAD_REQUEST, 
            message=f"Saga failed on state {saga.get_state()}"
        )

    # Ask for pieces
    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["piece_request"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish({
            "order_id": db_order.id,
            "amount": db_order.piece_amount,
        })

    # Create delivery
    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["delivery_create"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish({
            "order_id": db_order.id,
            "city": db_order.city,
            "street": db_order.street,
            "zip": db_order.zip,
            "client_id": db_order.client_id,
        })

    return OrderCreationResponse(
        id=db_order.id,
        piece_amount=db_order.piece_amount,
        status=db_order.status,
        client_id=db_order.client_id,
    )