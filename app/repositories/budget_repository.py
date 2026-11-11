"""Budget repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget


class BudgetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, budget: Budget) -> Budget:
        self.session.add(budget)
        await self.session.flush()
        await self.session.refresh(budget)
        return budget

    async def get(self, budget_id: int) -> Budget | None:
        result = await self.session.execute(select(Budget).where(Budget.id == budget_id))
        return result.scalar_one_or_none()

    async def list(self, category_id: int | None = None) -> Sequence[Budget]:
        stmt = select(Budget).order_by(Budget.period_start.desc())
        if category_id is not None:
            stmt = stmt.where(Budget.category_id == category_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_period(self, period_start: date, period_end: date) -> Sequence[Budget]:
        stmt = select(Budget).where(
            Budget.period_start >= period_start, Budget.period_end <= period_end
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, budget_id: int, **fields) -> Budget | None:
        budget = await self.get(budget_id)
        if budget is None:
            return None
        for key, value in fields.items():
            if hasattr(budget, key):
                setattr(budget, key, value)
        await self.session.flush()
        await self.session.refresh(budget)
        return budget

    async def delete(self, budget_id: int) -> bool:
        budget = await self.get(budget_id)
        if budget is None:
            return False
        await self.session.delete(budget)
        await self.session.flush()
        return True
