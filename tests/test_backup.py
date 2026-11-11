"""Backup and restore tests."""

import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

import app.services.backup_service as bs
from app.config import Settings
from app.database import Base


def _temp_settings(data_dir, db_file):
    db_url = "sqlite+aiosqlite:///" + os.path.join(data_dir, db_file).replace("\\", "/")
    return Settings(
        data_dir=data_dir,
        database_file=db_file,
        database_url=db_url,
    )


@pytest.mark.asyncio
async def test_backup_create_validate_restore(monkeypatch, temp_db_path):
    data_dir = os.path.dirname(temp_db_path)
    test_settings = _temp_settings(data_dir, os.path.basename(temp_db_path))
    monkeypatch.setattr(bs, "settings", test_settings)

    # create a db with schema
    engine = create_async_engine(test_settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    result = bs.create_backup()
    assert result["filename"].endswith(".json")
    assert os.path.exists(result["path"])
    assert result["size"] > 0

    meta = bs.validate_backup(result["path"])
    assert "tables" in meta

    # modify DB: add nothing, just ensure restore keeps tables
    restored = bs.restore_backup(result["path"])
    assert "tables" in restored


@pytest.mark.asyncio
async def test_backup_invalid_rejected(monkeypatch, temp_db_path):
    data_dir = os.path.dirname(temp_db_path)
    test_settings = _temp_settings(data_dir, os.path.basename(temp_db_path))
    monkeypatch.setattr(bs, "settings", test_settings)

    bad = os.path.join(data_dir, "bad_backup.json")
    with open(bad, "w") as f:
        f.write("not json")
    with pytest.raises(bs.BackupError):
        bs.validate_backup(bad)

    incomplete = os.path.join(data_dir, "incomplete.json")
    with open(incomplete, "w") as f:
        f.write('{"metadata": {"tables": ["accounts"]}, "data": {}}')
    with pytest.raises(bs.BackupError):
        bs.validate_backup(incomplete)
