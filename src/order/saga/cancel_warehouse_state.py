from .base_state import State
from chassis.messaging import RabbitMQPublisher
from ..global_vars import RABBITMQ_CONFIG, PUBLISHING_QUEUES
import logging

logger = logging.getLogger(__name__)


class CancelWarehouseState(State):
    """
    Sends cancellation command to Warehouse.
    """

    def execute(self):
        logger.info(
            "[CMD:WAREHOUSE:CANCEL] - order_id=%s",
            self._context.order_id,
        )

        with RabbitMQPublisher(
            queue=PUBLISHING_QUEUES["warehouse_cancel"],
            rabbitmq_config=RABBITMQ_CONFIG,
        ) as publisher:
            publisher.publish({
                "order_id": self._context.order_id,
            })

    def on_event(self, event: dict) -> State:
        match event["type"]:

            case "warehouse.cancelled":
                logger.info(
                    "[SAGA] - Warehouse cancelled, continuing: order_id=%s",
                    self._context.order_id,
                )
                from .release_client_balance_cancel_state import (
                    ReleaseClientBalanceCancelState,
                )
                return ReleaseClientBalanceCancelState(self._context)

            case "warehouse.cancel_rejected":
                logger.warning(
                    "[SAGA] - Warehouse cancellation rejected: order_id=%s",
                    self._context.order_id,
                )
                from .order_cancel_failed_state import OrderCancelFailedState
                return OrderCancelFailedState(self._context)

        return self
