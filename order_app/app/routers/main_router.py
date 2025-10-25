# -*- coding: utf-8 -*-
"""FastAPI router definitions for the Order microservice."""

import logging
from typing import List
from fastapi import APIRouter, Depends, status, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.sql import crud, schemas
from .router_utils import raise_and_log_error
from microservice_chassis.events import EventPublisher

from app.security.jwt_utils import verify_jwt
import os
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError 

logger = logging.getLogger(__name__)

# Instancia global del publisher (se conecta al iniciar)
event_publisher = EventPublisher(exchange="factory.events")

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
# Health check auth
# ------------------------------------------------------------------------------
@router.get(
    "/health/auth",
    summary="Health check endpoint (JWT protected)",
)
async def health_check(request: Request):
    """Verify service availability and print the client info from the JWT payload."""
    logger.debug("GET '/order/health/auth' called.")

    # Leer el token JWT del header Authorization
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header.split(" ")[1]

    # Verificar el JWT usando la función centralizada
    try:
        payload = verify_jwt(token)

        user_id = payload.get("sub")
        user_email = payload.get("email")
        user_role = payload.get("role")

        logger.info(f" Valid JWT: user_id={user_id}, email={user_email}, role={user_role}")

        return {
            "detail": f"Order service is running. Authenticated as {user_email} (id={user_id}, role={user_role})"
        }

    except Exception as e:
        logger.error(f" JWT verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    

        return {"detail": "Order service is running"}

# ------------------------------------------------------------------------------
# Create Order
# ------------------------------------------------------------------------------

@router.post(
    "/create_order",
    response_model=schemas.Order,
    summary="Create a new order",
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    request: Request,
    order_schema: schemas.OrderPost,
    db: AsyncSession = Depends(get_db),
):
    """Create a new order and publish an event, only if JWT is valid."""
    logger.debug("POST '/order/create_order' called with %s", order_schema)

    # --- Verificación JWT ---
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    
    token = auth_header.split(" ")[1]
    try:
        payload = verify_jwt(token)
        user_id = payload.get("sub")
        user_email = payload.get("email")
        user_role = payload.get("role")
        logger.info(f" Order creation authorized for user {user_email} (id={user_id}, role={user_role})")

    except Exception as e:
        logger.error(f" JWT verification failed during order creation: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    
    # --- Crear orden en DB ---
    try:
        db_order = await crud.create_order_from_schema(
            db=db,
            order=order_schema,
            client_id=user_id,  
        )

        # --- Publicar evento a RabbitMQ usando EventPublisher ---
        event_publisher.publish(
            "machine.request_piece",  # routing key
            {                 # message body
                "order_id": db_order.id,
                "client_id": db_order.client_id,
                "piece_amount": db_order.number_of_pieces,
                "description": db_order.description,
                "status": db_order.status,
                "created_by": user_id,  
            }
        )

        logger.info(f"Published 'machine.request_piece' event for order {db_order.id} by {user_email}")
        return db_order

    except Exception as exc:
        raise_and_log_error(logger, status.HTTP_409_CONFLICT, f"Error creating order: {exc}")



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