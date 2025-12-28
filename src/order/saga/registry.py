from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .saga import Saga 

_saga_registry: Dict[int, "Saga"] = {}


def create_saga(saga):
    _saga_registry[saga._context.order_id] = saga


def get_saga(order_id: int):
    return _saga_registry.get(order_id)


def remove_saga(order_id: int):
    _saga_registry.pop(order_id, None)
