# -*- coding: utf-8 -*-
"""Consumer that listens to Client/Auth events and updates the stored public key."""

import asyncio
import logging
import os
from microservice_chassis.events import EventSubscriber

logger = logging.getLogger(__name__)


PUBLIC_KEY_PATH = "/tmp/keys/public.pem"

class ClientEventConsumer:
    """Listens to 'auth.events' and updates the public key when rotated."""

    def __init__(self):
        self.subscriber = EventSubscriber(
            exchange="auth.events",
            queue_name="client_public_key_queue"
        )

    async def start(self):
        """Start listening for 'client.refresh_public_key' events."""
        logger.info(" Starting ClientEventConsumer: waiting for 'client.refresh_public_key' events...")

        async for event in self.subscriber.listen("client.refresh_public_key"):
            await self._handle_refresh_event(event)

    async def _handle_refresh_event(self, event: dict):
        """Handle received refresh_public_key event."""
        try:
            logger.info(" Received event 'client.refresh_public_key': %s", event)

            # Extraer la clave pública (puede venir como str o dict)
            data = event.get("data")
            if isinstance(data, str):
                new_public_key = data
            elif isinstance(data, dict):
                new_public_key = data.get("public_key")
            else:
                new_public_key = None

            if not new_public_key or not new_public_key.startswith("-----BEGIN PUBLIC KEY-----"):
                logger.warning(" Invalid or missing public key in event. Skipping update.")
                return

            # Crear carpeta /tmp/keys si no existe
            os.makedirs(os.path.dirname(PUBLIC_KEY_PATH), exist_ok=True)

            # Guardar la nueva clave pública
            with open(PUBLIC_KEY_PATH, "w") as f:
                f.write(new_public_key)

            logger.info(" Public key updated successfully at %s", PUBLIC_KEY_PATH)

        except Exception as e:
            logger.error(f" Error processing client.refresh_public_key event: {e}", exc_info=True)


async def start_client_consumer():
    """Launch the ClientEventConsumer asynchronously with automatic reconnection."""
    consumer = ClientEventConsumer()
    while True:
        try:
            await consumer.start()
        except Exception as e:
            logger.error(f"ClientEventConsumer crashed: {e}. Reconnecting in 5s...", exc_info=True)
            await asyncio.sleep(5)
