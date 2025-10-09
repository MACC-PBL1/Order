# -*- coding: utf-8 -*-
"""Database session configuration for the Order microservice."""

import os
import logging
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------------------------
# Database URL
# -----------------------------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URL",
    "sqlite+aiosqlite:///./order.db"  # Nombre adaptado al microservicio
)

# -----------------------------------------------------------------------------------------------
# Async Engine
# -----------------------------------------------------------------------------------------------
try:
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {},
        echo=False,  # Cambiar a True para depurar queries SQL
        future=True,
    )
    logger.info("Async database engine for Order microservice created successfully.")
except Exception as e:
    logger.error("Failed to create database engine: %s", str(e))
    raise

# -----------------------------------------------------------------------------------------------
# Session factory
# -----------------------------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True,
)

# -----------------------------------------------------------------------------------------------
# Declarative Base
# -----------------------------------------------------------------------------------------------
Base = declarative_base()
