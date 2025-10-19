# -*- coding: utf-8 -*-
"""Main file to start FastAPI application for the Order microservice."""

import logging.config
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.routers import main_router
from app.sql import models, database
from app.messaging.rabbitmq import init_rabbitmq, close_rabbitmq
#from app.messaging.consumer import start_consumer
from app.messaging.machine_consumer import start_machine_consumer

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

        # 🗄️ Crear tablas si no existen
        try:
            logger.info("Creating Order database tables (if not exist)")
            async with database.engine.begin() as conn:
                await conn.run_sync(models.Base.metadata.create_all)
        except Exception as e:
            logger.error(" Error creating tables: %s", str(e))

        #  Inicializar conexión a RabbitMQ
        await init_rabbitmq()

        # Iniciar el consumer de Machine (escucha eventos piece.started / piece.finished)
        app.state.machine_connection = await start_machine_consumer()

        # (Opcional) Si tienes otros consumers, también puedes arrancarlos aquí:
        # app.state.order_connection = await start_consumer()

        logger.info("✅ Order microservice started and listening for Machine events.")
        yield

    finally:
        #  Cerrar conexiones al apagar el servicio
        logger.info("🧹 Shutting down Order microservice gracefully...")
        if hasattr(app.state, "machine_connection"):
            await app.state.machine_connection.close()

        # Si hay otros consumers, ciérralos también
        # if hasattr(app.state, "order_connection"):
        #     await app.state.order_connection.close()

        await close_rabbitmq()
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
