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
from chassis.sql import (
    SessionLocal
)
import logging

logger = logging.getLogger(__name__)

@register_queue_handler(LISTENING_QUEUES["payment_confirmation"])
async def payment_confirmation(message: MessageType) -> None:
    assert (client_id := message.get("client_id")) is not None, "'client_id' field should be present."
    assert (order_id := message.get("order_id")) is not None, "'order_id' field should be present."
    assert (status := message.get("status")) is not None, "'status' field should be present."

    client_id = int(client_id)
    order_id = int(order_id)

    ## Pagoa onartu da, bidali makinari pedidoa eta entrega bat sortu
    ## Pagoa ez bada onartu markatu eskaera kantzelatua bezala
    if status != "OK":
        async with SessionLocal() as db:
            assert await update_order_status(db, order_id, Order.STATUS_CANCELLED) is not None, f"Order: '{order_id}' should exist."
        logger.info(f"Client: '{client_id}' had a problem '{status}' paying order {order_id}")
        return
    
    async with SessionLocal() as db:
        assert (db_order := await update_order_status(db, order_id, Order.STATUS_IN_PROGRESS)) is not None, f"Order: '{order_id}' should exist."

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["piece_request"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish({
            "order_id": order_id,
            "amount": db_order.piece_amount,
        })

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["delivery_create"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish({
            "order_id": order_id,
            "client_id": client_id,
        })

@register_queue_handler(LISTENING_QUEUES["piece_confirmation"])
async def piece_confirmation(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None, "'order_id' field should be present."
    assert (piece_id := message.get("piece_id")) is not None, "'piece_id' field should be present."

    order_id = int(order_id)
    piece_id = int(piece_id)

    ## Jun kontatzen piezak, eta behin piezak guztiak sortzean, enpaketatu eta delibery estadoa aldatau
    async with SessionLocal() as db:
        assert (db_order := await get_order(db, order_id)) is not None, f"Order: '{order_id}' should exist."
    
    if piece_id != (db_order.piece_amount - 1):
        return
    
    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["delivery.update_status"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish({
            "order_id": order_id,
            "status": "packaged",
        })

@register_queue_handler(LISTENING_QUEUES["order_status_update"])
async def order_status_update(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None, "'order_id' field should be present."
    assert (status := message.get("status")) is not None, "'status' field should be present."

    order_id = int(order_id)

    ## Orderra entregatua (bakarrik entregatua)? bezala dagoela jarri
    async with SessionLocal() as db:
        await update_order_status(db, order_id, Order.STATUS_CREATED)

@register_queue_handler(
    queue=LISTENING_QUEUES["public_key"],
    exchange="public_key",
    exchange_type="fanout"
)
def public_key(message: MessageType) -> None:
    global PUBLIC_KEY
    assert (public_key := message.get("public_key")) is not None, "'public_key' field should be present."
    PUBLIC_KEY = str(public_key)