"""Backup and restore service.

A backup is a JSON archive containing all application data plus metadata. It is
written atomically to a temporary file then renamed. Restore validates the
backup before replacing the working database.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import create_engine

from app.config import get_settings
from app.database import Base

settings = get_settings()


@dataclass
class BackupMetadata:
    version: str = "1.0"
    created_at: str = ""
    base_currency: str = settings.base_currency
    tables: list = field(default_factory=list)
    row_counts: dict = field(default_factory=dict)


class BackupError(ValueError):
    pass


def _data_dir() -> str:
    return settings.data_dir


def _database_path() -> str:
    url = settings.database_url
    if url.startswith("sqlite+aiosqlite:///"):
        path = url[len("sqlite+aiosqlite:///") :]
    elif url.startswith("sqlite:///"):
        path = url[len("sqlite:///") :]
    else:
        raise BackupError("unsupported database URL")
    return path


def list_backups() -> list:
    """Return metadata for all backup files in the data directory."""
    backups = []
    data_dir = _data_dir()
    if not os.path.isdir(data_dir):
        return backups
    for name in sorted(os.listdir(data_dir)):
        if name.startswith("finora_backup_") and name.endswith(".json"):
            path = os.path.join(data_dir, name)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("metadata", {})
                backups.append(
                    {
                        "filename": name,
                        "path": path,
                        "size": os.path.getsize(path),
                        "created_at": meta.get("created_at"),
                        "version": meta.get("version"),
                        "tables": meta.get("tables", []),
                        "row_counts": meta.get("row_counts", {}),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
    return backups


def create_backup(filename: str | None = None) -> dict:
    """Create a full database backup as JSON.

    Returns metadata about the created backup.
    """
    data_dir = _data_dir()
    os.makedirs(data_dir, exist_ok=True)
    db_path = _database_path()

    if not os.path.exists(db_path):
        raise BackupError("no database file to back up")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = filename or f"finora_backup_{timestamp}.json"
    backup_path = os.path.join(data_dir, backup_name)

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        tables = []
        row_counts = {}
        data = {}
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
        for table in table_names:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            data[table] = [dict(r) for r in rows]
            row_counts[table] = len(rows)
            tables.append(table)
    finally:
        conn.close()

    metadata = BackupMetadata(
        created_at=datetime.utcnow().isoformat() + "Z",
        base_currency=settings.base_currency,
        tables=tables,
        row_counts=row_counts,
    )
    payload = {"metadata": metadata.__dict__, "data": data}

    fd, tmp_path = tempfile.mkstemp(prefix=".finora_backup_", suffix=".tmp", dir=data_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, backup_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return {
        "filename": backup_name,
        "path": backup_path,
        "size": os.path.getsize(backup_path),
        "created_at": metadata.created_at,
        "tables": tables,
        "row_counts": row_counts,
    }


def validate_backup(path: str) -> dict:
    """Validate a backup file without modifying the database."""
    if not os.path.exists(path):
        raise BackupError("backup file does not exist")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise BackupError("backup file is not valid JSON") from exc

    if "metadata" not in data or "data" not in data:
        raise BackupError("backup is missing metadata or data sections")
    metadata = data["metadata"]
    tables = metadata.get("tables", [])
    payload_data = data["data"]
    for table in tables:
        if table not in payload_data:
            raise BackupError(f"backup is missing table: {table}")
        if not isinstance(payload_data[table], list):
            raise BackupError(f"backup table {table} is not a list")
    return metadata


def restore_backup(path: str) -> dict:
    """Restore the database from a validated backup.

    The current database is replaced only after validation, using an atomic
    temporary-file swap.
    """
    validate_backup(path)

    data_dir = _data_dir()
    db_path = _database_path()

    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    data = payload["data"]

    fd, tmp_db = tempfile.mkstemp(prefix=".finora_restore_", suffix=".db", dir=data_dir)
    os.close(fd)

    try:
        # Create the schema in the empty temp database before inserting data.
        tmp_url = "sqlite:///" + tmp_db.replace("\\", "/")
        sync_engine = create_engine(tmp_url)
        try:
            Base.metadata.create_all(sync_engine)
        finally:
            sync_engine.dispose()

        conn = sqlite3.connect(tmp_db)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            for table, rows in data.items():
                if not rows:
                    continue
                columns = list(rows[0].keys())
                placeholders = ", ".join(["?"] * len(columns))
                col_list = ", ".join(columns)
                conn.executemany(
                    f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                    [tuple(r.get(c) for c in columns) for r in rows],
                )
            conn.commit()
        finally:
            conn.close()

        if os.path.exists(db_path):
            os.replace(db_path, db_path + ".finora_bak")
        os.replace(tmp_db, db_path)
        bak = db_path + ".finora_bak"
        if os.path.exists(bak):
            os.remove(bak)
    except Exception:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)
        raise

    return {"restored_from": path, "tables": list(data.keys())}


__all__ = [
    "BackupError",
    "BackupMetadata",
    "list_backups",
    "create_backup",
    "validate_backup",
    "restore_backup",
    "_database_path",
]
