from .base_state import State
from chassis.messaging import RabbitMQPublisher
from ..global_vars import RABBITMQ_CONFIG
import logging

logger = logging.getLogger(__name__)


class OrderCancelFailedState(State):
    """
    Terminal state for ORDER CANCELLATION saga when something goes wrong.
    """

    def execute(self):
        logger.error(
            "[SAGA:ORDER:CANCEL:FAILED] - order_id=%s",
            self._context.order_id,
        )

        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="evt",
            exchange_type="topic",
            routing_key="order.cancel_failed",
        ) as publisher:
            publisher.publish({
                "order_id": self._context.order_id,
                "reason": "cancellation_failed",
            })

    def on_event(self, event: dict) -> State:
        return self
