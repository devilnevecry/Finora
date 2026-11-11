"""Recurring transaction generation and duplicate prevention."""

from datetime import date

import pytest

from app.services.account_service import AccountService
from app.services.recurring_service import RecurringService


@pytest.mark.asyncio
async def test_recurring_generates_once_per_period(session):
    acc_svc = AccountService(session)
    rec_svc = RecurringService(session)
    acc = await acc_svc.create(name="Wallet", type="cash", opening_balance="1000.00")

    rule = await rec_svc.create(
        account_id=acc.id,
        amount="10.00",
        type="expense",
        description="Sub",
        interval="monthly",
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    assert rule.next_run_date == date(2026, 1, 1)

    created = await rec_svc.process_due(as_of=date(2026, 1, 1))
    assert len(created) == 1
    assert created[0].amount == 1000

    # Rule advanced to next month
    rule2 = await rec_svc.get(rule.id)
    assert rule2.next_run_date == date(2026, 2, 1)

    # Re-processing same date must not duplicate
    created2 = await rec_svc.process_due(as_of=date(2026, 1, 1))
    assert len(created2) == 0

    # Processing Feb 1 generates the second transaction
    created3 = await rec_svc.process_due(as_of=date(2026, 2, 1))
    assert len(created3) == 1


@pytest.mark.asyncio
async def test_recurring_pause_resume(session):
    acc_svc = AccountService(session)
    rec_svc = RecurringService(session)
    acc = await acc_svc.create(name="Wallet", type="cash", opening_balance="1000.00")

    rule = await rec_svc.create(
        account_id=acc.id,
        amount="5.00",
        type="expense",
        description="Pause",
        interval="daily",
        interval_count=1,
        start_date=date(2026, 1, 1),
    )
    paused = await rec_svc.pause(rule.id)
    assert paused.is_active is False

    resumed = await rec_svc.resume(rule.id)
    assert resumed.is_active is True
