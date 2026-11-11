"""Alembic environment configuration for Finora.

Supports offline and online (async SQLite) migration modes. The database URL
and model metadata are sourced from the application configuration so migrations
always match the current SQLAlchemy models.
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure the application package is importable when alembic runs from the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
database_url = settings.database_url
# Alembic's sync offline mode does not understand the +aiosqlite driver suffix.
offline_url = database_url
if offline_url.startswith("sqlite+aiosqlite:///"):
    offline_url = offline_url.replace("sqlite+aiosqlite:///", "sqlite:///")
# The async engine needs the +aiosqlite driver.
async_url = database_url
if async_url.startswith("sqlite:///"):
    async_url = async_url.replace("sqlite:///", "sqlite+aiosqlite:///")


def run_migrations_offline() -> None:
    """Run migrations without connecting to the database."""
    context.configure(
        url=offline_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations connected to the database asynchronously."""
    connectable = create_async_engine(async_url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
