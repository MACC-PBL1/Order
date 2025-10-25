# -*- coding: utf-8 -*-
"""Consumer that listens to Client/Auth events and updates the stored public key."""

import os
import ssl
import time
import pika
import logging
from threading import Thread
from chassis.messaging.utils import (
    register_queue_handler,
    start_rabbitmq_listener,
)
from chassis.messaging.types import RabbitMQConfig

logger = logging.getLogger(__name__)

PUBLIC_KEY_PATH = "/tmp/keys/public.pem"


# ------------------------------------------------------------------------------
# OPTIONAL: Ensure binding exists between auth.events → client_public_key_queue
# ------------------------------------------------------------------------------
def ensure_queue_binding(config: RabbitMQConfig):
    """Ensure queue is bound to 'auth.events' exchange with routing key 'client.refresh_public_key'."""
    try:
        logger.info("Ensuring queue binding between 'auth.events' and 'client_public_key_queue'...")

        context = ssl.create_default_context(cafile=config["ca_cert"])
        context.load_cert_chain(certfile=config["client_cert"], keyfile=config["client_key"])

        ssl_opts = pika.SSLOptions(context, config["host"])

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=config["host"],
                port=config["port"],
                ssl_options=ssl_opts,
            )
        )
        channel = connection.channel()

        channel.exchange_declare(exchange="auth.events", exchange_type="topic", durable=True)
        channel.queue_declare(queue="client_public_key_queue", durable=True)
        channel.queue_bind(
            exchange="auth.events",
            queue="client_public_key_queue",
            routing_key="client.refresh_public_key",
        )

        connection.close()
        logger.info(" Queue successfully bound to exchange.")
    except Exception as e:
        logger.error(f"Failed to ensure binding: {e}", exc_info=True)


# ------------------------------------------------------------------------------
# HANDLER — ejecutado al recibir un mensaje
# ------------------------------------------------------------------------------
@register_queue_handler("client_public_key_queue")
def handle_refresh_public_key(message: dict):
    """Handle 'client.refresh_public_key' events from Auth Service."""
    try:
        logger.info("Received event 'client.refresh_public_key': %s", message)

        data = message.get("data")
        if isinstance(data, str):
            new_public_key = data
        elif isinstance(data, dict):
            new_public_key = data.get("public_key")
        else:
            new_public_key = None

        if not new_public_key or not new_public_key.startswith("-----BEGIN PUBLIC KEY-----"):
            logger.warning("Invalid or missing public key in event. Skipping update.")
            return

        os.makedirs(os.path.dirname(PUBLIC_KEY_PATH), exist_ok=True)

        with open(PUBLIC_KEY_PATH, "w") as f:
            f.write(new_public_key)

        logger.info("✅ Public key updated successfully at %s", PUBLIC_KEY_PATH)

    except Exception as e:
        logger.error(f"Error processing 'client.refresh_public_key' event: {e}", exc_info=True)


# ------------------------------------------------------------------------------
# START LISTENER
# ------------------------------------------------------------------------------
def start_client_consumer():
    """Start the RabbitMQ listener in a background thread and auto-reconnect."""
    config: RabbitMQConfig = {
        "host": os.getenv("RABBITMQ_HOST", "rabbitmq"),
        "port": int(os.getenv("RABBITMQ_PORT", "5671")),
        "username": os.getenv("RABBITMQ_USER", "guest"),
        "password": os.getenv("RABBITMQ_PASS", "guest"),
        "use_tls": True,
        "ca_cert": "/etc/rabbitmq/ssl/ca_cert.pem",
        "client_cert": "/etc/rabbitmq/ssl/client_cert.pem",
        "client_key": "/etc/rabbitmq/ssl/client_key.pem",
        "prefetch_count": 10,
    }

    def _listener():
        while True:
            try:
                ensure_queue_binding(config)

                start_rabbitmq_listener(
                    queue="client_public_key_queue",
                    config=config,
                )
            except Exception as e:
                logger.error(f"ClientEventConsumer crashed: {e}. Reconnecting in 5s...", exc_info=True)
                time.sleep(5)

    Thread(target=_listener, daemon=True).start()
    logger.info("ClientEventConsumer started and listening for 'client.refresh_public_key' events.")
