"""Dependency injection for FastAPI routes."""

from collections.abc import AsyncGenerator

import httpx
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_ollama_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an httpx client configured for Ollama."""
    async with httpx.AsyncClient(
        base_url=settings.ollama_url,
        timeout=settings.extraction_timeout_seconds,
    ) as client:
        yield client


async def get_colpali_client() -> AsyncGenerator[httpx.AsyncClient | None, None]:
    """Provide an httpx client configured for ColPali, or None if not configured."""
    if not settings.colpali_url:
        yield None
        return
    async with httpx.AsyncClient(
        base_url=settings.colpali_url,
        timeout=settings.colpali_timeout_seconds,
    ) as client:
        yield client
