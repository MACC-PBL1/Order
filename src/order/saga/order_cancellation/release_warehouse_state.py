from ...global_vars import RABBITMQ_CONFIG
from ..base_state import State
from .reject_cancellation_state import RejectCancellationState
from chassis.messaging import RabbitMQPublisher
import logging

logger = logging.getLogger(__name__)

class ReleaseWarehouse(State):
    async def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self
        
        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="cmd",
            exchange_type="topic",
            routing_key="warehouse.release",
        ) as publisher:
            publisher.publish({
                "order_id": str(self._context.order_id),
            })
            logger.info(
                "[CMD:WAREHOUSE_RELEASE:SENT] - Sent release command: "
                f"order_id={self._context.order_id}, "
            )
        return RejectCancellationState(self._context)

