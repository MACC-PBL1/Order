from ..base_state import State

class OrderCancelledState(State):
    """Terminal state - order cancelled"""

    async def on_event(self, event: State) -> State:
        return self