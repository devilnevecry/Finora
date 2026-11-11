"""Reporting service — analytics queries based on actual database data.

All amounts are in the configured base currency. Transfers are excluded from
income/expense analytics to avoid double counting.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.currency import from_minor_units

settings = get_settings()


def _period_bounds(
    period: str, custom_from: date | None = None, custom_to: date | None = None
) -> tuple[datetime, datetime]:
    today = date.today()
    if period == "current_month":
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(today.year, today.month + 1, 1) - timedelta(days=1)
    elif period == "previous_month":
        if today.month == 1:
            start = date(today.year - 1, 12, 1)
            end = date(today.year, 1, 1) - timedelta(days=1)
        else:
            start = date(today.year, today.month - 1, 1)
            end = date(today.year, today.month, 1) - timedelta(days=1)
    elif period == "current_year":
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
    elif period == "custom":
        start = custom_from or today
        end = custom_to or today
    else:
        start = date(today.year, today.month, 1)
        end = today
    date_from = datetime(start.year, start.month, start.day)
    date_to = datetime(end.year, end.month, end.day, 23, 59, 59)
    return date_from, date_to


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.accounts = AccountRepository(session)
        self.transactions = TransactionRepository(session)

    async def dashboard_summary(
        self, period: str = "current_month", custom_from=None, custom_to=None
    ) -> dict:
        date_from, date_to = _period_bounds(period, custom_from, custom_to)

        accounts = await self.accounts.list_active()
        total_balance = sum((a.current_balance for a in accounts), 0)

        # Income and expense for the period (exclude transfers).
        income_tx, _ = await self.transactions.list(
            type="income", date_from=date_from, date_to=date_to, limit=10000, offset=0
        )
        expense_tx, _ = await self.transactions.list(
            type="expense", date_from=date_from, date_to=date_to, limit=10000, offset=0
        )
        total_income = sum((t.amount for t in income_tx), 0)
        total_expense = sum((t.amount for t in expense_tx), 0)
        net = total_income - total_expense

        # Spending by category.
        category_spending: dict[int, dict] = {}
        for t in expense_tx:
            cid = t.category_id
            if cid is None:
                continue
            entry = category_spending.setdefault(
                cid, {"category_id": cid, "amount_minor": 0, "count": 0}
            )
            entry["amount_minor"] += t.amount
            entry["count"] += 1

        # Enrich category names.
        category_list = []
        for cid, entry in category_spending.items():
            cat = await self._get_category(cid)
            category_list.append(
                {
                    "category_id": cid,
                    "category_name": cat.name if cat else "Unknown",
                    "category_type": cat.type if cat else "expense",
                    "color": cat.color if cat else None,
                    "icon": cat.icon if cat else None,
                    "amount": float(from_minor_units(entry["amount_minor"])),
                    "amount_minor": entry["amount_minor"],
                    "count": entry["count"],
                }
            )
        category_list.sort(key=lambda x: x["amount_minor"], reverse=True)

        # Monthly comparison: current vs previous period same length.
        length = (date_to.date() - date_from.date()).days + 1
        prev_to = date_from.date() - timedelta(days=1)
        prev_from = prev_to - timedelta(days=length - 1)
        prev_income_tx, _ = await self.transactions.list(
            type="income",
            date_from=datetime.combine(prev_from, datetime.min.time()),
            date_to=datetime.combine(prev_to, datetime.max.time()),
            limit=10000,
            offset=0,
        )
        prev_expense_tx, _ = await self.transactions.list(
            type="expense",
            date_from=datetime.combine(prev_from, datetime.min.time()),
            date_to=datetime.combine(prev_to, datetime.max.time()),
            limit=10000,
            offset=0,
        )
        prev_income = sum((t.amount for t in prev_income_tx), 0)
        prev_expense = sum((t.amount for t in prev_expense_tx), 0)

        # Recent transactions.
        recent, _ = await self.transactions.list(
            sort_by="transaction_date", sort_dir="desc", limit=10, offset=0
        )

        # Account overview.
        account_overview = []
        for a in accounts:
            account_overview.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "type": a.type,
                    "balance": float(from_minor_units(a.current_balance)),
                    "balance_minor": a.current_balance,
                    "is_active": a.is_active,
                }
            )

        return {
            "period": period,
            "date_from": date_from.date().isoformat(),
            "date_to": date_to.date().isoformat(),
            "total_balance": float(from_minor_units(total_balance)),
            "total_balance_minor": total_balance,
            "total_income": float(from_minor_units(total_income)),
            "total_income_minor": total_income,
            "total_expense": float(from_minor_units(total_expense)),
            "total_expense_minor": total_expense,
            "net_cash_flow": float(from_minor_units(net)),
            "net_cash_flow_minor": net,
            "previous_income": float(from_minor_units(prev_income)),
            "previous_expense": float(from_minor_units(prev_expense)),
            "spending_by_category": category_list,
            "recent_transactions": [
                {
                    "id": t.id,
                    "description": t.description,
                    "type": t.type,
                    "amount": float(from_minor_units(t.amount)),
                    "amount_minor": t.amount,
                    "date": t.transaction_date.isoformat(),
                    "account_id": t.account_id,
                    "category_id": t.category_id,
                }
                for t in recent
            ],
            "accounts": account_overview,
        }

    async def _get_category(self, category_id: int):
        from app.repositories.category_repository import CategoryRepository

        cats = CategoryRepository(self.session)
        return await cats.get(category_id)

    async def spending_by_category(
        self, period: str = "current_month", custom_from=None, custom_to=None
    ) -> list[dict]:
        summary = await self.dashboard_summary(period, custom_from, custom_to)
        return summary["spending_by_category"]

    async def income_vs_expense(
        self, period: str = "current_month", custom_from=None, custom_to=None
    ) -> dict:
        summary = await self.dashboard_summary(period, custom_from, custom_to)
        return {
            "income": summary["total_income_minor"],
            "expense": summary["total_expense_minor"],
            "net": summary["net_cash_flow_minor"],
        }
