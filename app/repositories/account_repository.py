"""Account repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.transaction import Transaction


class AccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, account: Account) -> Account:
        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def get(self, account_id: int) -> Account | None:
        result = await self.session.execute(select(Account).where(Account.id == account_id))
        return result.scalar_one_or_none()

    async def list(self, include_archived: bool = False) -> Sequence[Account]:
        stmt = select(Account).order_by(Account.name)
        if not include_archived:
            stmt = stmt.where(Account.is_archived == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_active(self) -> Sequence[Account]:
        result = await self.session.execute(
            select(Account).where(Account.is_active == True).order_by(Account.name)  # noqa: E712
        )
        return result.scalars().all()

    async def update(self, account_id: int, **fields) -> Account | None:
        account = await self.get(account_id)
        if account is None:
            return None
        for key, value in fields.items():
            if hasattr(account, key):
                setattr(account, key, value)
        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def delete(self, account_id: int) -> bool:
        account = await self.get(account_id)
        if account is None:
            return False
        await self.session.delete(account)
        await self.session.flush()
        return True

    async def archive(self, account_id: int) -> Account | None:
        return await self.update(account_id, is_archived=True, is_active=False)

    async def recalculate_balance(self, account_id: int) -> int:
        """Derive current balance from transactions (source of truth for verification)."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.account_id == account_id
            )
        )
        total = result.scalar_one() or 0
        return int(total)
