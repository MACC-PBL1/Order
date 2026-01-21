from ...global_vars import RABBITMQ_CONFIG
from ...sql import (
    Order,
    update_order_status,
)
from ..base_state import State
from chassis.messaging import RabbitMQPublisher
from chassis.sql import SessionLocal

class ApproveCancellation(State):
    @staticmethod
    def _notify_cancellation_approved(order_id: int, client_id: int, total_amount: float) -> None:
        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="cancellation-approved",
            exchange_type="fanout",
        ) as publisher:
            publisher.publish({
                "order_id": order_id,
                "client_id": client_id,
                "total_amount": total_amount
            })

    async def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self

        assert self._context.total_amount is not None, "'total_amount' should be known at this point."        
        async with SessionLocal() as db:
            await update_order_status(
                db=db,
                order_id=self._context.order_id,
                status=Order.STATUS_CANCELLED,
            )

        ApproveCancellation._notify_cancellation_approved(
            order_id=self._context.order_id,
            client_id=self._context.client_id,
            total_amount=self._context.total_amount,
        )

        return self
