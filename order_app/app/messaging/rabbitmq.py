# -*- coding: utf-8 -*-
"""RabbitMQ connection and message publishing utilities."""

import asyncio
import aio_pika
import json
import os
import logging

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://user:password@rabbitmq:5672/")
connection: aio_pika.RobustConnection | None = None
channel: aio_pika.Channel | None = None


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://user:password@rabbitmq:5672/")
connection: aio_pika.RobustConnection | None = None
channel: aio_pika.Channel | None = None

async def init_rabbitmq(retries: int = 10, delay: int = 3):
    """Initialize RabbitMQ connection and channel with retries."""
    global connection, channel
    attempt = 1

    while attempt <= retries:
        try:
            logger.info(f"Connecting to RabbitMQ (attempt {attempt}/{retries}): {RABBITMQ_URL}")
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            channel = await connection.channel()
            logger.info("✅ Connected to RabbitMQ successfully.")
            return
        except Exception as e:
            logger.error(f"❌ Error connecting to RabbitMQ: {e}")
            if attempt == retries:
                logger.error("🚨 Failed to connect to RabbitMQ after multiple attempts.")
                return
            attempt += 1
            await asyncio.sleep(delay)


async def close_rabbitmq():
    """Close RabbitMQ connection gracefully."""
    global connection, channel
    try:
        if channel:
            await channel.close()
        if connection:
            await connection.close()
        logger.info("🔌 RabbitMQ connection closed.")
    except Exception as e:
        logger.error("Error closing RabbitMQ connection: %s", str(e))


async def publish_message(routing_key: str, message: dict):
    """Publish a message to a default exchange."""
    global channel
    if not channel:
        logger.warning("RabbitMQ channel not initialized — message skipped.")
        return

    try:
        exchange = await channel.declare_exchange("order_exchange", aio_pika.ExchangeType.DIRECT)
        body = json.dumps(message).encode()
        await exchange.publish(aio_pika.Message(body=body), routing_key=routing_key)
        logger.info(f"📤 Published message → order_exchange:{routing_key} → {message}")
    except Exception as e:
        logger.error("❌ Failed to publish message: %s", str(e))

