# db.py — TapTap POD Analytics Chatbot
# SQLAlchemy async engine and session management.
# Replaces the old database.py (asyncpg pool) with SQLAlchemy ORM approach.

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from logger import logger

load_dotenv()

# Module-level engine and session factory — initialised at startup
_engine: AsyncEngine | None = None
_async_session: sessionmaker | None = None


def _build_dsn() -> str:
    """Build the asyncpg DSN from individual .env variables."""
    host     = os.getenv("DB_HOST")
    port     = os.getenv("DB_PORT", "5432")
    name     = os.getenv("DB_NAME")
    user     = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    ssl      = os.getenv("DB_SSL", "require")

    if not all([host, name, user, password]):
        raise RuntimeError(
            "Missing DB environment variables. "
            "Ensure DB_HOST, DB_NAME, DB_USER, DB_PASSWORD are set in .env"
        )

    # SQLAlchemy async PostgreSQL uses postgresql+asyncpg driver
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}?ssl={ssl}"


async def init_db() -> None:
    """Create the async engine and session factory. Called once at startup."""
    global _engine, _async_session

    dsn = _build_dsn()

    _engine = create_async_engine(
        dsn,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
        echo=False,  # Set True to log all SQL statements (useful for debugging)
    )

    _async_session = sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("SQLAlchemy async engine initialised.")


async def close_db() -> None:
    """Dispose the engine. Called at shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("SQLAlchemy async engine disposed.")
        _engine = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a SQLAlchemy session.
    Used in analytics.py for every query:
        async with get_session() as session:
            result = await session.execute(...)
    """
    if _async_session is None:
        raise RuntimeError("DB not initialised. Call init_db() first.")

    async with _async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()