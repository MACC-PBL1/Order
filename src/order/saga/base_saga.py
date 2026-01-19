from .base_state import State
from abc import (
    ABC,
    abstractmethod,
)

class BaseSaga(ABC):
    @abstractmethod
    async def _on_event(self, event: State) -> None:
        """
        State change
        """
        pass

    @abstractmethod
    async def process(self) -> bool:
        """
        Process SAGA
        """
        pass

    @abstractmethod
    def get_state(self) -> str:
        pass