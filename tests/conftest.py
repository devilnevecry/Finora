"""Pytest configuration and fixtures for Finora tests.

Each test receives an isolated async SQLAlchemy session backed by a temporary
SQLite database. No real financial data is used; all data is synthetic.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, async_session_factory  # noqa: F401
from app.models import (  # noqa: F401
    Account,
    Budget,
    Category,
    RecurringTransaction,
    Tag,
    Transaction,
    TransactionTag,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass
    for ext in ("-wal", "-shm", "-journal"):
        try:
            os.remove(path + ext)
        except OSError:
            pass


@pytest.fixture
async def session(temp_db_path: str) -> AsyncGenerator[AsyncSession, None]:
    database_url = "sqlite+aiosqlite:///" + temp_db_path.replace("\\", "/")
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as sess:
        yield sess
    await engine.dispose()


@pytest.fixture
def anyio_backend():
    return "asyncio"
