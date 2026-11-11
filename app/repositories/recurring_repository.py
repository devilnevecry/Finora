"""Recurring transaction repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recurring import RecurringTransaction


class RecurringRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, recurring: RecurringTransaction) -> RecurringTransaction:
        self.session.add(recurring)
        await self.session.flush()
        await self.session.refresh(recurring)
        return recurring

    async def get(self, recurring_id: int) -> RecurringTransaction | None:
        result = await self.session.execute(
            select(RecurringTransaction).where(RecurringTransaction.id == recurring_id)
        )
        return result.scalar_one_or_none()

    async def list(self, include_inactive: bool = False) -> Sequence[RecurringTransaction]:
        stmt = select(RecurringTransaction).order_by(RecurringTransaction.next_run_date)
        if not include_inactive:
            stmt = stmt.where(RecurringTransaction.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_due(self, as_of: date) -> Sequence[RecurringTransaction]:
        result = await self.session.execute(
            select(RecurringTransaction).where(
                RecurringTransaction.is_active == True,  # noqa: E712
                RecurringTransaction.next_run_date <= as_of,
            )
        )
        return result.scalars().all()

    async def update(self, recurring_id: int, **fields) -> RecurringTransaction | None:
        recurring = await self.get(recurring_id)
        if recurring is None:
            return None
        for key, value in fields.items():
            if hasattr(recurring, key):
                setattr(recurring, key, value)
        await self.session.flush()
        await self.session.refresh(recurring)
        return recurring

    async def delete(self, recurring_id: int) -> bool:
        recurring = await self.get(recurring_id)
        if recurring is None:
            return False
        await self.session.delete(recurring)
        await self.session.flush()
        return True

    async def pause(self, recurring_id: int) -> RecurringTransaction | None:
        return await self.update(recurring_id, is_active=False)
