from .models import Order
from chassis.sql import delete_element_by_id
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

async def create_order(
    db: AsyncSession, 
    client_id: int, 
    piece_amount: int,
    city: str,
    street: str,
    zip: str,
) -> Order:
    db_order = Order(
        piece_amount=piece_amount,
        client_id=client_id,
        city=city,
        street=street,
        zip=zip,
    )
    db.add(db_order)
    await db.flush()
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
    db_order = await get_order(db, order_id)
    if db_order is not None:
        db_order.status = status
        await db.commit()
        await db.refresh(db_order)
    return db_order