"""Reports / analytics API routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.report_service import ReportService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_session)) -> ReportService:
    return ReportService(session)


@router.get("/dashboard")
async def dashboard(
    service: ReportService = Depends(_service),
    period: str = Query("current_month"),
    custom_from: str | None = Query(None),
    custom_to: str | None = Query(None),
):
    cf = date.fromisoformat(custom_from) if custom_from else None
    ct = date.fromisoformat(custom_to) if custom_to else None
    result = await service.dashboard_summary(period=period, custom_from=cf, custom_to=ct)
    return JSONResponse(result)


@router.get("/spending-by-category")
async def spending_by_category(
    service: ReportService = Depends(_service),
    period: str = Query("current_month"),
    custom_from: str | None = Query(None),
    custom_to: str | None = Query(None),
):
    cf = date.fromisoformat(custom_from) if custom_from else None
    ct = date.fromisoformat(custom_to) if custom_to else None
    result = await service.spending_by_category(period=period, custom_from=cf, custom_to=ct)
    return JSONResponse(result)


@router.get("/income-vs-expense")
async def income_vs_expense(
    service: ReportService = Depends(_service),
    period: str = Query("current_month"),
    custom_from: str | None = Query(None),
    custom_to: str | None = Query(None),
):
    cf = date.fromisoformat(custom_from) if custom_from else None
    ct = date.fromisoformat(custom_to) if custom_to else None
    result = await service.income_vs_expense(period=period, custom_from=cf, custom_to=ct)
    return JSONResponse(result)
