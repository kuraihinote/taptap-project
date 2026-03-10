# database.py — TapTap Analytics Chatbot v3

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from dotenv import load_dotenv

from logger import logger

load_dotenv()

_pool: asyncpg.Pool | None = None


async def init_db_pool() -> asyncpg.Pool:
    """Create and return a connection pool. Called once at startup."""
    global _pool
    db_host     = os.getenv("DB_HOST")
    db_port     = os.getenv("DB_PORT", "5432")
    db_name     = os.getenv("DB_NAME")
    db_user     = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_ssl      = os.getenv("DB_SSL", "require")
    
    if not all([db_host, db_name, db_user, db_password]):
        raise RuntimeError("Database environment variables are missing (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD).")

    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={db_ssl}"

    _pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("Database connection pool initialised.")
    return _pool


async def close_db_pool() -> None:
    """Gracefully close the connection pool. Called at shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        logger.info("Database connection pool closed.")
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the active pool; raises if not yet initialised."""
    if _pool is None:
        raise RuntimeError("DB pool is not initialised. Call init_db_pool() first.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Async context manager that yields a single connection from the pool."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn