from .global_vars import (
    LISTENING_QUEUES,
    PUBLIC_KEY,
    PUBLISHING_QUEUES,
    RABBITMQ_CONFIG,
)
from ..sql import (
    get_order,
    Order,
    update_order_status,
)
from chassis.messaging import (
    MessageType, 
    RabbitMQPublisher,
    register_queue_handler,
)
from chassis.sql import SessionLocal
from chassis.consul import ConsulClient      
import requests
import logging

logger = logging.getLogger(__name__)                  

@register_queue_handler(LISTENING_QUEUES["piece_confirmation"])
async def piece_confirmation(message: MessageType) -> None:

    logger.info(f"EVENT: Piece confirmation --> Message: {message}")

    with RabbitMQPublisher(
        queue="events.order",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.order",
    ) as publisher:
        publisher.publish({
            "service_name": "order",
            "event_type": "Listen",
            "message": f"EVENT: Piece confirmation --> Message: {message}"
        })

    assert (order_id := message.get("order_id"))
    assert (piece_id := message.get("piece_id"))

    order_id = int(order_id)
    piece_id = int(piece_id)

    async with SessionLocal() as db:
        assert (db_order := await get_order(db, order_id)) is not None, "'db_order' should exist."

    if piece_id != (db_order.piece_amount - 1):
        return

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["delivery_update"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish({
            "order_id": order_id, 
            "status": "packaged"
        })

@register_queue_handler(LISTENING_QUEUES["order_status_update"])
async def order_status_update(message: MessageType) -> None:

    logger.info(f"EVENT: Update order status --> Message: {message}")

    with RabbitMQPublisher(
        queue="events.order",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.order",
    ) as publisher:
        publisher.publish({
            "service_name": "order",
            "event_type": "Listen",
            "message": f"EVENT: Update order status --> Message: {message}"
        })

    assert (order_id := message.get("order_id"))
    assert (status := message.get("status"))

    order_id = int(order_id)

    # TODO: BEGIRATU EA HAU ONDO DAGOEN!
    async with SessionLocal() as db:
        await update_order_status(db, order_id, Order.STATUS_CREATED)

    logger.info(
        f"Order {order_id} status updated to CREATED",
        extra={"order_id": order_id}
    )

@register_queue_handler(
    queue=LISTENING_QUEUES["public_key"],
    exchange="public_key",
    exchange_type="fanout"
)
def public_key(message: MessageType) -> None:
    global PUBLIC_KEY
    assert (auth_base_url := ConsulClient(logger).get_service_url("auth")), (
        "The 'auth' service should be accesible"
    )
    assert "public_key" in message, "'public_key' field should be present."
    assert message["public_key"] == "AVAILABLE", (
        f"'public_key' value is '{message['public_key']}', expected 'AVAILABLE'"
    )
    response = requests.get(f"{auth_base_url}/auth/key", timeout=5)
    assert response.status_code == 200, (
        f"Public key request returned '{response.status_code}', should return '200'"
    )
    data: dict = response.json()
    new_key = data.get("public_key")
    assert new_key is not None, (
        "Auth response did not contain expected 'public_key' field."
    )
    PUBLIC_KEY["key"] = str(new_key)
    logger.info(f"EVENT: Public key updated: {message}")