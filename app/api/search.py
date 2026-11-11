"""Search API route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.transaction_service import TransactionService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_session)) -> TransactionService:
    return TransactionService(session)


@router.get("")
async def search(
    service: TransactionService = Depends(_service),
    q: str = Query(...),
    account_id: int | None = Query(None),
    category_id: int | None = Query(None),
    type: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(25),
    offset: int = Query(0),
):
    from datetime import datetime

    df = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
    dt_ = datetime.strptime(date_to, "%Y-%m-%d") if date_to else None
    rows, total = await service.list(
        account_id=account_id,
        category_id=category_id,
        type=type,
        date_from=df,
        date_to=dt_,
        search=q,
        sort_by="transaction_date",
        sort_dir="desc",
        limit=min(limit, 100),
        offset=offset,
    )
    return JSONResponse(
        {
            "query": q,
            "items": [
                {
                    "id": t.id,
                    "description": t.description,
                    "notes": t.notes,
                    "type": t.type,
                    "amount": t.amount / 100,
                    "date": t.transaction_date.isoformat(),
                    "account_id": t.account_id,
                    "category_id": t.category_id,
                }
                for t in rows
            ],
            "total": total,
        }
    )
