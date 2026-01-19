from ..base_saga import BaseSaga
from ..base_state import (
    StateContext,
    State,
)
from .initial_state import InitialState
from .order_cancelled_state import OrderCancelledState
from .process_approved_state import ProcessApprovedState
from .release_client_balance_state import ReleaseClientBalanceState
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class OrderCreationSaga(BaseSaga):
    SAGA_HISTORY: Dict[int, List[str]] = {}

    def __init__(self, context: StateContext):
        self._context = context
        self._state = InitialState(context)
        OrderCreationSaga.SAGA_HISTORY[self._context.order_id] = [str(self._state)]
    
    async def _on_event(self, event: State) -> None:
        self._state = await self._state.on_event(event)
        OrderCreationSaga.SAGA_HISTORY[self._context.order_id].append(str(self._state))
    
    async def process(self) -> bool:
        logger.info(f"[LOG:SAGA] - Processing Order {self._context.order_id}")
        
        # Start the saga
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        await self._on_event(self._state)
        
        # Check credit
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        await self._on_event(self._state)
        
        # If cancelled, exit
        if isinstance(self._state, OrderCancelledState):
            logger.warning("[LOG:SAGA] - Order cancelled, no funds.")
            return False
        
        # Check delivery
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        await self._on_event(self._state)
        
        if isinstance(self._state, ReleaseClientBalanceState):
            logger.info("[LOG:SAGA] - Order cancelled, incorrect zip code")
            await self._on_event(self._state)
            return False
        
        if isinstance(self._state, ProcessApprovedState):
            logger.info("[LOG:SAGA] - Order approved")
            return True
        
        return False
    
    def get_state(self) -> str:
        return str(self._state)