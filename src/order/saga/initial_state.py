from .check_balance_state import CheckBalanceState
from .base_state import State

class InitialState(State):
    """Starting state - order just created"""

    def on_event(self, event: State) -> State:
        if str(event) == str(self):
            return CheckBalanceState(self._context)
        return self
