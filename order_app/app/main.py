# -*- coding: utf-8 -*-
"""Main file to start FastAPI application for the Order microservice."""

import asyncio
import logging.config
import os
from contextlib import asynccontextmanager
from threading import Thread
from fastapi import FastAPI

from app.routers import main_router
from app.routers.main_router import event_publisher
from app.sql import models, database
from app.messaging.machine_consumer import MachineEventConsumer
from app.messaging.client_consumer import start_client_consumer
from chassis.consul import ConsulClient 
from chassis.messaging.publisher import RabbitMQPublisher
from chassis.messaging.types import RabbitMQConfig

# -----------------------------------------------------------------------------------------------
# Logging configuration
# -----------------------------------------------------------------------------------------------
logging.config.fileConfig(os.path.join(os.path.dirname(__file__), "logging.ini"))
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------------------------
# Publisher global (nuevo con la chassis)
# -----------------------------------------------------------------------------------------------
rabbitmq_config: RabbitMQConfig = {
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

# Publisher compartido para el microservicio
event_publisher = RabbitMQPublisher(
    queue="order_queue",
    rabbitmq_config=rabbitmq_config,
)

# -----------------------------------------------------------------------------------------------
# Lifespan management (startup / shutdown)
# -----------------------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle Order microservice startup and shutdown."""
    try:
        logger.info(" Starting up Order microservice...")

        # Crear tablas si no existen
        try:
            logger.info("Creating Order database tables (if not exist)")
            async with database.engine.begin() as conn:
                await conn.run_sync(models.Base.metadata.create_all)
        except Exception as e:
            logger.error(" Error creating tables: %s", str(e))

        # Conectar el RabbitMQPublisher
        try:
            logger.info("Connecting RabbitMQPublisher to RabbitMQ...")
            event_publisher._connect()
            logger.info(" RabbitMQPublisher connected")
        except Exception as e:
            logger.error(" Error connecting RabbitMQPublisher: %s", str(e))

        logger.info("Registering service to Consul...")
        try:
            service_port = int(os.getenv("PORT", "8000"))
            consul = ConsulClient(logger=logger)
            consul.register_service(service_name="order-service", port=service_port, health_path="/order/health")
            
        except Exception as e:
            logger.error(f"Failed to register with Consul: {e}")
        # Iniciar listener de Machine en thread separado
        # try:
        #     logger.info("Starting Machine event listener...")
        #     app.state.machine_thread = Thread(target=start_machine_consumer, daemon=True)
        #    app.state.machine_thread.start()
        #     logger.info(" Machine event listener started.")
        # except Exception as e:
        #     logger.error(" Error starting Machine event listener: %s", str(e))

        # Iniciar listener de Client/Auth en thread separado
        try:
            logger.info("Starting Client/Auth event listener...")
            app.state.client_thread = Thread(target=start_client_consumer, daemon=True)
            app.state.client_thread.start()
            logger.info(" Client/Auth event listener started.")
        except Exception as e:
            logger.error(" Error starting Client/Auth event listener: %s", str(e))

        logger.info(" Order microservice fully started and listening for events.")
        yield

    finally:
        logger.info("Shutting down Order microservice gracefully...")

        # Cerrar RabbitMQPublisher
        try:
            event_publisher._close()
            logger.info(" RabbitMQPublisher connection closed.")
        except Exception as e:
            logger.warning(" Error closing RabbitMQPublisher: %s", e)

        # Cerrar motor de base de datos
        await database.engine.dispose()
        logger.info(" Database engine disposed.")
        logger.info(" Order microservice shutdown complete.")


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