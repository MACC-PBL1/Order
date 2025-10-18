# -*- coding: utf-8 -*-
"""FastAPI router definitions for the Order microservice."""

import logging
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.sql import crud, schemas
from .router_utils import raise_and_log_error
from app.messaging.rabbitmq import publish_message


logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Router definition
# ------------------------------------------------------------------------------
router = APIRouter(
    prefix="/order",
    tags=["Order"]
)

# ------------------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------------------
@router.get(
    "/health",
    summary="Health check endpoint",
    response_model=schemas.Message,
)
async def health_check():
    """Simple endpoint to verify service availability."""
    logger.debug("GET '/order/health' called.")
    return {"detail": "Order service is running"}


# ------------------------------------------------------------------------------
# Create Order
# ------------------------------------------------------------------------------



@router.post(
    "/",
    response_model=schemas.Order,
    summary="Create a new order",
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    order_schema: schemas.OrderPost,
    db: AsyncSession = Depends(get_db),
):
    """Create a new order and publish an event."""
    logger.debug("POST '/order' called with %s", order_schema)
    try:
        db_order = await crud.create_order_from_schema(db, order_schema)

        # --- 🔔 Publicar evento a RabbitMQ ---
        await publish_message(
            "order.created",  # 🧭 routing key
               {                 # 📦 message body
                   "order_id": db_order.id,
                   "client_id": db_order.client_id,
                   "number_of_pieces": db_order.number_of_pieces,
                    "description": db_order.description,
                    "status": db_order.status,
               }
            )

        logger.info(f"Published 'order.created' event for order {db_order.id}")
        return db_order

    except Exception as exc:
        raise_and_log_error(logger, status.HTTP_409_CONFLICT, f"Error creating order: {exc}")


# @router.post(
#     "/",
#     response_model=schemas.Order,
#     summary="Create a new order",
#     status_code=status.HTTP_201_CREATED,
# )
# async def create_order(
#     order_schema: schemas.OrderPost,
#     db: AsyncSession = Depends(get_db),
# ):
#     """Create a new order and its pieces."""
#     logger.debug("POST '/order' called with %s", order_schema)
#     try:
#         db_order = await crud.create_order_from_schema(db, order_schema)
#         return db_order
#     except Exception as exc:  # TODO: add more specific exception handling
#         raise_and_log_error(logger, status.HTTP_409_CONFLICT, f"Error creating order: {exc}")


# ------------------------------------------------------------------------------
# Get All Orders
# ------------------------------------------------------------------------------
@router.get(
    "/",
    response_model=List[schemas.Order],
    summary="Retrieve all orders",
)
async def get_order_list(
    db: AsyncSession = Depends(get_db),
):
    """Return a list of all orders with their pieces."""
    logger.debug("GET '/order' called.")
    return await crud.get_order_list(db)

# ------------------------------------------------------------------------------
# Get Single Order
# ------------------------------------------------------------------------------
@router.get(
    "/{order_id}",
    response_model=schemas.Order,
    summary="Retrieve a single order by ID",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": schemas.Message,
            "description": "Order not found",
        },
    },
)
async def get_single_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single order by ID."""
    logger.debug("GET '/order/%s' called.", order_id)
    order = await crud.get_order(db, order_id)
    if not order:
        raise_and_log_error(logger, status.HTTP_404_NOT_FOUND, f"Order {order_id} not found")
    return order

# ------------------------------------------------------------------------------
# Delete Order
# ------------------------------------------------------------------------------
@router.delete(
    "/{order_id}",
    response_model=schemas.Order,
    summary="Delete an order by ID",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": schemas.Message,
            "description": "Order not found",
        },
    },
)
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete an existing order and all its pieces."""
    logger.debug("DELETE '/order/%s' called.", order_id)
    order = await crud.get_order(db, order_id)
    if not order:
        raise_and_log_error(logger, status.HTTP_404_NOT_FOUND, f"Order {order_id} not found")

    deleted = await crud.delete_order(db, order_id)
    return deleted

# ------------------------------------------------------------------------------
# Update Order Status
# ------------------------------------------------------------------------------
@router.put(
    "/{order_id}/status",
    response_model=schemas.Order,
    summary="Update order status",
)
async def update_order_status(
    order_id: int,
    status_body: schemas.OrderUpdateStatus,
    db: AsyncSession = Depends(get_db),
):
    """Update the status of a given order."""
    logger.debug("PUT '/order/%s/status' called with %s", order_id, status_body)
    order = await crud.update_order_status(db, order_id, status_body.status)
    if not order:
        raise_and_log_error(logger, status.HTTP_404_NOT_FOUND, f"Order {order_id} not found")
    return order