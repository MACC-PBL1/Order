from ..base_state import State
from .check_order_exists_state import CheckOrderExistsState

class InitialState(State):
    """Starting state - order just created"""

    async def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self        
        return CheckOrderExistsState(self._context)
