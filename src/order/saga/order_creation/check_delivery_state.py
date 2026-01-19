from ..base_state import State
from .process_approved_state import ProcessApprovedState
from .release_client_balance_state import ReleaseClientBalanceState

class CheckDeliveryState(State):
    """Check if delivery zipcode is valid"""

    async def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self
        
        is_valid_zipcode = self._context.zipcode in ["01", "20", "48"]

        if is_valid_zipcode:
            return ProcessApprovedState(self._context)
        else:
            return ReleaseClientBalanceState(self._context)