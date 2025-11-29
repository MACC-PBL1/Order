from .base_state import (
    StateContext,
    State,
)
from .initial_state import InitialState
from .order_cancelled_state import OrderCancelledState
from .process_approved_state import ProcessApprovedState
from .release_client_balance_state import ReleaseClientBalanceState
import logging

logger = logging.getLogger(__name__)

class Saga:  
    def __init__(self, context: StateContext):
        self._context = context
        self._state = InitialState(context)
    
    def _on_event(self, event: State):
        self._state = self._state.on_event(event)
    
    def process(self) -> bool:
        logger.info(f"Processing Order {self._context.order_id}")
        
        # Start the saga
        self._on_event(self._state)
        
        # Check credit
        self._on_event(self._state)
        
        # If cancelled, exit
        if isinstance(self._state, OrderCancelledState):
            return False
        
        # Check delivery
        self._on_event(self._state)
        
        if isinstance(self._state, ReleaseClientBalanceState):
            self._on_event(self._state)
            return False
        
        if isinstance(self._state, ProcessApprovedState):
            logger.info("Order completed")
            return True
        
        return False
    
    def get_state(self) -> str:
        """Get current state name"""
        return str(self._state)