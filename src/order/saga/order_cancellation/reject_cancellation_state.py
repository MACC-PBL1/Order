from ...sql import (
    update_order_status,
    Order
)
from ..base_state import State
from chassis.sql import SessionLocal

class RejectCancellationState(State):
    """Terminal state - order cancellation rejected"""
    async def on_event(self, event: State) -> State:
        async with SessionLocal() as db:
            await update_order_status(db, self._context.order_id, Order.STATUS_APPROVED)
        return self

