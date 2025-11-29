from .base_state import State

class ProcessApprovedState(State):
    """Terminal state - order successfully processed"""

    def on_event(self, event: State) -> State:
        return self
