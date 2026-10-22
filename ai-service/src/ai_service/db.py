from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ai_service.config import (
    DATABASE_URL,
    DB_MAX_OVERFLOW,
    DB_POOL_RECYCLE_SECONDS,
    DB_POOL_SIZE,
)

engine = (
    create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=DB_POOL_RECYCLE_SECONDS,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
    )
    if DATABASE_URL
    else None
)

SessionLocal = (
    async_sessionmaker(engine, expire_on_commit=False) if engine is not None else None
)


async def ping_database() -> bool:
    """Return True when the configured database is reachable."""
    if engine is None:
        return False

    async with engine.connect() as connection:
        await connection.execute(text('SELECT 1'))

    return True
