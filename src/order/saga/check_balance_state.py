from ..messaging.global_vars import RABBITMQ_CONFIG
from .base_state import State
from .check_delivery_state import CheckDeliveryState
from .order_cancelled_state import OrderCancelledState
from chassis.messaging import (
    MessageType,
    RabbitMQPublisher,
    register_queue_handler,
    start_rabbitmq_listener,
)

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
            assert (client_id := message.get("client_id")) is not None, "'client_id' field should be present."
            assert (status := message.get("status")) is not None, "'status' field should be present."
            payment_ok = (status == "OK")

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

        start_rabbitmq_listener(
            queue=response_queue,
            config=RABBITMQ_CONFIG,
            one_use=True,
        )

        return payment_ok