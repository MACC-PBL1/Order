from ..global_vars import (
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
    OrderResponse,
    update_order_status,
    get_order_for_update,
    get_orders,
    get_orders_by_client,
    get_order_by_id,
    acquire_cancel_lock,
    get_order_pieces,
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
    Query, 
    HTTPException,
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional
import logging 
import socket

from ..saga.registry import create_saga

PIECE_PRICE: Dict[str, float] = {
    "A": 4.75,
    "B": 6.20,
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
         f"client_id={client_id})"
    )

    db_order = await create_order(
        db=db, 
        client_id=client_id, 
        city=order_data.city,
        street=order_data.street,
        zip=order_data.zip,
        pieces=order_data.pieces,
    )

    total_amount = sum(
        piece.quantity * PIECE_PRICE[piece.piece_type]
        for piece in order_data.pieces
    )

    ctx = StateContext(
        order_id=db_order.id,
        client_id=db_order.client_id,
        total_amount=total_amount,
        zipcode=db_order.zip,
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
    # with RabbitMQPublisher(
    #     queue=PUBLISHING_QUEUES["piece_request"],
    #     rabbitmq_config=RABBITMQ_CONFIG
    # ) as publisher:
    #     publisher.publish({
    #         "order_id": db_order.id,
    #         "amount": db_order.piece_amount,
    #     })
    pieces_payload = [
        {
            "piece_type": piece.piece_type,
            "quantity": piece.quantity,
        }
        for piece in order_data.pieces
        ]

    
    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["order_created"],
        rabbitmq_config=RABBITMQ_CONFIG,
    ) as publisher:
        publisher.publish({
            "order_id": db_order.id,
            "client_id": db_order.client_id,
            "zip": db_order.zip,
            "pieces": pieces_payload,
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
        status=db_order.status,
        client_id=db_order.client_id,
        pieces=pieces_payload,
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


@Router.get(
    "",
    summary="Get all orders",
    response_model=List[OrderResponse],
)
async def get_all_orders(
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger)),
    db: AsyncSession = Depends(get_db),
):
    user_id = int(token_data["sub"])
    user_role = token_data.get("role")

    logger.debug(
        "[LOG:REST] - GET '/order' called "
        f"user_id={user_id}, role={user_role}"
    )

    if user_role == "admin":
        orders = await get_orders(db)
    else:
        orders = await get_orders_by_client(db, user_id)

    response: list[OrderResponse] = []

    for order in orders:
        pieces = await get_order_pieces(db, order.id)

        response.append(
            OrderResponse(
                id=order.id,
                client_id=order.client_id,
                status=order.status,
                city=order.city,
                street=order.street,
                zip=order.zip,
                pieces=[
                    {
                        "piece_type": p.piece_type,
                        "quantity": p.quantity,
                    }
                    for p in pieces
                ],
            )
        )


    logger.info(f"[LOG:REST] - {len(response)} orders returned")

    return response


@Router.get(
    "/{order_id}",
    summary="Get order by id",
    response_model=OrderResponse,
)
async def get_order(
    order_id: int,
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger)),
    db: AsyncSession = Depends(get_db),
):
    user_id = int(token_data["sub"])
    user_role = token_data.get("role")

    logger.debug(
        "[LOG:REST] - GET '/order/%s' called user_id=%s role=%s",
        order_id,
        user_id,
        user_role,
    )

    order = await get_order_by_id(db, order_id)

    if order is None:
        raise_and_log_error(
            logger,
            status.HTTP_404_NOT_FOUND,
            f"Order {order_id} not found",
        )

    if user_role != "admin" and order.client_id != user_id:
        raise_and_log_error(
            logger,
            status.HTTP_403_FORBIDDEN,
            "Not allowed to access this order",
        )

    return order

@Router.post(
    "/{order_id}/cancel",
    summary="Cancel order",
)
async def cancel_order(
    order_id: int,
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger)),
    db: AsyncSession = Depends(get_db),
):
    user_id = int(token_data["sub"])

    locked = await acquire_cancel_lock(db, order_id, user_id)

    if locked is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order cannot be cancelled",
        )

    order_id_value = locked["order_id"]
    client_id = locked["client_id"]
    zip_code = locked["zip"]

    pieces = await get_order_pieces(db, order_id_value)

    total_amount = sum(
        piece.quantity * PIECE_PRICE[piece.piece_type]
        for piece in pieces
    )

    ctx = StateContext(
        order_id=order_id_value,
        client_id=client_id,
        total_amount=total_amount,
        zipcode=zip_code,
    )

    saga = Saga(ctx)
    create_saga(saga)
    saga.process_cancel()

    logger.info(
        "[LOG:REST] - Order cancelling: order_id=%s",
        order_id_value,
    )

    return {
        "status": "cancelling",
        "order_id": order_id_value,
    }
