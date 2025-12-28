from .base_state import State
from .cancel_delivery_state import CancelDeliveryState
import logging

logger = logging.getLogger(__name__)

class CancelOrderState(State):
    """
    Entry point for order cancellation saga.
    """

    def execute(self):
        logger.info(
            "[SAGA] - Entered CancelOrderState: order_id=%s",
            self._context.order_id,
        )
    
    def on_event(self, event: dict) -> State:
        if event["type"] == "__start__":
            return CancelDeliveryState(self._context)

        return self
