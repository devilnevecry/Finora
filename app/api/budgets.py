"""Budget API routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.budget_service import BudgetService
from app.services.currency import MoneyError, from_minor_units

router = APIRouter()


def _service(session: AsyncSession = Depends(get_session)) -> BudgetService:
    return BudgetService(session)


@router.get("")
async def list_budgets(
    service: BudgetService = Depends(_service),
    category_id: int | None = Query(None),
):
    budgets = await service.list(category_id=category_id)
    return JSONResponse(
        [
            {
                "id": b.id,
                "category_id": b.category_id,
                "period_start": b.period_start.isoformat(),
                "period_end": b.period_end.isoformat(),
                "amount_limit": float(from_minor_units(b.amount_limit)),
                "amount_limit_minor": b.amount_limit,
                "created_at": b.created_at.isoformat(),
            }
            for b in budgets
        ]
    )


@router.post("")
async def create_budget(
    category_id: str | None = Form(None),
    period_start: str = Form(...),
    period_end: str = Form(...),
    amount_limit: str = Form(...),
    service: BudgetService = Depends(_service),
):
    category_id = int(category_id) if category_id else None
    try:
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
    except ValueError:
        return JSONResponse({"error": "invalid period dates"}, status_code=400)
    try:
        budget = await service.create(
            category_id=category_id,
            period_start=start,
            period_end=end,
            amount_limit=amount_limit,
        )
    except MoneyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(
        {
            "id": budget.id,
            "category_id": budget.category_id,
            "amount_limit": float(from_minor_units(budget.amount_limit)),
        },
        status_code=201,
    )


@router.put("/{budget_id}")
async def update_budget(
    budget_id: int,
    amount_limit: str | None = Form(None),
    period_start: str | None = Form(None),
    period_end: str | None = Form(None),
    service: BudgetService = Depends(_service),
):
    fields = {}
    if amount_limit is not None:
        fields["amount_limit"] = amount_limit
    if period_start is not None:
        try:
            fields["period_start"] = date.fromisoformat(period_start)
        except ValueError:
            return JSONResponse({"error": "invalid period_start"}, status_code=400)
    if period_end is not None:
        try:
            fields["period_end"] = date.fromisoformat(period_end)
        except ValueError:
            return JSONResponse({"error": "invalid period_end"}, status_code=400)
    try:
        budget = await service.update(budget_id, **fields)
    except MoneyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if budget is None:
        return JSONResponse({"error": "budget not found"}, status_code=404)
    return JSONResponse({"id": budget.id})


@router.delete("/{budget_id}")
async def delete_budget(budget_id: int, service: BudgetService = Depends(_service)):
    ok = await service.delete(budget_id)
    if not ok:
        return JSONResponse({"error": "budget not found"}, status_code=404)
    return JSONResponse({"ok": True})


@router.get("/progress")
async def budget_progress(
    category_id: int | None = Query(None),
    period_start: str = Query(...),
    period_end: str = Query(...),
    service: BudgetService = Depends(_service),
):
    try:
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
    except ValueError:
        return JSONResponse({"error": "invalid period dates"}, status_code=400)
    result = await service.progress(category_id=category_id, period_start=start, period_end=end)
    return JSONResponse(result)
