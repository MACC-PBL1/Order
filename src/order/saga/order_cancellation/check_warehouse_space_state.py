from ...global_vars import RABBITMQ_CONFIG
from ..base_state import State
from .check_delivery_status_state import CheckDeliveryStatus
from .reject_cancellation_state import RejectCancellationState
from chassis.messaging import (
    MessageType,
    RabbitMQPublisher,
    register_queue_handler,
    start_rabbitmq_listener,
)
import logging

logger = logging.getLogger(__name__)

class CheckWarehouseSpaceState(State):
    async def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self

        return CheckDeliveryStatus(self._context) if await self._ask_space() == True else RejectCancellationState(self._context)

    async def _ask_space(self) -> bool:
        response_queue = f"sagas-warehouse-{self._context.client_id}-{self._context.order_id}"
        response_exchange = "warehouse_sagas"
        response_exchange_type = "topic"
        response_routing_key = f"{self._context.client_id}.{self._context.order_id}"
        warehouse_ok = False

        @register_queue_handler(
            queue=response_queue,
            exchange=response_exchange,
            exchange_type=response_exchange_type,
            routing_key=response_routing_key,
        )
        def _warehouse_response(message: MessageType) -> None:
            nonlocal warehouse_ok
            assert (status := message.get("status")) is not None, "'status' field should be present."
            if (warehouse_ok := (status == "OK")):
                logger.info(
                    "[EVENT:WAREHOUSE_RESERVE:SUCCESS] - Warehouse reserved successfully: "
                    f"order_id={self._context.order_id}"
                )
            else:
                logger.info(
                    "[EVENT:WAREHOUSE_RESERVE:FAILED] - Warehouse reserve failed: "
                    f"order_id={self._context.order_id}, "
                    f"status='{status}'"
                )

        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="cmd",
            exchange_type="topic",
            routing_key="warehouse.reserve",
            auto_delete_queue=True,
        ) as publisher:
            publisher.publish({
                "order_id": str(self._context.order_id),
                "response_exchange": response_exchange,
                "response_exchange_type": response_exchange_type,
                "response_routing_key": response_routing_key
            })
            logger.info(
                "[CMD:WAREHOUSE_RESERVE:SENT] - Sent reserve command: "
                f"order_id={self._context.order_id}, "
            )

        start_rabbitmq_listener(
            queue=response_queue,
            config=RABBITMQ_CONFIG,
            one_use=True,
        )

        return warehouse_ok