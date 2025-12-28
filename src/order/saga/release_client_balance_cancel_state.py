from .base_state import State
from .cancel_warehouse_state import CancelWarehouseState
from .order_cancel_failed_state import OrderCancelFailedState
from .order_cancelled_state import OrderCancelledState
from chassis.messaging import RabbitMQPublisher
from ..global_vars import RABBITMQ_CONFIG
import logging

logger = logging.getLogger(__name__)

class ReleaseClientBalanceCancelState(State):
    """
    Release balance as part of ORDER CANCELLATION saga.
    NOT a terminal state.
    """

    def execute(self):
        logger.info(
            "[CMD:PAYMENT_RELEASE:CANCEL] - Releasing balance: order_id=%s",
            self._context.order_id,
        )

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
    
    def on_event(self, event: dict) -> State:
        if event["type"] == "payment.released":
            logger.info(
                "[SAGA] - Payment released, continuing cancellation: order_id=%s",
                self._context.order_id,
            )
            return OrderCancelledState(self._context)

        if event["type"] == "payment.failed":
            logger.error(
                "[SAGA] - Payment release failed: order_id=%s",
                self._context.order_id,
            )
            return OrderCancelFailedState(self._context)

        return self
