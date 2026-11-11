"""CSV import/export API routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.transaction_repository import TransactionRepository
from app.services.export_service import ExportService
from app.services.import_service import ImportService

router = APIRouter()

import_service = ImportService()


def _repo(session: AsyncSession = Depends(get_session)) -> TransactionRepository:
    return TransactionRepository(session)


@router.post("/preview")
async def preview_import(
    file: UploadFile = File(...),
    mapping: str = Form("{}"),
    repo: TransactionRepository = Depends(_repo),
):
    import json

    try:
        mapping_dict = json.loads(mapping or "{}")
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid mapping JSON"}, status_code=400)

    content = await file.read()
    try:
        import_service.validate_file(file.filename or "upload.csv", content)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    try:
        columns, rows = import_service.parse(content)
    except Exception as exc:
        return JSONResponse({"error": f"failed to parse CSV: {exc}"}, status_code=400)

    # Build existing keys for duplicate detection.
    all_tx, _ = await repo.list(limit=100000, offset=0)
    existing_keys = ImportService.build_existing_keys(all_tx)

    preview = import_service.preview(columns, rows, mapping_dict, existing_keys)
    return JSONResponse(
        {
            "columns": preview.columns,
            "total": preview.total,
            "valid_count": preview.valid_count,
            "error_count": preview.error_count,
            "duplicate_count": preview.duplicate_count,
            "rows": [
                {
                    "line_number": r.line_number,
                    "mapped": r.mapped,
                    "errors": r.errors,
                    "warnings": r.warnings,
                    "valid": r.valid,
                }
                for r in preview.rows
            ],
        }
    )


@router.post("/confirm")
async def confirm_import(
    rows_json: str = Form(...),
    repo: TransactionRepository = Depends(_repo),
):
    import json

    from app.services.transaction_service import TransactionService

    try:
        rows = json.loads(rows_json or "[]")
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid rows JSON"}, status_code=400)

    service = TransactionService(repo.session)
    imported = 0
    skipped = 0
    errors = []

    for row in rows:
        if not row.get("valid"):
            skipped += 1
            continue
        mapped = row.get("mapped", {})
        try:
            await service.create_expense(
                account_id=int(mapped["account_id"]) if mapped.get("account_id") else 0,
                amount=mapped.get("amount_minor", 0) / 100,
                transaction_date=mapped["transaction_date_parsed"],
                description=mapped.get("description", ""),
                category_id=int(mapped["category_id"]) if mapped.get("category_id") else None,
                notes=mapped.get("notes") or None,
                tags=[t.strip() for t in mapped.get("tags", "").split(",")]
                if mapped.get("tags")
                else None,
            )
            imported += 1
        except Exception as exc:
            errors.append(str(exc))
            skipped += 1

    return JSONResponse(
        {
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10],
        }
    )


@router.get("/export")
async def export(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    account_id: int | None = Query(None),
    type: str | None = Query(None),
    category_id: int | None = Query(None),
    repo: TransactionRepository = Depends(_repo),
):
    df = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
    dt_ = datetime.strptime(date_to, "%Y-%m-%d") if date_to else None

    export_service = ExportService(repo)
    filename, payload, content_type = await export_service.export(
        date_from=df, date_to=dt_, account_id=account_id, type=type, category_id=category_id
    )
    return StreamingResponse(
        iter([payload]),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
