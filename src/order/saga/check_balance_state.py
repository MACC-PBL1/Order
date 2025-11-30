from ..global_vars import RABBITMQ_CONFIG
from .base_state import State
from .check_delivery_state import CheckDeliveryState
from .order_cancelled_state import OrderCancelledState
from chassis.messaging import (
    MessageType,
    RabbitMQPublisher,
    register_queue_handler,
    start_rabbitmq_listener,
)
import logging

logger = logging.getLogger(__name__)

class CheckBalanceState(State):
    """Check if customer has sufficient credit"""

    def on_event(self, event: State) -> State:
        if str(event) != str(self):
            return self

        if self._ask_balance() == True:
            return CheckDeliveryState(self._context)
        else:
            return OrderCancelledState(self._context)
    
    def _ask_balance(self) -> bool:
        response_queue = f"sagas-payment-{self._context.client_id}-{self._context.order_id}"
        response_exchange = "payment_sagas"
        response_exchange_type = "topic"
        response_routing_key = f"{self._context.client_id}.{self._context.order_id}"

        payment_ok = False

        @register_queue_handler(
            queue=response_queue,
            exchange=response_exchange,
            exchange_type=response_exchange_type,
            routing_key=response_routing_key,
        )
        def payment_response(message: MessageType) -> None:
            nonlocal payment_ok
            assert (status := message.get("status")) is not None, "'status' field should be present."
            if (payment_ok := (status == "OK")):
                logger.info(
                    "[EVENT:PAYMENT_RESERVE:SUCCESS] - Payment reserved successfully: "
                    f"order_id={self._context.order_id}"
                )
            else:
                logger.info(
                    "[EVENT:PAYMENT_RESERVE:FAILED] - Payment reserve failed: "
                    f"order_id={self._context.order_id}, "
                    f"status='{status}'"
                )


        with RabbitMQPublisher(
            queue="",
            rabbitmq_config=RABBITMQ_CONFIG,
            exchange="cmd",
            exchange_type="topic",
            routing_key="payment.reserve",
        ) as publisher:
            publisher.publish({
                "client_id": str(self._context.client_id),
                "total_amount": str(self._context.total_amount),
                "response_exchange": response_exchange,
                "response_exchange_type": response_exchange_type,
                "response_routing_key": response_routing_key
            })
            logger.info(
                "[CMD:PAYMENT_RESERVE:SENT] - Sent reserve command: "
                f"order_id={self._context.order_id}, "
                f"client_id={self._context.client_id}, "
                f"amount={self._context.total_amount}"
            )

        start_rabbitmq_listener(
            queue=response_queue,
            config=RABBITMQ_CONFIG,
            one_use=True,
        )

        return payment_ok