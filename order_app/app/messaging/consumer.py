# -*- coding: utf-8 -*-
"""RabbitMQ consumer for the Order microservice."""

import asyncio
import json
import logging
import os
import aio_pika
from app.sql import crud, database

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://user:password@rabbitmq:5672/")


async def handle_message(message: aio_pika.IncomingMessage):
    """Process incoming messages from RabbitMQ."""
    async with message.process():
        try:
            data = json.loads(message.body)
            event = data.get("event")

            logger.info(f"📥 Received event '{event}' → {data}")

            async with database.SessionLocal() as db:
                # AQUI MODIFICAR CON LOS EVENTOS QUE HAY
                if event == "payment.confirmed":
                    await crud.update_order_status(db, data["order_id"], "Paid")
                    logger.info(f"✅ Order {data['order_id']} marked as 'Paid'.")

                elif event == "piece.manufactured":
                    await crud.update_order_status(db, data["order_id"], "In Progress")
                    logger.info(f"⚙️ Order {data['order_id']} now 'In Progress'.")

                elif event == "delivery.completed":
                    await crud.update_order_status(db, data["order_id"], "Completed")
                    logger.info(f"📦 Order {data['order_id']} marked as 'Completed'.")

                else:
                    logger.warning(f"⚠️ Unknown event type: {event}")

        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")


async def start_consumer():
    """Start listening to RabbitMQ for order-related updates."""
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()

        # Declarar la cola que otros servicios usarán para enviar eventos al Order Service
        queue = await channel.declare_queue("order_updates", durable=True) #RabbitMQ tiene una cola llamada order_updates, Los demás microservicios (Payment, Machine, Delivery) enviarán mensajes a esa cola:
        await queue.consume(handle_message)

        logger.info("👂 Order service is now listening for events on 'order_updates' queue.")
        return connection

    except Exception as e:
        logger.error(f"❌ Failed to start consumer: {e}")
        return None
