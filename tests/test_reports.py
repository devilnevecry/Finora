"""Reporting / analytics tests based on actual database queries."""

from datetime import date, datetime

import pytest

from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService


async def _reports_fixture(session):
    acc_svc = AccountService(session)
    cat_svc = CategoryService(session)
    tx_svc = TransactionService(session)
    rep_svc = ReportService(session)
    acc = await acc_svc.create(name="Wallet", type="cash", opening_balance="1000.00")
    inc = await cat_svc.create(name="Salary", type="income")
    exp = await cat_svc.create(name="Food", type="expense")
    today = date.today()
    await tx_svc.create_income(
        account_id=acc.id,
        amount="500.00",
        category_id=inc.id,
        transaction_date=datetime(today.year, today.month, 5),
        description="salary",
    )
    await tx_svc.create_expense(
        account_id=acc.id,
        amount="120.00",
        category_id=exp.id,
        transaction_date=datetime(today.year, today.month, 6),
        description="food",
    )
    return rep_svc, acc, tx_svc


@pytest.mark.asyncio
async def test_dashboard_excludes_transfers(session):
    rep_svc, acc, tx_svc = await _reports_fixture(session)
    dst = await AccountService(session).create(name="Dest", type="savings", opening_balance="0")
    today = date.today()
    await tx_svc.create_transfer(
        source_account_id=acc.id,
        destination_account_id=dst.id,
        amount="50.00",
        transaction_date=datetime(today.year, today.month, 7),
        description="transfer",
    )
    summary = await rep_svc.dashboard_summary(period="current_month")
    assert summary["total_income_minor"] == 50000
    assert summary["total_expense_minor"] == 12000
    assert summary["net_cash_flow_minor"] == 38000
