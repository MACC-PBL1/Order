from .messaging import (
    LISTENING_QUEUES,
    RABBITMQ_CONFIG,
)
from .routers import Router
from chassis.messaging import start_rabbitmq_listener
from chassis.sql import (
    Base, 
    Engine,
)
from chassis.consul import ConsulClient 
from contextlib import asynccontextmanager
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config
from threading import Thread
import asyncio
import logging.config
import os

# Configure logging
logging.config.fileConfig(os.path.join(os.path.dirname(__file__), "logging.ini"))
logger = logging.getLogger(__name__)

from .messaging import LISTENING_QUEUES
from .routers import Router


# App Lifespan #####################################################################################
@asynccontextmanager
async def lifespan(__app: FastAPI):
    """Lifespan context manager."""
    try:
        logger.info("[LOG:ORDER] - Starting up")
        try:
            logger.info("[LOG:ORDER] - Creating database tables")
            async with Engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("[LOG:ORDER] - Starting RabbitMQ listeners")
            try:
                for _, queue in LISTENING_QUEUES.items():
                    Thread(
                        target=start_rabbitmq_listener,
                        args=(queue, RABBITMQ_CONFIG),
                        daemon=True,
                    ).start()
            except Exception as e:
                logger.error(f"[LOG:ORDER] - Could not start the RabbitMQ listeners: Reason={e}", exc_info=True)
            logger.info("[LOG:ORDER] - Registering service to Consul...")
            try:
                service_port = int(os.getenv("PORT", "8000"))
                consul = ConsulClient(logger=logger)
                consul.register_service(service_name="order-service", port=service_port, health_path="/order/health")
                
            except Exception as e:
                logger.error(f"[LOG:ORDER] - Failed to register with Consul: Reason={e}", exc_info=True)
        except Exception:
            logger.error("[LOG:ORDER] - Could not create tables at startup")
        yield
    finally:
        logger.info("[LOG:ORDER] - Shutting down database")
        await Engine.dispose()


# OpenAPI Documentation ############################################################################
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
logger.info("[LOG:ORDER] - Running app version %s", APP_VERSION)
DESCRIPTION = """
Order microservice
"""

tag_metadata = [
    {
        "name": "Order",
        "description": "Endpoints related to order",
    },
]

APP = FastAPI(
    redoc_url=None,
    title="FastAPI - Order app",
    description=DESCRIPTION,
    version=APP_VERSION,
    servers=[{"url": "/", "description": "Development"}],
    license_info={
        "name": "MIT License",
        "url": "https://choosealicense.com/licenses/mit/",
    },
    openapi_tags=tag_metadata,
    lifespan=lifespan,
)

APP.include_router(Router)

def start_server():
    ## Run here
    config = Config()

    config.bind = [os.getenv("HOST", "0.0.0.0") + ":" + os.getenv("PORT", "8000")]
    config.workers = int(os.getenv("WORKERS", "1"))

    logger.info("[LOG:ORDER] - Starting Hypercorn server on %s", config.bind)

    asyncio.run(serve(APP, config)) # type: ignore