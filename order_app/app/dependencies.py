# -*- coding: utf-8 -*-
"""Application dependency injector for the Order microservice."""

import logging
import httpx

logger = logging.getLogger(__name__)

# HTTP client for inter-service communication ######################################################
async_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    """
    Returns a shared AsyncClient instance for calling other microservices.
    Creates it if it does not exist yet.
    """
    global async_client
    if async_client is None:
        logger.debug("Creating shared HTTP async client for Order microservice")
        async_client = httpx.AsyncClient()
    return async_client


# Database #########################################################################################
async def get_db():
    """
    Generates database sessions and closes them when finished.
    Used for dependency injection in repository and router functions.
    """
    from app.sql.database import SessionLocal  # pylint: disable=import-outside-toplevel

    logger.debug("Getting database SessionLocal for Order microservice")
    db = SessionLocal()
    try:
        yield db
        await db.commit()
    except Exception as e:
        logger.error("Database transaction failed: %s", str(e))
        await db.rollback()
        raise
    finally:
        await db.close()


# External Services ###############################################################################
PAYMENT_SERVICE_URL = "http://payment_app:8000/payment"
MACHINE_SERVICE_URL = "http://machine_app:8000/machine"
DELIVERY_SERVICE_URL = "http://delivery_app:8000/delivery"


async def get_payment_service():
    """Provides the base URL of the Payment microservice."""
    return PAYMENT_SERVICE_URL


async def get_machine_service():
    """Provides the base URL of the Machine microservice."""
    return MACHINE_SERVICE_URL


async def get_delivery_service():
    """Provides the base URL of the Delivery microservice."""
    return DELIVERY_SERVICE_URL


# Shutdown hook ####################################################################################
async def shutdown_dependencies():
    """Gracefully close resources on application shutdown."""
    global async_client
    if async_client is not None:
        logger.info("Closing HTTP async client for Order microservice")
        await async_client.aclose()
        async_client = None
