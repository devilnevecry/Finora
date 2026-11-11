"""Transaction repository with filtering, sorting and pagination."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, transaction: Transaction) -> Transaction:
        self.session.add(transaction)
        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction

    async def get(self, transaction_id: int) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        account_id: int | None = None,
        category_id: int | None = None,
        type: str | None = None,
        tag: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        search: str | None = None,
        sort_by: str = "transaction_date",
        sort_dir: str = "desc",
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[Sequence[Transaction], int]:
        stmt = select(Transaction)
        count_stmt = select(func.count()).select_from(Transaction)

        conditions = []
        if account_id is not None:
            conditions.append(Transaction.account_id == account_id)
        if category_id is not None:
            conditions.append(Transaction.category_id == category_id)
        if type:
            conditions.append(Transaction.type == type)
        if date_from is not None:
            conditions.append(Transaction.transaction_date >= date_from)
        if date_to is not None:
            conditions.append(Transaction.transaction_date <= date_to)
        if tag:
            conditions.append(Transaction.tags.like(f"%{tag}%"))
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    Transaction.description.ilike(like),
                    Transaction.notes.ilike(like),
                )
            )

        if conditions:
            where = and_(*conditions)
            stmt = stmt.where(where)
            count_stmt = count_stmt.where(where)

        # total count
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # sorting
        order_col = getattr(Transaction, sort_by, Transaction.transaction_date)
        if sort_dir == "asc":
            stmt = stmt.order_by(asc(order_col))
        else:
            stmt = stmt.order_by(desc(order_col))

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all(), total

    async def update(self, transaction_id: int, **fields) -> Transaction | None:
        transaction = await self.get(transaction_id)
        if transaction is None:
            return None
        for key, value in fields.items():
            if hasattr(transaction, key):
                setattr(transaction, key, value)
        transaction.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction

    async def delete(self, transaction_id: int) -> bool:
        transaction = await self.get(transaction_id)
        if transaction is None:
            return False
        await self.session.delete(transaction)
        await self.session.flush()
        return True

    async def sum_by_type_and_account(self, account_id: int, type: str) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.account_id == account_id, Transaction.type == type
            )
        )
        return int(result.scalar_one() or 0)

    async def sum_by_type_and_category(self, category_id: int, type: str) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.category_id == category_id, Transaction.type == type
            )
        )
        return int(result.scalar_one() or 0)
