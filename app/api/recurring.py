"""Recurring transaction API routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.currency import MoneyError
from app.services.recurring_service import RecurringService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_session)) -> RecurringService:
    return RecurringService(session)


@router.get("")
async def list_recurring(
    service: RecurringService = Depends(_service),
    include_inactive: bool = Query(False),
):
    rules = await service.list(include_inactive=include_inactive)
    return JSONResponse(
        [
            {
                "id": r.id,
                "account_id": r.account_id,
                "category_id": r.category_id,
                "amount": r.amount / 100,
                "amount_minor": r.amount,
                "type": r.type,
                "description": r.description,
                "notes": r.notes,
                "tags": r.tags,
                "interval": r.interval,
                "interval_count": r.interval_count,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat() if r.end_date else None,
                "next_run_date": r.next_run_date.isoformat(),
                "is_active": r.is_active,
                "last_run_date": r.last_run_date.isoformat() if r.last_run_date else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rules
        ]
    )


@router.post("")
async def create_recurring(
    account_id: int = Form(...),
    amount: str = Form(...),
    type: str = Form(...),
    description: str = Form(...),
    interval: str = Form(...),
    interval_count: int = Form(1),
    start_date: str = Form(...),
    end_date: str | None = Form(None),
    category_id: int | None = Form(None),
    notes: str | None = Form(None),
    tags: str | None = Form(None),
    service: RecurringService = Depends(_service),
):
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else None
        tags_list = [t.strip() for t in tags.split(",")] if tags else None
        rule = await service.create(
            account_id=account_id,
            amount=amount,
            type=type,
            description=description,
            interval=interval,
            interval_count=interval_count,
            start_date=start,
            end_date=end,
            category_id=category_id,
            notes=notes,
            tags=tags_list,
        )
    except (MoneyError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(
        {
            "id": rule.id,
            "next_run_date": rule.next_run_date.isoformat(),
        },
        status_code=201,
    )


@router.put("/{recurring_id}")
async def update_recurring(
    recurring_id: int,
    is_active: bool | None = Form(None),
    amount: str | None = Form(None),
    description: str | None = Form(None),
    interval: str | None = Form(None),
    interval_count: int | None = Form(None),
    end_date: str | None = Form(None),
    service: RecurringService = Depends(_service),
):
    fields = {}
    if is_active is not None:
        fields["is_active"] = is_active
    if amount is not None:
        from app.services.currency import to_minor_units

        fields["amount"] = to_minor_units(amount)
    if description is not None:
        fields["description"] = description
    if interval is not None:
        fields["interval"] = interval
    if interval_count is not None:
        fields["interval_count"] = interval_count
    if end_date is not None:
        try:
            fields["end_date"] = date.fromisoformat(end_date)
        except ValueError:
            return JSONResponse({"error": "invalid end_date"}, status_code=400)
    try:
        rule = await service.update(recurring_id, **fields)
    except MoneyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if rule is None:
        return JSONResponse({"error": "recurring rule not found"}, status_code=404)
    return JSONResponse({"id": rule.id})


@router.post("/{recurring_id}/pause")
async def pause_recurring(recurring_id: int, service: RecurringService = Depends(_service)):
    rule = await service.pause(recurring_id)
    if rule is None:
        return JSONResponse({"error": "recurring rule not found"}, status_code=404)
    return JSONResponse({"id": rule.id, "is_active": rule.is_active})


@router.post("/{recurring_id}/resume")
async def resume_recurring(recurring_id: int, service: RecurringService = Depends(_service)):
    rule = await service.resume(recurring_id)
    if rule is None:
        return JSONResponse({"error": "recurring rule not found"}, status_code=404)
    return JSONResponse({"id": rule.id, "is_active": rule.is_active})


@router.delete("/{recurring_id}")
async def delete_recurring(recurring_id: int, service: RecurringService = Depends(_service)):
    ok = await service.delete(recurring_id)
    if not ok:
        return JSONResponse({"error": "recurring rule not found"}, status_code=404)
    return JSONResponse({"ok": True})


@router.post("/process")
async def process_recurring(
    service: RecurringService = Depends(_service), as_of: str | None = Query(None)
):
    date_val = None
    if as_of:
        try:
            date_val = date.fromisoformat(as_of)
        except ValueError:
            return JSONResponse({"error": "invalid as_of date"}, status_code=400)
    created = await service.process_due(as_of=date_val)
    return JSONResponse(
        {
            "created": [
                {
                    "id": t.id,
                    "description": t.description,
                    "type": t.type,
                    "amount": t.amount / 100,
                    "date": t.transaction_date.isoformat(),
                }
                for t in created
            ],
            "count": len(created),
        }
    )
