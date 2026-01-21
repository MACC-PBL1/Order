from ..global_vars import (
    LISTENING_QUEUES,
    PUBLIC_KEY,
    RABBITMQ_CONFIG,
)
from ..sql import (
    Order,
    update_order_status,
)
from chassis.consul import CONSUL_CLIENT
from chassis.messaging import (
    MessageType,
    RabbitMQPublisher,
    register_queue_handler,
)
from chassis.sql import SessionLocal
from random import randint
import asyncio
import logging
import requests

logger = logging.getLogger(__name__)

@register_queue_handler(LISTENING_QUEUES["order_status_update"])
async def order_status_update(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None, "'order_id' should exist."
    assert (status := message.get("status")) is not None, "'status' should exist."

    order_id = int(order_id)
    status = str(status)

    if status == Order.STATUS_PROCESSED:
        await asyncio.sleep(randint(5, 10))
        status = Order.STATUS_PACKAGED
        with RabbitMQPublisher(
            queue="delivery.start",
            rabbitmq_config=RABBITMQ_CONFIG,
        ) as publisher:
            publisher.publish({
                "order_id": order_id,
            })

    async with SessionLocal() as db:
        await update_order_status(
            db=db, 
            order_id=order_id, 
            status=status,
        )

    logger.info(
        "[EVENT:STATUS_UPDATE:SUCCESS] - Order status updated: "
        f"order_id={order_id}, "
        f"status={status}"
    )

@register_queue_handler(
    queue=LISTENING_QUEUES["public_key"],
    exchange="public_key",
    exchange_type="fanout"
)
def public_key(message: MessageType) -> None:
    global PUBLIC_KEY
    assert (auth_base_url := CONSUL_CLIENT.discover_service("auth")) is not None, (
        "The 'auth' service should be accesible"
    )
    assert "public_key" in message, "'public_key' field should be present."
    assert message["public_key"] == "AVAILABLE", (
        f"'public_key' value is '{message['public_key']}', expected 'AVAILABLE'"
    )
    address, port = auth_base_url
    response = requests.get(f"{address}:{port}/auth/key", timeout=5)
    assert response.status_code == 200, (
        f"Public key request returned '{response.status_code}', should return '200'"
    )
    data: dict = response.json()
    new_key = data.get("public_key")
    assert new_key is not None, (
        "Auth response did not contain expected 'public_key' field."
    )
    PUBLIC_KEY["key"] = str(new_key)
    logger.info(
        "[EVENT:PUBLIC_KEY:UPDATED] - Public key updated: "
        f"key={PUBLIC_KEY["key"]}"
    )