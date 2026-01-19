from ...global_vars import RABBITMQ_CONFIG
from ..base_state import State
from .aprove_cancellation_state import ApproveCancellation
from .release_warehouse_state import ReleaseWarehouse
from chassis.messaging import (
    MessageType,
    RabbitMQPublisher,
    register_queue_handler,
    start_rabbitmq_listener,
)
import logging

logger = logging.getLogger(__name__)

class CheckDeliveryStatus(State):
    def _delivery_in_process(self) -> bool:    
        response_queue = f"sagas-delivery-{self._context.client_id}-{self._context.order_id}"
        response_exchange = "delivery_sagas"
        response_exchange_type = "topic"
        response_routing_key = f"{self._context.client_id}.{self._context.order_id}"
        delivery_ok = False

        @register_queue_handler(
            queue=response_queue,
            exchange=response_exchange,
            exchange_type=response_exchange_type,
            routing_key=response_routing_key,
        )
        def _delivery_response(message: MessageType) -> None:
            nonlocal delivery_ok
            assert (status := message.get("status")) is not None, "'status' field should be present."
            if (delivery_ok := (status == "OK")):
                logger.info(
                    "[EVENT:DELIVERY_CANCEL:SUCCESS] - delivery cancelled successfully: "
                    f"order_id={self._context.order_id}"
                )
            else:
                logger.info(
                    "[EVENT:DELIVERY_CANCEL:FAILED] - delivery cancel failed: "
                    f"order_id={self._context.order_id}, "
                    f"status='{status}'"
                )

        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="cmd",
            exchange_type="topic",
            routing_key="delivery.cancel",
            auto_delete_queue=True,
        ) as publisher:
            publisher.publish({
                "order_id": str(self._context.order_id),
                "response_exchange": response_exchange,
                "response_exchange_type": response_exchange_type,
                "response_routing_key": response_routing_key
            })
            logger.info(
                "[CMD:DELIVERY_CANCEL:SENT] - Sent reserve command: "
                f"order_id={self._context.order_id}, "
            )

        start_rabbitmq_listener(
            queue=response_queue,
            config=RABBITMQ_CONFIG,
            one_use=True,
        )

        return not delivery_ok

    async def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self
        return ApproveCancellation(self._context) if not self._delivery_in_process() else ReleaseWarehouse(self._context)
    