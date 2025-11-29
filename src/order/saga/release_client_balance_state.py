from ..messaging import RABBITMQ_CONFIG
from .base_state import State
from .order_cancelled_state import OrderCancelledState
from chassis.messaging import RabbitMQPublisher

class ReleaseClientBalanceState(State):
    """Compensation state - release reserved balance"""

    def on_event(self, event: State) -> State:
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
                "total_amount": str(self._context.total_amount),
            })

        return OrderCancelledState(self._context)

