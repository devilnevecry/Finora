"""Budget progress calculations."""

from datetime import date, datetime

import pytest

from app.services.account_service import AccountService
from app.services.budget_service import BudgetService
from app.services.category_service import CategoryService
from app.services.transaction_service import TransactionService


async def _budget_fixture(session):
    acc_svc = AccountService(session)
    cat_svc = CategoryService(session)
    tx_svc = TransactionService(session)
    bud_svc = BudgetService(session)
    acc = await acc_svc.create(name="Wallet", type="cash", opening_balance="2000.00")
    cat = await cat_svc.create(name="Food", type="expense")
    return acc_svc, cat_svc, tx_svc, bud_svc, acc, cat


@pytest.mark.asyncio
async def test_budget_create_and_progress(session):
    acc_svc, cat_svc, tx_svc, bud_svc, acc, cat = await _budget_fixture(session)
    # create expense transactions in current month
    today = date.today()
    await tx_svc.create_expense(
        account_id=acc.id,
        amount="100.00",
        category_id=cat.id,
        transaction_date=datetime(today.year, today.month, 10),
        description="x",
    )
    await tx_svc.create_expense(
        account_id=acc.id,
        amount="50.00",
        category_id=cat.id,
        transaction_date=datetime(today.year, today.month, 15),
        description="y",
    )
    # transfer must NOT count toward budget
    dst = await acc_svc.create(name="Dest", type="savings", opening_balance="0")
    await tx_svc.create_transfer(
        source_account_id=acc.id,
        destination_account_id=dst.id,
        amount="50.00",
        transaction_date=datetime(today.year, today.month, 12),
        description="t",
    )

    _bud = await bud_svc.create(
        category_id=cat.id,
        period_start=date(today.year, today.month, 1),
        period_end=date(today.year, today.month, 28),
        amount_limit="200.00",
    )
    prog = await bud_svc.progress(
        cat.id, date(today.year, today.month, 1), date(today.year, today.month, 28)
    )
    assert prog["actual_minor"] == 15000  # 150.00, transfer excluded
    assert prog["limit_minor"] == 20000
    assert prog["remaining_minor"] == 5000
    assert prog["overspent"] is False

    # overspend
    await tx_svc.create_expense(
        account_id=acc.id,
        amount="100.00",
        category_id=cat.id,
        transaction_date=datetime(today.year, today.month, 20),
        description="z",
    )
    prog2 = await bud_svc.progress(
        cat.id, date(today.year, today.month, 1), date(today.year, today.month, 28)
    )
    assert prog2["overspent"] is True
