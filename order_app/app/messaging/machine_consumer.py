# -*- coding: utf-8 -*-
"""Consumer that listens to Machine events and updates the Order database."""
import aio_pika
import json
import logging
import os
from app.sql import crud, database, models

logger = logging.getLogger(__name__)
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://user:password@rabbitmq:5672/")


async def handle_machine_event(message: aio_pika.IncomingMessage):
    """Handles events from the Machine microservice."""
    async with message.process():
        try:
            data = json.loads(message.body)
            routing_key = message.routing_key
            piece_id = data.get("piece_id")

            async with database.SessionLocal() as db:
                if routing_key == "piece.started":
                    logger.info(f" Machine started manufacturing piece {piece_id}")
                    await crud.update_piece_status(db, piece_id, models.Piece.STATUS_MANUFACTURING)

                elif routing_key == "piece.finished":
                    logger.info(f"✅ Machine finished manufacturing piece {piece_id}")
                    piece = await crud.update_piece_status(db, piece_id, models.Piece.STATUS_MANUFACTURED)
                    await crud.update_piece_status(db, piece_id, models.Piece.STATUS_MANUFACTURED)

                    # Buscar si todas las piezas del pedido ya están terminadas
                    order_id = piece.order_id
                    result = await db.execute(
                        models.Piece.__table__.select()
                       .where(models.Piece.order_id == order_id)
                       .where(models.Piece.status != models.Piece.STATUS_MANUFACTURED)
                    )
                    remaining = result.scalars().all()
                    if not remaining:
                        logger.info(" All pieces manufactured! Marking order as 'Completed'.")
                        await crud.update_order_status(db, order_id, models.Order.STATUS_COMPLETED)

        except Exception as e:
            logger.error(f"❌ Error processing machine event: {e}")


async def start_machine_consumer():
    """Starts the consumer listening for Machine events."""
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()

        # Exchange declared by Machine service
        exchange = await channel.declare_exchange("machine.events", aio_pika.ExchangeType.TOPIC)

        # Queue for this microservice
        queue = await channel.declare_queue("order_machine_queue", durable=True)

        # Bind to events we care about
        await queue.bind(exchange, routing_key="piece.started")
        await queue.bind(exchange, routing_key="piece.finished")

        # Start listening
        await queue.consume(handle_machine_event)
        logger.info("Order Service is listening for Machine events.")
        return connection

    except Exception as e:
        logger.error(f"❌ Failed to start Machine consumer: {e}")
        return None
