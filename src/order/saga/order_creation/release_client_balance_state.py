from ...global_vars import RABBITMQ_CONFIG
from ..base_state import State
from .order_cancelled_state import OrderCancelledState
from chassis.messaging import RabbitMQPublisher
import logging

logger = logging.getLogger(__name__)

class ReleaseClientBalanceState(State):
    """Compensation state - release reserved balance"""

    async def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self
        
        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="cmd",
            exchange_type="topic",
            routing_key="payment.release",
        ) as publisher:
            publisher.publish({
                "client_id": str(self._context.client_id),
                "order_id": str(self._context.order_id),
                "total_amount": str(self._context.total_amount),
            })
            logger.info(
                "[CMD:PAYMENT_RELEASE:SENT] - Sent release command: "
                f"order_id={self._context.order_id}, "
                f"client_id={self._context.client_id}, "
                f"amount={self._context.total_amount}"
            )

        return OrderCancelledState(self._context)

