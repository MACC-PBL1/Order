from .models import (
    Order, 
    Piece,
)
from .schemas import OrderPieceSchema
from chassis.sql import update_elements_statement_result
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

async def create_order(
    db: AsyncSession, 
    client_id: int, 
    city: str,
    street: str,
    zip: str,
    total_amount: float,
    pieces: list[OrderPieceSchema]
) -> Order:
    db_order = Order(
        client_id=client_id,
        city=city,
        street=street,
        zip=zip,
        status=Order.STATUS_CREATED,
        total_amount=total_amount,
    )
    db.add(db_order)
    await db.flush()
    await db.refresh(db_order)

    for piece in pieces:
        db.add(
            Piece(
                order_id=db_order.id,
                piece_type=piece.type,
                quantity=piece.quantity,
            )
        )
    await db.flush()
    await db.commit()
    await db.refresh(db_order)
    return db_order

async def get_order(
    db: AsyncSession,
    order_id: int,
) -> Optional[Order]:
    return await db.get(Order, order_id)

async def update_order_status(
    db: AsyncSession,
    order_id: int,
    status: str,
) -> Optional[Order]:
    await update_elements_statement_result(
        db=db,
        stmt=(
            update(Order)
                .where(Order.id == order_id)
                .values(status=status)
        )
    )
    return await get_order(db, order_id)