"""Transaction API routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.currency import MoneyError, format_amount, from_minor_units
from app.services.transaction_service import TransactionService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_session)) -> TransactionService:
    return TransactionService(session)


def _tx_to_dict(tx) -> dict:
    return {
        "id": tx.id,
        "account_id": tx.account_id,
        "category_id": tx.category_id,
        "amount": float(from_minor_units(tx.amount)),
        "amount_minor": tx.amount,
        "amount_formatted": format_amount(tx.amount),
        "transaction_date": tx.transaction_date.isoformat(),
        "type": tx.type,
        "description": tx.description,
        "notes": tx.notes,
        "tags": tx.tags,
        "created_at": tx.created_at.isoformat(),
        "updated_at": tx.updated_at.isoformat(),
        "linked_transaction_id": tx.linked_transaction_id,
    }


@router.get("")
async def list_transactions(
    service: TransactionService = Depends(_service),
    account_id: int | None = Query(None),
    category_id: int | None = Query(None),
    type: str | None = Query(None),
    tag: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("transaction_date"),
    sort_dir: str = Query("desc"),
    limit: int = Query(25),
    offset: int = Query(0),
):
    df = _parse_date(date_from) if date_from else None
    dt_ = _parse_date(date_to) if date_to else None
    if date_from and df is None:
        return JSONResponse({"error": "invalid date_from"}, status_code=400)
    if date_to and dt_ is None:
        return JSONResponse({"error": "invalid date_to"}, status_code=400)
    rows, total = await service.list(
        account_id=account_id,
        category_id=category_id,
        type=type,
        tag=tag,
        date_from=df,
        date_to=dt_,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=min(limit, 100),
        offset=offset,
    )
    return JSONResponse(
        {
            "items": [_tx_to_dict(t) for t in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("/income")
async def create_income(
    account_id: int = Form(...),
    amount: str = Form(...),
    transaction_date: str = Form(...),
    description: str = Form(...),
    category_id: str | None = Form(None),
    notes: str | None = Form(None),
    tags: str | None = Form(None),
    service: TransactionService = Depends(_service),
):
    category_id = int(category_id) if category_id else None
    try:
        tx = await service.create_income(
            account_id=account_id,
            amount=amount,
            transaction_date=_parse_required_date(transaction_date),
            description=description,
            category_id=category_id,
            notes=notes,
            tags=[t.strip() for t in tags.split(",")] if tags else None,
        )
    except MoneyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(_tx_to_dict(tx), status_code=201)


@router.post("/expense")
async def create_expense(
    account_id: int = Form(...),
    amount: str = Form(...),
    transaction_date: str = Form(...),
    description: str = Form(...),
    category_id: str | None = Form(None),
    notes: str | None = Form(None),
    tags: str | None = Form(None),
    service: TransactionService = Depends(_service),
):
    category_id = int(category_id) if category_id else None
    try:
        tx = await service.create_expense(
            account_id=account_id,
            amount=amount,
            transaction_date=_parse_required_date(transaction_date),
            description=description,
            category_id=category_id,
            notes=notes,
            tags=[t.strip() for t in tags.split(",")] if tags else None,
        )
    except MoneyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(_tx_to_dict(tx), status_code=201)


@router.post("/transfer")
async def create_transfer(
    source_account_id: int = Form(...),
    destination_account_id: int = Form(...),
    amount: str = Form(...),
    transaction_date: str = Form(...),
    description: str = Form(...),
    notes: str | None = Form(None),
    tags: str | None = Form(None),
    service: TransactionService = Depends(_service),
):
    try:
        expense, income = await service.create_transfer(
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            amount=amount,
            transaction_date=_parse_required_date(transaction_date),
            description=description,
            notes=notes,
            tags=[t.strip() for t in tags.split(",")] if tags else None,
        )
    except MoneyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(
        {
            "expense": _tx_to_dict(expense),
            "income": _tx_to_dict(income),
        },
        status_code=201,
    )


@router.get("/{transaction_id}")
async def get_transaction(transaction_id: int, service: TransactionService = Depends(_service)):
    tx = await service.get(transaction_id)
    if tx is None:
        return JSONResponse({"error": "transaction not found"}, status_code=404)
    return JSONResponse(_tx_to_dict(tx))


@router.put("/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    description: str | None = Form(None),
    notes: str | None = Form(None),
    amount: str | None = Form(None),
    transaction_date: str | None = Form(None),
    category_id: str | None = Form(None),
    tags: str | None = Form(None),
    service: TransactionService = Depends(_service),
):
    category_id = int(category_id) if category_id else None
    fields = {}
    if description is not None:
        fields["description"] = description
    if notes is not None:
        fields["notes"] = notes
    if amount is not None:
        fields["amount"] = amount
    if transaction_date is not None:
        fields["transaction_date"] = _parse_required_date(transaction_date)
    if category_id is not None:
        fields["category_id"] = category_id
    if tags is not None:
        fields["tags"] = tags
    try:
        tx = await service.update(transaction_id, **fields)
    except (MoneyError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if tx is None:
        return JSONResponse({"error": "transaction not found"}, status_code=404)
    return JSONResponse(_tx_to_dict(tx))


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: int, service: TransactionService = Depends(_service)):
    ok = await service.delete(transaction_id)
    if not ok:
        return JSONResponse({"error": "transaction not found"}, status_code=404)
    return JSONResponse({"ok": True})


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_required_date(value: str) -> datetime:
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError("invalid transaction date")
    return parsed
