"""Recurring transaction service.

Generates transactions from recurring rules on their scheduled dates with
duplicate prevention. After a transaction is generated the rule's
next_run_date is advanced so the same transaction is never created twice,
including across application restarts.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recurring import RecurringTransaction
from app.models.transaction import Transaction
from app.repositories.account_repository import AccountRepository
from app.repositories.recurring_repository import RecurringRepository
from app.services.currency import MoneyError, to_minor_units
from app.services.transaction_service import TransactionService


def _add_interval(base: date, interval: str, count: int) -> date:
    if interval == "daily":
        return base + timedelta(days=count)
    if interval == "weekly":
        return base + timedelta(weeks=count)
    if interval == "monthly":
        return _add_months(base, count)
    if interval == "yearly":
        return _add_months(base, count * 12)
    if interval == "custom":
        return base + timedelta(days=count)
    raise MoneyError(f"unknown interval: {interval}")


def _add_months(base: date, months: int) -> date:
    year = base.year + (base.month - 1 + months) // 12
    month = (base.month - 1 + months) % 12 + 1
    day = min(base.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - date(year, month, 1)).days


class RecurringService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.recurring = RecurringRepository(session)
        self.accounts = AccountRepository(session)
        self.transaction_service = TransactionService(session)

    async def create(
        self,
        *,
        account_id: int,
        amount,
        type: str,
        description: str,
        interval: str,
        interval_count: int,
        start_date: date,
        end_date: date | None = None,
        category_id: int | None = None,
        notes: str | None = None,
        tags: Sequence[str] | None = None,
    ) -> RecurringTransaction:
        minor = to_minor_units(amount)
        if minor <= 0:
            raise MoneyError("amount must be positive")
        if interval_count < 1:
            raise MoneyError("interval count must be at least 1")
        if end_date is not None and end_date < start_date:
            raise MoneyError("end date must be on or after start date")
        if type not in ("income", "expense", "transfer"):
            raise MoneyError(f"invalid type: {type}")
        if interval not in ("daily", "weekly", "monthly", "yearly", "custom"):
            raise MoneyError(f"invalid interval: {interval}")

        account = await self.accounts.get(account_id)
        if account is None:
            raise MoneyError(f"account {account_id} does not exist")

        recurring = RecurringTransaction(
            account_id=account_id,
            category_id=category_id,
            amount=minor,
            type=type,
            description=description,
            notes=notes,
            tags=",".join(t for t in (tags or []) if t),
            interval=interval,
            interval_count=interval_count,
            start_date=start_date,
            end_date=end_date,
            next_run_date=start_date,
            is_active=True,
            last_run_date=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        return await self.recurring.add(recurring)

    async def list(self, include_inactive: bool = False):
        return await self.recurring.list(include_inactive=include_inactive)

    async def get(self, recurring_id: int) -> RecurringTransaction | None:
        return await self.recurring.get(recurring_id)

    async def update(self, recurring_id: int, **fields) -> RecurringTransaction | None:
        return await self.recurring.update(recurring_id, **fields)

    async def pause(self, recurring_id: int) -> RecurringTransaction | None:
        return await self.recurring.pause(recurring_id)

    async def resume(self, recurring_id: int) -> RecurringTransaction | None:
        recurring = await self.recurring.get(recurring_id)
        if recurring is None:
            return None
        recurring.next_run_date = max(recurring.next_run_date, date.today())
        return await self.recurring.update(
            recurring_id, is_active=True, next_run_date=recurring.next_run_date
        )

    async def delete(self, recurring_id: int) -> bool:
        return await self.recurring.delete(recurring_id)

    async def process_due(self, as_of: date | None = None) -> list[Transaction]:
        """Generate transactions for all due recurring rules.

        Returns the list of newly created transactions. Duplicate prevention is
        ensured by advancing next_run_date and recording last_run_date within
        the same database transaction.
        """
        if as_of is None:
            as_of = date.today()
        due = await self.recurring.list_due(as_of)
        created: list = []
        for rule in due:
            # Generate the transaction.
            if rule.type == "transfer":
                raise MoneyError("recurring transfers are not supported in this version")
            if rule.type == "income":
                tx = await self.transaction_service.create_income(
                    account_id=rule.account_id,
                    amount_minor=rule.amount,
                    transaction_date=datetime.combine(rule.next_run_date, datetime.min.time()),
                    description=rule.description,
                    category_id=rule.category_id,
                    notes=rule.notes,
                    tags=[t for t in (rule.tags or "").split(",") if t],
                )
            else:
                tx = await self.transaction_service.create_expense(
                    account_id=rule.account_id,
                    amount_minor=rule.amount,
                    transaction_date=datetime.combine(rule.next_run_date, datetime.min.time()),
                    description=rule.description,
                    category_id=rule.category_id,
                    notes=rule.notes,
                    tags=[t for t in (rule.tags or "").split(",") if t],
                )
            created.append(tx)

            # Advance the schedule and mark last run.
            next_date = _add_interval(rule.next_run_date, rule.interval, rule.interval_count)
            if rule.end_date is not None and next_date > rule.end_date:
                await self.recurring.update(rule.id, is_active=False, last_run_date=as_of)
            else:
                await self.recurring.update(
                    rule.id,
                    next_run_date=next_date,
                    last_run_date=as_of,
                )
        return created
