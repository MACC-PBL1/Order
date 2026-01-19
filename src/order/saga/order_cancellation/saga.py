from ..base_saga import BaseSaga
from ..base_state import (
    State, 
    StateContext,
)
from .aprove_cancellation_state import ApproveCancellation
from .initial_state import InitialState
from .reject_cancellation_state import RejectCancellationState
from .release_warehouse_state import ReleaseWarehouse
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class OrderCancellationSaga(BaseSaga):
    SAGA_HISTORY: dict[int, list[str]] = defaultdict(list)

    def __init__(self, context: StateContext) -> None:
        self._context = context
        self._state = InitialState(self._context)

    async def _on_event(self, event: State) -> None:
        self._state = await self._state.on_event(event)
        OrderCancellationSaga.SAGA_HISTORY[self._context.order_id].append(str(self._state))

    async def process(self) -> bool:
        logger.info(f"[LOG:SAGA] - Processing Order {self._context.order_id}")

        # Start the saga
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        await self._on_event(self._state)
        
        # Check order exists
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        await self._on_event(self._state)

        # If not exist, exit
        if isinstance(self._state, RejectCancellationState):
            logger.warning("[LOG:SAGA] - Order cancellation rejected, does not exist.")
            return False

        # Check warehouse space
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        await self._on_event(self._state)

        # If not enough space
        if isinstance(self._state, RejectCancellationState):
            logger.warning("[LOG:SAGA] - Order cancellation rejected, not enough space in warehouse.")
            return False

        # Check delivery status
        logger.info(f"[LOG:SAGA] - State: {self.get_state()}")
        await self._on_event(self._state)

        if isinstance(self._state, ReleaseWarehouse):
            logger.warning("[LOG:SAGA] - Order cancellation rejected, delivery already in process.")
            await self._on_event(self._state)
            return False
        
        if isinstance(self._state, ApproveCancellation):
            logger.info("[LOG:SAGA] - Order cancellation approved.")
            await self._on_event(self._state)
            return True

        return False

    def get_state(self) -> str:
        return str(self._state)

