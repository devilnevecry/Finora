"""Budget service."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget
from app.repositories.budget_repository import BudgetRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.currency import MoneyError, from_minor_units, to_minor_units


class BudgetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.budgets = BudgetRepository(session)
        self.transactions = TransactionRepository(session)

    async def create(
        self,
        *,
        category_id: int | None,
        period_start: date,
        period_end: date,
        amount_limit,
    ) -> Budget:
        limit_minor = to_minor_units(amount_limit)
        if limit_minor < 0:
            raise MoneyError("budget limit must not be negative")
        if period_end < period_start:
            raise MoneyError("period end must be on or after period start")
        budget = Budget(
            category_id=category_id,
            period_start=period_start,
            period_end=period_end,
            amount_limit=limit_minor,
            created_at=datetime.utcnow(),
        )
        return await self.budgets.add(budget)

    async def list(self, category_id: int | None = None):
        return await self.budgets.list(category_id=category_id)

    async def get(self, budget_id: int) -> Budget | None:
        return await self.budgets.get(budget_id)

    async def update(self, budget_id: int, **fields) -> Budget | None:
        if "amount_limit" in fields:
            fields["amount_limit"] = to_minor_units(fields["amount_limit"])
            if fields["amount_limit"] < 0:
                raise MoneyError("budget limit must not be negative")
        return await self.budgets.update(budget_id, **fields)

    async def delete(self, budget_id: int) -> bool:
        return await self.budgets.delete(budget_id)

    async def progress(self, category_id: int | None, period_start: date, period_end: date) -> dict:
        """Compute budget progress for a period.

        Actual spending is the sum of expense transactions (excluding transfers)
        in the period, optionally filtered by category.
        """
        # Convert date range to datetimes covering the whole days.
        from datetime import datetime as _dt

        date_from = _dt(period_start.year, period_start.month, period_start.day)
        date_to = _dt(period_end.year, period_end.month, period_end.day, 23, 59, 59)

        # Fetch budgets for the period to know the limit.
        budgets = await self.budgets.list_for_period(period_start, period_end)
        relevant = (
            [b for b in budgets if b.category_id == category_id]
            if category_id is not None
            else [b for b in budgets if b.category_id is None]
        )
        limit_minor = sum((b.amount_limit for b in relevant), 0)

        # Actual expense sum (exclude transfers).
        transactions, _ = await self.transactions.list(
            category_id=category_id,
            type="expense",
            date_from=date_from,
            date_to=date_to,
            limit=10000,
            offset=0,
        )
        actual_minor = sum((t.amount for t in transactions), 0)

        remaining = limit_minor - actual_minor
        percent = (actual_minor / limit_minor * 100) if limit_minor > 0 else 0.0
        return {
            "category_id": category_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "limit": float(from_minor_units(limit_minor)),
            "limit_minor": limit_minor,
            "actual": float(from_minor_units(actual_minor)),
            "actual_minor": actual_minor,
            "remaining": float(from_minor_units(remaining)),
            "remaining_minor": remaining,
            "percent": round(percent, 2),
            "overspent": actual_minor > limit_minor,
        }
