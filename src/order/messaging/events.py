from .global_vars import (
    LISTENING_QUEUES,
    PUBLIC_KEY,
    PUBLISHING_QUEUES,
    RABBITMQ_CONFIG,
)
from ..sql import (
    get_order,
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
    assert (order_id := message.get("order_id")) is not None, "'order_id' should exist."
    assert (piece_id := message.get("piece_id")) is not None, "'piece_id' should exist."

    order_id = int(order_id)
    piece_id = int(piece_id)

    async with SessionLocal() as db:
        assert (db_order := await get_order(db, order_id)) is not None, "'db_order' should exist."

    logger.info(
        "[EVENT:PIECE:CREATED] - Ordered piece created: "
        f"order_id={order_id}, "
        f"piece_id={piece_id} "
    )

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
    assert (order_id := message.get("order_id")) is not None, "'order_id' should exist."
    assert (status := message.get("status")) is not None, "'status' should exist."

    order_id = int(order_id)
    status = str(status)

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
    logger.info(
        "[EVENT:PUBLIC_KEY:UPDATED] - Public key updated: "
        f"key={PUBLIC_KEY["key"]}"
    )
