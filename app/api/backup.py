"""Backup and restore API routes."""

from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import FileResponse, JSONResponse

from app.services.backup_service import (
    BackupError,
    create_backup,
    list_backups,
    restore_backup,
    validate_backup,
)

router = APIRouter()


@router.get("")
async def list_backups_route():
    backups = list_backups()
    return JSONResponse({"backups": backups})


@router.post("/create")
async def create_backup_route(filename: str | None = Form(None)):
    try:
        result = create_backup(filename=filename)
    except BackupError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(result)


@router.get("/download/{filename}")
async def download_backup(filename: str):
    import os

    from app.config import get_settings

    settings = get_settings()
    path = os.path.join(settings.data_dir, filename)
    if not os.path.exists(path):
        return JSONResponse({"error": "backup not found"}, status_code=404)
    return FileResponse(path, media_type="application/json", filename=filename)


@router.post("/validate")
async def validate_backup_route(filename: str = Form(...)):
    import os

    from app.config import get_settings

    settings = get_settings()
    path = os.path.join(settings.data_dir, filename)
    try:
        metadata = validate_backup(path)
    except BackupError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"valid": True, "metadata": metadata})


@router.post("/restore")
async def restore_backup_route(filename: str = Form(...), confirm: str = Form("no")):
    import os

    from app.config import get_settings

    settings = get_settings()
    path = os.path.join(settings.data_dir, filename)
    if confirm.lower() != "yes":
        return JSONResponse({"error": "restore requires confirm=yes"}, status_code=400)
    try:
        result = restore_backup(path)
    except BackupError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(result)
