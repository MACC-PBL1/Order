from .models import Order
from chassis.sql import delete_element_by_id
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import select, update

async def create_order(
    db: AsyncSession, 
    client_id: int, 
    piece_amount: int,
   # piece_type: str,
    city: str,
    street: str,
    zip: str,
) -> Order:
    db_order = Order(
        piece_amount=piece_amount,
     #   piece_type = piece_type,
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

async def get_orders(db) -> List[Order]:
    result = await db.execute(select(Order))
    return result.scalars().all()

async def get_orders_by_client(db, client_id: int) -> List[Order]:
    result = await db.execute(
        select(Order).where(Order.client_id == client_id)
    )
    return result.scalars().all()

async def get_order_by_id(db, order_id: int) -> Optional[Order]:
    result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    return result.scalar_one_or_none()

async def get_order_for_update(
    db: AsyncSession,
    order_id: int,
) -> Optional[Order]:
    """
    EVITAR que dos procesos modifiquen la misma order al mismo tiempo.
    """
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()

async def acquire_cancel_lock(
    db: AsyncSession,
    order_id: int,
    client_id: int,
) -> Optional[dict]:
    result = await db.execute(
        update(Order)
        .where(
            Order.id == order_id,
            Order.client_id == client_id,
            Order.status.in_([
                Order.STATUS_CREATED,
                Order.STATUS_IN_PROGRESS,
            ]),
        )
        .values(status=Order.STATUS_CANCELLING)
        .returning(
            Order.id,
            Order.client_id,
            Order.zip,
            Order.piece_amount,
        )
    )

    row = result.first()
    await db.commit()

    if row is None:
        return None

    return {
        "order_id": row.id,
        "client_id": row.client_id,
        "zip": row.zip,
        "piece_amount": row.piece_amount,
    }
