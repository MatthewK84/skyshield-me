"""
SkyShield ME — Async Database Engine & Session Factory.

Provides the async engine, session maker, and base declarative model.
All sessions are scoped to request lifecycle via FastAPI dependency injection.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=(settings.app_env == "development"),
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a scoped async session."""
    session: AsyncSession = async_session_factory()
    try:
        yield session
    finally:
        await session.close()
