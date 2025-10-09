# -*- coding: utf-8 -*-
"""Main file to start FastAPI application for the Order microservice."""

import logging.config
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routers import main_router
from app.sql import models
from app.sql import database

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
        logger.info("Starting up Order microservice...")
        try:
            logger.info("Creating Order database tables (if not exist)")
            async with database.engine.begin() as conn:
                await conn.run_sync(models.Base.metadata.create_all)
        except Exception as e:
            logger.error("Error creating tables: %s", str(e))
        yield
    finally:
        logger.info("Shutting down Order microservice and closing DB connection...")
        await database.engine.dispose()

# -----------------------------------------------------------------------------------------------
# OpenAPI metadata
# -----------------------------------------------------------------------------------------------
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DESCRIPTION = """
**Order Microservice**

This service manages manufacturing orders, including:
- Creating new orders
- Updating their status
- Fetching order information
- Coordinating with Payment, Machine, and Delivery services
"""

tags_metadata = [
    {
        "name": "Order",
        "description": "Endpoints to **CREATE**, **READ**, **UPDATE**, or **DELETE** orders.",
    }
]

# -----------------------------------------------------------------------------------------------
# FastAPI app instance
# -----------------------------------------------------------------------------------------------
app = FastAPI(
    title="FastAPI - Order Service",
    description=DESCRIPTION,
    version=APP_VERSION,
    redoc_url=None,  # Disable ReDoc
    openapi_tags=tags_metadata,
    servers=[{"url": "/", "description": "Development Server"}],
    license_info={
        "name": "MIT License",
        "url": "https://choosealicense.com/licenses/mit/",
    },
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------------------------------
app.include_router(main_router.router)

logger.info("Order microservice v%s initialized successfully", APP_VERSION)
