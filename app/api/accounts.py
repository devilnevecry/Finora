"""Account API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.account_service import AccountService
from app.services.currency import MoneyError, format_amount, from_minor_units

router = APIRouter()


def _service(session: AsyncSession = Depends(get_session)) -> AccountService:
    return AccountService(session)


@router.get("")
async def list_accounts(
    service: AccountService = Depends(_service), include_archived: bool = False
):
    accounts = await service.list(include_archived=include_archived)
    return JSONResponse(
        [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "currency": a.currency,
                "opening_balance": float(from_minor_units(a.opening_balance)),
                "opening_balance_minor": a.opening_balance,
                "current_balance": float(from_minor_units(a.current_balance)),
                "current_balance_minor": a.current_balance,
                "current_balance_formatted": format_amount(a.current_balance),
                "description": a.description,
                "created_at": a.created_at.isoformat(),
                "is_active": a.is_active,
                "is_archived": a.is_archived,
            }
            for a in accounts
        ]
    )


@router.post("")
async def create_account(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    currency: str = Form(None),
    opening_balance: str = Form("0"),
    description: str = Form(""),
    service: AccountService = Depends(_service),
):
    try:
        account = await service.create(
            name=name,
            type=type,
            currency=currency or "",
            opening_balance=opening_balance,
            description=description or None,
        )
    except MoneyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(
        {
            "id": account.id,
            "name": account.name,
            "current_balance": float(from_minor_units(account.current_balance)),
            "current_balance_formatted": format_amount(account.current_balance),
        },
        status_code=201,
    )


@router.get("/{account_id}")
async def get_account(account_id: int, service: AccountService = Depends(_service)):
    account = await service.get(account_id)
    if account is None:
        return JSONResponse({"error": "account not found"}, status_code=404)
    return JSONResponse(
        {
            "id": account.id,
            "name": account.name,
            "type": account.type,
            "currency": account.currency,
            "opening_balance": float(from_minor_units(account.opening_balance)),
            "current_balance": float(from_minor_units(account.current_balance)),
            "current_balance_minor": account.current_balance,
            "description": account.description,
            "created_at": account.created_at.isoformat(),
            "is_active": account.is_active,
            "is_archived": account.is_archived,
        }
    )


@router.put("/{account_id}")
async def update_account(
    account_id: int,
    name: str | None = Form(None),
    type: str | None = Form(None),
    currency: str | None = Form(None),
    description: str | None = Form(None),
    is_active: bool | None = Form(None),
    is_archived: bool | None = Form(None),
    service: AccountService = Depends(_service),
):
    try:
        account = await service.update(
            account_id,
            name=name,
            type=type,
            currency=currency,
            description=description,
            is_active=is_active,
            is_archived=is_archived,
        )
    except MoneyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if account is None:
        return JSONResponse({"error": "account not found"}, status_code=404)
    return JSONResponse({"id": account.id, "name": account.name})


@router.delete("/{account_id}")
async def delete_account(account_id: int, service: AccountService = Depends(_service)):
    ok = await service.delete(account_id)
    if not ok:
        return JSONResponse({"error": "account not found"}, status_code=404)
    return JSONResponse({"ok": True})


@router.post("/{account_id}/archive")
async def archive_account(account_id: int, service: AccountService = Depends(_service)):
    account = await service.archive(account_id)
    if account is None:
        return JSONResponse({"error": "account not found"}, status_code=404)
    return JSONResponse({"id": account.id, "is_archived": account.is_archived})
