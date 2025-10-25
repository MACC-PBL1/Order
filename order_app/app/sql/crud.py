# -*- coding: utf-8 -*-
"""CRUD functions that interact with the database for the Order microservice."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from . import models, schemas
from datetime import datetime, timezone
logger = logging.getLogger(__name__)
#from microservice_chassis.errors import raise_and_log_error

# ================================================================================================
# ORDER CRUD OPERATIONS
# ================================================================================================

async def create_order_from_schema(db: AsyncSession, order: schemas.OrderPost, client_id: int) -> models.Order:
    """
    Persist a new order into the database.
    Automatically creates the requested number of pieces.
    """
    logger.info("Creating new order for client_id=%s with %s pieces", client_id, order.number_of_pieces)

    db_order = models.Order(
        client_id=client_id,  
        number_of_pieces=order.number_of_pieces,
        description=order.description,
        status=models.Order.STATUS_CREATED
    )
    db.add(db_order)
    await db.flush()  # Ensure order.id is available before creating pieces

    # Create pieces automatically
    for _ in range(order.number_of_pieces):
        piece = models.Piece(order=db_order, status=models.Piece.STATUS_QUEUED)
        db.add(piece)

    await db.commit()
    await db.refresh(db_order)
    logger.debug("Order %s created successfully with %s pieces", db_order.id, len(db_order.pieces))
    return db_order


# async def add_piece_to_order(db: AsyncSession, order):
#     """Creates piece and adds it to order."""
#     piece = models.Piece()
#     piece.order = order
#     db.add(piece)
#     await db.commit()
#     await db.refresh(order)
#     return order


async def get_order_list(db: AsyncSession):
    """Load all the orders from the database."""
    logger.debug("Fetching all orders from database")
    result = await db.execute(
        select(models.Order).options(selectinload(models.Order.pieces))
    )
    return result.scalars().unique().all()


async def get_order(db: AsyncSession, order_id: int):
    """Load a single order (with pieces) from the database."""
    logger.debug("Fetching order with id=%s", order_id)
    result = await db.execute(
        select(models.Order)
        .options(selectinload(models.Order.pieces))
        .where(models.Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def delete_order(db: AsyncSession, order_id: int):
    """Delete an order and its pieces from the database."""
    logger.info("Deleting order id=%s", order_id)
    order = await db.get(models.Order, order_id)
    if order:
        await db.delete(order)
        await db.commit()
        logger.debug("Order %s deleted successfully", order_id)
    else:
        logger.warning("Order id=%s not found for deletion", order_id)
    return order


async def update_order_status(db: AsyncSession, order_id: int, status: str):
    """Update an order's status in the database."""
    logger.info("Updating order id=%s to status=%s", order_id, status)
    db_order = await db.get(models.Order, order_id)
    if db_order:
        db_order.status = status
        await db.commit()
        await db.refresh(db_order)
        logger.debug("Order %s status updated to %s", db_order.id, db_order.status)
    else:
        logger.warning("Order id=%s not found for update", order_id)
    return db_order



async def update_piece_status(db: AsyncSession, piece_id: int, new_status: str):
    """Update the status (and manufacturing date) of a piece."""
    try:
        result = await db.execute(
            select(models.Piece).where(models.Piece.id == piece_id)
        )
        piece = result.scalar_one_or_none()

        if not piece:
            logger.error(f" Piece {piece_id} not found.")
            raise ValueError(f"Piece {piece_id} not found")

        piece.status = new_status
        piece.manufacturing_date = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(piece)

        logger.info(f" Updated piece {piece_id} to status '{new_status}'.")
        return piece

    except Exception as e:
        logger.error(f"Error updating piece {piece_id} status: {e}", exc_info=True)
        await db.rollback()
        raise