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
from chassis.logging.rabbitmq_logging import log_with_context         
import logging

logger = logging.getLogger("order")                  


@register_queue_handler(LISTENING_QUEUES["payment_confirmation"])
async def payment_confirmation(message: MessageType) -> None:

    logger.info(f"EVENT: Payment confirmation --> Message: {message}")

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
            "message": f"EVENT: Payment confirmation --> Message: {message}"
        })

    assert (client_id := message.get("client_id")), "'client_id' field should be present."
    assert (order_id := message.get("order_id")), "'order_id' field should be present."
    assert (status := message.get("status")), "'status' field should be present."

    client_id = int(client_id)
    order_id = int(order_id)

    # Payment KO → cancel order
    if status != "OK":
        async with SessionLocal() as db:
            await update_order_status(db, order_id, Order.STATUS_CANCELLED)

        log_with_context(                                 
            logger,
            logging.WARNING,
            f"Client '{client_id}' had a payment error '{status}'",
            client_id=client_id,
            order_id=order_id
        )
        return

    # Payment OK → update order
    async with SessionLocal() as db:
        db_order = await update_order_status(db, order_id, Order.STATUS_IN_PROGRESS)

    # Request pieces
    data = {
        "order_id": order_id,
        "amount": db_order.piece_amount,
    }

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["piece_request"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish(data)

    log_with_context(                                      
        logger,
        logging.INFO,
        f"EVENT: Request piece --> {data}",
        order_id=order_id
    )

    with RabbitMQPublisher(
        queue="events.order",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.order",
    ) as publisher:
        publisher.publish({
            "service_name": "order",
            "event_type": "Publish",
            "message": f"EVENT: Request piece --> {data}"
        })

    # Create delivery
    delivery_data = {
        "order_id": order_id,
        "client_id": client_id,
    }

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["delivery_create"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish(delivery_data)

    log_with_context(                                      
        logger,
        logging.INFO,
        f"EVENT: Create delivery --> {delivery_data}",
        client_id=client_id,
        order_id=order_id
    )

    with RabbitMQPublisher(
        queue="events.order",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.order",
    ) as publisher:
        publisher.publish({
            "service_name": "order",
            "event_type": "Publish",
            "message": f"EVENT: Create delivery --> {delivery_data}"
        })


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
        db_order = await get_order(db, order_id)

    if piece_id != (db_order.piece_amount - 1):
        return

    data = {"order_id": order_id, "status": "packaged"}

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["delivery_update"],
        rabbitmq_config=RABBITMQ_CONFIG
    ) as publisher:
        publisher.publish(data)

    log_with_context(                                      
        logger,
        logging.INFO,
        f"EVENT: Update delivery --> {data}",
        order_id=order_id
    )

    with RabbitMQPublisher(
        queue="events.order",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.order",
    ) as publisher:
        publisher.publish({
            "service_name": "order",
            "event_type": "Publish",
            "message": f"EVENT: Update delivery --> {data}"
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

    async with SessionLocal() as db:
        await update_order_status(db, order_id, Order.STATUS_CREATED)

    log_with_context(                                      
        logger,
        logging.INFO,
        f"Order {order_id} status updated to CREATED",
        order_id=order_id
    )


@register_queue_handler(
    queue=LISTENING_QUEUES["public_key"],
    exchange="public_key",
    exchange_type="fanout"
)
def public_key(message: MessageType) -> None:

    logger.info(f"EVENT: Public key updated --> Message: {message}")

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
            "message": f"EVENT: Public key updated --> Message: {message}"
        })

    assert (public_key := message.get("public_key"))
    PUBLIC_KEY["key"] = str(public_key)

    log_with_context(                                      
        logger,
        logging.INFO,
        "Public key updated"
    )
