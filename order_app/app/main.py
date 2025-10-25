# -*- coding: utf-8 -*-
"""Main file to start FastAPI application for the Order microservice."""

import asyncio
import logging.config
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.routers import main_router
from app.routers.main_router import event_publisher
from app.sql import models, database
from app.messaging.machine_consumer import MachineEventConsumer
from app.messaging.client_consumer import start_client_consumer

# -----------------------------------------------------------------------------------------------
# Logging configuration
# -----------------------------------------------------------------------------------------------
logging.config.fileConfig(os.path.join(os.path.dirname(__file__), "logging.ini"))
logger = logging.getLogger(__name__)



# -----------------------------------------------------------------------------------------------
# Lifespan management (startup / shutdown)
# -----------------------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle Order microservice startup and shutdown."""
    try:
        logger.info(" Starting up Order microservice...")

        #  Crear tablas si no existen
        try:
            logger.info("Creating Order database tables (if not exist)")
            async with database.engine.begin() as conn:
                await conn.run_sync(models.Base.metadata.create_all)
        except Exception as e:
            logger.error(" Error creating tables: %s", str(e))

        #  Conectar el EventPublisher
        try:
            logger.info("Connecting EventPublisher to RabbitMQ...")
            event_publisher.connect()
            logger.info(" EventPublisher connected")
        except Exception as e:
            logger.error(" Error connecting EventPublisher: %s", str(e))

        #  Iniciar el consumer de Machine (escucha eventos de machine.events)
        try:
            logger.info("Starting Machine event consumer...")
            machine_consumer = MachineEventConsumer()
            # Ejecutar el consumer en background
            app.state.machine_consumer_task = asyncio.create_task(machine_consumer.start())
            logger.info(" Machine event consumer started")
        except Exception as e:
            logger.error(" Error starting Machine consumer: %s", str(e))
            
        #  Iniciar también el consumer de Client/Auth (actualiza public_key)
        try:
            logger.info("Starting Client/Auth event consumer...")
            app.state.client_consumer_task = asyncio.create_task(start_client_consumer())
            logger.info(" Client/Auth event consumer started")
        except Exception as e:
           logger.error(" Error starting Client/Auth consumer: %s", str(e))

        logger.info(" Order microservice started and listening for Machine events.")
        yield

    finally:
        logger.info("🧹 Shutting down Order microservice gracefully...")
        
        # Cancelar el consumer task
        if hasattr(app.state, "machine_consumer_task"):
            app.state.machine_consumer_task.cancel()
            try:
                await app.state.machine_consumer_task
            except asyncio.CancelledError:
                logger.info("Machine consumer task cancelled")

        # Cancelar el client_consumer task
        if hasattr(app.state, "client_consumer_task"):
            app.state.client_consumer_task.cancel()
            try:
                await app.state.client_consumer_task
            except asyncio.CancelledError:
                logger.info("Client/Auth consumer task cancelled")

        # Cerrar el EventPublisher
        try:
            event_publisher.close()
            logger.info("EventPublisher closed")
        except Exception as e:
            logger.warning("Error closing EventPublisher: %s", e)

        # Cerrar engine de base de datos
        await database.engine.dispose()
        logger.info("🔌 Order microservice shutdown complete.")


# -----------------------------------------------------------------------------------------------
# OpenAPI metadata
# -----------------------------------------------------------------------------------------------
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DESCRIPTION = """
**Order Microservice**

This service manages manufacturing orders, including:
- Creating new orders
- Updating their status
- Coordinating with Payment, Machine, and Delivery services.
"""

tags_metadata = [
    {"name": "Order", "description": "Endpoints to **CREATE**, **READ**, **UPDATE**, or **DELETE** orders."}
]

# -----------------------------------------------------------------------------------------------
# FastAPI app instance
# -----------------------------------------------------------------------------------------------
app = FastAPI(
    title="FastAPI - Order Service",
    description=DESCRIPTION,
    version=APP_VERSION,
    redoc_url=None,
    openapi_tags=tags_metadata,
    servers=[{"url": "/", "description": "Development Server"}],
    license_info={"name": "MIT License", "url": "https://choosealicense.com/licenses/mit/"},
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------------------------------
app.include_router(main_router.router)

logger.info("Order microservice v%s initialized successfully", APP_VERSION)