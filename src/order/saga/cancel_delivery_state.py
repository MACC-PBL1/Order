from .base_state import State
from chassis.messaging import RabbitMQPublisher
from ..global_vars import RABBITMQ_CONFIG, PUBLISHING_QUEUES
import logging

logger = logging.getLogger(__name__)


class CancelDeliveryState(State):
    """
    Cancels delivery as part of ORDER CANCELLATION saga.
    """

    def execute(self):
        logger.info(
            "[CMD:DELIVERY:CANCEL] - order_id=%s",
            self._context.order_id,
        )

        with RabbitMQPublisher(
            queue=PUBLISHING_QUEUES["delivery_cancel"],
            rabbitmq_config=RABBITMQ_CONFIG,
        ) as publisher:
            publisher.publish({
                "order_id": self._context.order_id,
            })

    def on_event(self, event: dict) -> State:
        match event["type"]:

            case "delivery.cancelled" | "delivery.not_found":
                logger.info(
                    "[SAGA] - Delivery cancelable or absent: order_id=%s",
                    self._context.order_id,
                )
                from .cancel_warehouse_state import CancelWarehouseState
                return CancelWarehouseState(self._context)

            case "delivery.cancel_rejected":
                logger.warning(
                    "[SAGA] - Delivery completed, cancellation rejected: order_id=%s",
                    self._context.order_id,
                )
                from .order_cancel_failed_state import OrderCancelFailedState
                return OrderCancelFailedState(self._context)

        return self

