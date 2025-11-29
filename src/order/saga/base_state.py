from abc import (
    ABC,
    abstractmethod,
)
from dataclasses import dataclass

@dataclass
class StateContext:
    """Context that flows through the saga"""
    order_id: int
    client_id: int
    total_amount: float
    zipcode: str

class State(ABC):
    """
    We define a state object which provides some utility functions for the
    individual states within the state machine.
    """

    def __init__(self, context: StateContext):
        self._context = context

    @abstractmethod
    def on_event(self, event: 'State') -> 'State':
        """
        Handle events that are delegated to this State.
        """
        pass

    def __repr__(self):
        """
        Leverages the __str__ method to describe the State.
        """
        return self.__str__()

    def __str__(self):
        """
        Returns the name of the State.
        """
        return self.__class__.__name__