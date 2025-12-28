from ..global_vars import (
    LISTENING_QUEUES,
    PUBLIC_KEY,
    PUBLISHING_QUEUES,
    RABBITMQ_CONFIG,
)
from ..sql import (
    get_order,
    update_order_status,
    Order,
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

from ..saga.registry import get_saga

logger = logging.getLogger(__name__)                  

# @register_queue_handler(LISTENING_QUEUES["piece_confirmation"])
# async def piece_confirmation(message: MessageType) -> None:
#     assert (order_id := message.get("order_id")) is not None, "'order_id' should exist."
#     assert (piece_id := message.get("piece_id")) is not None, "'piece_id' should exist."

#     order_id = int(order_id)
#     piece_id = int(piece_id)

#     async with SessionLocal() as db:
#         assert (db_order := await get_order(db, order_id)) is not None, "'db_order' should exist."

#     logger.info(
#         "[EVENT:PIECE:CREATED] - Ordered piece created: "
#         f"order_id={order_id}, "
#         f"piece_id={piece_id} "
#     )

#     if piece_id != (db_order.piece_amount - 1):
#         return

#     with RabbitMQPublisher(
#         queue=PUBLISHING_QUEUES["delivery_update"],
#         rabbitmq_config=RABBITMQ_CONFIG
#     ) as publisher:
#         publisher.publish({
#             "order_id": order_id, 
#             "status": "packaged"
#         })

@register_queue_handler(LISTENING_QUEUES["order_completed"])
async def order_completed(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None, "'order_id' should exist."

    order_id = int(order_id)

    logger.info(
        "[EVENT:ORDER:COMPLETED] - All pieces manufactured: order_id=%s",
        order_id,
    )

    async with SessionLocal() as db:
        order = await get_order(db, order_id)
        if order.status == Order.STATUS_CANCELLING:
            logger.warning(
                "[ORDER] Ignoring order_completed for cancelling order %s",
                order_id,
            )
            return
        
        await update_order_status(
            db=db,
            order_id=order_id,
            status="PACKAGED", 
        )

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["delivery_update"],
        rabbitmq_config=RABBITMQ_CONFIG,
    ) as publisher:
        publisher.publish({
            "order_id": order_id,
            "status": "packaged",
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
    assert (auth_base_url := ConsulClient(logger).get_service_url("auth")) is not None, (
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


@register_queue_handler(
    queue=LISTENING_QUEUES["payment_released"],
    exchange="evt",
    exchange_type="topic",
    routing_key="payment.released",
)
async def payment_released(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None

    order_id = int(order_id)

    logger.info(
        "[EVENT:PAYMENT:RELEASED] - order_id=%s",
        order_id,
    )

    saga = get_saga(order_id)
    if saga is None:
        logger.warning(
            "[SAGA] - No saga found for order_id=%s",
            order_id,
        )
        return

    saga.handle_event({
        "type": "payment.released",
        "payload": message,
    })

@register_queue_handler(
    queue=LISTENING_QUEUES["payment_failed"],
    exchange="evt",
    exchange_type="topic",
    routing_key="payment.failed",
)
async def payment_failed(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None

    order_id = int(order_id)

    logger.error(
        "[EVENT:PAYMENT:FAILED] - order_id=%s",
        order_id,
    )

    saga = saga = get_saga(order_id)
    if saga:
        saga.handle_event({
            "type": "payment.failed",
            "payload": message,
        })


@register_queue_handler(
    queue=LISTENING_QUEUES["order_cancel_failed"],
    exchange="evt",
    exchange_type="topic",
    routing_key="order.cancel_failed",
)
async def order_cancel_failed(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None
    order_id = int(order_id)

    async with SessionLocal() as db:
        order = await get_order(db, order_id)

        if order.status != Order.STATUS_CANCELLING:
            logger.warning(
                "[ORDER] Ignoring cancel_failed for order in status %s",
                order.status,
            )
            return

        await update_order_status(
            db=db,
            order_id=order_id,
            status="Cancel failed",
        )


@register_queue_handler(
    queue=LISTENING_QUEUES["warehouse_cancelled"],
    exchange="evt",
    exchange_type="topic",
    routing_key="warehouse.cancelled",
)
async def warehouse_cancelled(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None
    order_id = int(order_id)

    logger.info(
        "[EVENT:WAREHOUSE:CANCELLED] - order_id=%s",
        order_id,
    )

    saga = get_saga(order_id)
    if saga is None:
        logger.warning(
            "[SAGA] - No saga found for order_id=%s",
            order_id,
        )
        return

    saga.handle_event({
        "type": "warehouse.cancelled",
        "payload": message,
    })

@register_queue_handler(
    queue=LISTENING_QUEUES["delivery_cancelled"],
    exchange="evt",
    exchange_type="topic",
    routing_key="delivery.cancelled",
)
async def delivery_cancelled(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None
    order_id = int(order_id)

    logger.info(
        "[EVENT:DELIVERY:CANCELLED] - order_id=%s",
        order_id,
    )

    saga = get_saga(order_id)
    if saga is None:
        logger.warning(
            "[SAGA] - No saga found for order_id=%s",
            order_id,
        )
        return

    saga.handle_event({
        "type": "delivery.cancelled",
        "payload": message,
    })

@register_queue_handler(
    queue=LISTENING_QUEUES["delivery_cancel_rejected"],
    exchange="evt",
    exchange_type="topic",
    routing_key="delivery.cancel_rejected",
)
async def delivery_cancel_rejected(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None
    order_id = int(order_id)

    logger.warning(
        "[EVENT:DELIVERY:CANCEL_REJECTED] - order_id=%s",
        order_id,
    )

    saga = get_saga(order_id)
    if saga is None:
        logger.warning(
            "[SAGA] - No saga found for order_id=%s",
            order_id,
        )
        return

    saga.handle_event({
        "type": "delivery.cancel_rejected",
        "payload": message,
    })

@register_queue_handler(
    queue=LISTENING_QUEUES["delivery_not_found"],
    exchange="evt",
    exchange_type="topic",
    routing_key="delivery.not_found",
)
async def delivery_not_found(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None
    order_id = int(order_id)

    logger.info(
        "[EVENT:DELIVERY:NOT_FOUND] - order_id=%s",
        order_id,
    )

    saga = get_saga(order_id)
    if saga is None:
        logger.warning(
            "[SAGA] - No saga found for order_id=%s",
            order_id,
        )
        return

    saga.handle_event({
        "type": "delivery.not_found",
        "payload": message,
    })


@register_queue_handler(
    queue=LISTENING_QUEUES["order_cancel_completed"],
    exchange="evt",
    exchange_type="topic",
    routing_key="order.cancel_completed",
)
async def order_cancel_completed(message: MessageType) -> None:
    assert (order_id := message.get("order_id")) is not None
    order_id = int(order_id)

    async with SessionLocal() as db:
        order = await get_order(db, order_id)

        if order.status != Order.STATUS_CANCELLING:
            logger.warning(
                "[ORDER] Ignoring cancel_completed for order in status %s",
                order.status,
            )
            return

        await update_order_status(
            db=db,
            order_id=order_id,
            status="CANCELLED",
        )
