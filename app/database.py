"""Database engine, session, and dependency management.

SQLite is the only supported backend. All financial amounts are stored as
integer minor currency units (cents) to avoid binary floating-point error.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def _normalize_sqlite_url(url: str) -> str:
    """Ensure the SQLite URL uses the async driver and an absolute path."""
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///") :]
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        return "sqlite+aiosqlite:///" + path.replace("\\", "/")
    return url


def create_engine():
    """Create the async SQLAlchemy engine."""
    database_url = _normalize_sqlite_url(settings.database_url)
    connect_args = {"check_same_thread": False}
    return create_async_engine(database_url, echo=settings.debug, connect_args=connect_args)


engine = create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The transaction is committed when the request completes successfully and
    rolled back on error, so multi-step financial operations (e.g. transfers)
    are atomic.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


__all__ = [
    "Base",
    "engine",
    "async_session_factory",
    "get_session",
    "create_engine",
]
