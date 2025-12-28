from .base_state import (
    StateContext,
    State,
)
from .initial_state import InitialState
from .order_cancelled_state import OrderCancelledState
from .process_approved_state import ProcessApprovedState
from .release_client_balance_state import ReleaseClientBalanceState
from .order_cancel_failed_state import OrderCancelFailedState
from typing import Dict, List
import logging

from .initial_cancel_order_state import CancelOrderState
from .registry import remove_saga

logger = logging.getLogger(__name__)
SAGA_HISTORY: Dict[int, List[str]] = {}

class Saga:  
    def __init__(self, context: StateContext):
        self._context = context
        self._state = InitialState(context)
        SAGA_HISTORY[self._context.order_id] = [str(self._state)]
    
    def _on_event(self, event: State):
        self._state = self._state.on_event(event)
        SAGA_HISTORY[self._context.order_id].append(str(self._state))
    
    def process(self) -> bool:
        logger.info(f"[LOG:SAGA] - Processing Order {self._context.order_id}")
        
        # Start the saga
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        self._on_event(self._state)
        
        # Check credit
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        self._on_event(self._state)
        
        # If cancelled, exit
        if isinstance(self._state, OrderCancelledState):
            logger.warning("[LOG:SAGA] - Order cancelled, no funds.")
            return False
        
        # Check delivery
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        self._on_event(self._state)
        
        if isinstance(self._state, ReleaseClientBalanceState):
            logger.info(f"[LOG:SAGA] - Order cancelled, incorrect zip code")
            self._on_event(self._state)
            return False
        
        if isinstance(self._state, ProcessApprovedState):
            logger.info("[LOG:SAGA] - Order approved")
            return True
        
        return False
    
    def get_state(self) -> str:
        return str(self._state)
    

    def process_cancel(self) -> None:
        logger.info(
            "[LOG:SAGA] - Starting cancellation for order_id=%s",
            self._context.order_id,
        )

        self._state = CancelOrderState(self._context)
        SAGA_HISTORY[self._context.order_id].append(str(self._state))
        self._state.execute()
        self.handle_event({"type": "__start__"})

    def handle_event(self, event: dict) -> None:
        """
        Called by RabbitMQ listeners when an external event arrives.
        """
        logger.info(
            "[LOG:SAGA] - Event received: %s | order_id=%s",
            event["type"],
            self._context.order_id,
        )

        new_state = self._state.on_event(event)

        if new_state is self._state:
            return

        self._state = new_state
        SAGA_HISTORY[self._context.order_id].append(str(self._state))
        self._state.execute()

        if isinstance(self._state, (OrderCancelledState, OrderCancelFailedState)):
            logger.info(
                "[LOG:SAGA] - Cancellation saga finished for order_id=%s",
                self._context.order_id,
            )
            remove_saga(self._context.order_id)