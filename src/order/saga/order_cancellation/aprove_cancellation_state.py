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
    def _return_money(client_id: int, order_id: int, amount: float) -> None:
        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="cmd",
            exchange_type="topic",
            routing_key="payment.release",
        ) as publisher:
            publisher.publish({
                "client_id": client_id,
                "order_id": order_id,
                "total_amount": amount,
            })

    @staticmethod
    def _send_cancel(order_id: int) -> None:
        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="cmd",
            exchange_type="topic",
            routing_key="warehouse.cancel",
        ) as publisher:
            publisher.publish({
                "order_id": order_id
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

        # TODO: Hau ebentu bezala jarri!
        ApproveCancellation._return_money(
            client_id=self._context.client_id,
            order_id=self._context.order_id,
            amount=self._context.total_amount,
        )
        ApproveCancellation._send_cancel(self._context.order_id)

        return self
