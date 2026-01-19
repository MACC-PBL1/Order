from ...sql import (
    get_order,
    Order,
    update_order_status,
)
from ..base_state import State
from .check_warehouse_space_state import CheckWarehouseSpaceState
from .reject_cancellation_state import RejectCancellationState
from chassis.sql import SessionLocal
from typing import Optional

class CheckOrderExistsState(State):
    async def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self

        async with SessionLocal() as db:
            order: Optional[Order] = await get_order(db, self._context.order_id)

        if order is not None and order.status == Order.STATUS_APPROVED:
            self._context.total_amount = order.total_amount
            await update_order_status(db, order.id, Order.STATUS_CANCELLING)
            return CheckWarehouseSpaceState(self._context)
        return RejectCancellationState(self._context)