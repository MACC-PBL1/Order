from ..messaging import (
    PUBLIC_KEY,
    PUBLISHING_QUEUES,
    RABBITMQ_CONFIG,
)
from ..saga import (
    StateContext,
    Saga,
    SAGA_HISTORY,
)
from ..sql import (
    create_order,
    Message,
    Order,
    OrderCreationRequest,
    OrderCreationResponse,
    update_order_status,
)
from chassis.routers import (
    get_system_metrics,
    raise_and_log_error,
)
from chassis.messaging import (
    is_rabbitmq_healthy,
    RabbitMQPublisher
)
from chassis.security import create_jwt_verifier
from chassis.sql import get_db
from fastapi import (
    APIRouter, 
    Depends, 
    status,
    Query
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional
import logging 
import socket

PIECE_PRICE: Dict[str, float] = {
    "pieza_1": 4.75
}

logger = logging.getLogger(__name__)

Router = APIRouter(prefix="/order", tags=["Order"])

# ------------------------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------------------------
@Router.get(
    "/health",
    summary="Health check endpoint",
    response_model=Message,
)
async def health_check():
    if not is_rabbitmq_healthy(RABBITMQ_CONFIG):
        raise_and_log_error(
            logger=logger,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="[LOG:REST] - RabbitMQ not reachable"
        )

    container_id = socket.gethostname()
    logger.debug(f"[LOG:REST] - GET '/health' served by {container_id}")
    return {
        "detail": f"OK - Served by {container_id}",
        "system_metrics": get_system_metrics()
    }

@Router.get(
    "/health/auth",
    summary="Health check endpoint (JWT protected)",
    response_model=Message
)
async def health_check_auth(
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger))
):
    logger.debug("[LOG:REST] - GET '/health/auth' endpoint called.")

    user_id = token_data.get("sub")
    user_role = token_data.get("role")

    logger.info(f"[LOG:REST] - Valid JWT: user_id={user_id}, role={user_role}")

    return {
        "detail": f"Auth service is running. Authenticated as (id={user_id}, role={user_role})",
        "system_metrics": get_system_metrics()
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
    client_id = int(token_data["sub"])

    logger.debug(
        "[LOG:REST] - POST '/order/create' called: "
        f"client_id={client_id}, piece_amount={order_data.piece_count})"
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
            f"[LOG:REST] - Failed to process payment: " 
            f"client_id={db_order.client_id}, order_id={db_order.id}"
        )
        raise_and_log_error(
            logger=logger, 
            status_code=status.HTTP_400_BAD_REQUEST, 
            message=f"[LOG:REST] - Saga failed"
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

    logger.info(f"[LOG:REST] - Order created: order_id={db_order.id}")

    return OrderCreationResponse(
        id=db_order.id,
        piece_amount=db_order.piece_amount,
        status=db_order.status,
        client_id=db_order.client_id,
    )
    
# ------------------------------------------------------------------------------------
# Saga history
# ------------------------------------------------------------------------------------
@Router.get(
    "/saga/history",
    summary="Get saga state history",
    response_model=Dict[int, List[str]],
)
async def get_saga_history(
    order_id: Optional[int] = Query(None, description="Order id"),
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger)),
):
    logger.debug(f"[LOG:REST] - GET '/saga/history' called. order_id={order_id}")
    
    user_role = token_data.get("role")
    if user_role != "admin":
        raise_and_log_error(
            logger, 
            status.HTTP_401_UNAUTHORIZED, 
            f"Access denied: user_role={user_role} (admin required)",
        )

    if order_id is not None:
        if order_id in SAGA_HISTORY:
            return {order_id: SAGA_HISTORY[order_id]}
        else:
            raise_and_log_error(
                logger=logger,
                status_code=status.HTTP_404_NOT_FOUND,
                message=f"Saga history not found for order {order_id}"
            )
            
    return SAGA_HISTORY