"""Account CRUD and balance tests."""

import pytest

from app.services.account_service import AccountService
from app.services.currency import MoneyError


@pytest.mark.asyncio
async def test_create_account(session):
    svc = AccountService(session)
    acc = await svc.create(name="Cash", type="cash", currency="USD", opening_balance="100.00")
    assert acc.id is not None
    assert acc.current_balance == 10000
    assert acc.opening_balance == 10000


@pytest.mark.asyncio
async def test_create_account_negative_opening_rejected(session):
    svc = AccountService(session)
    with pytest.raises(MoneyError):
        await svc.create(name="Bad", type="cash", opening_balance="-10")


@pytest.mark.asyncio
async def test_list_and_get_account(session):
    svc = AccountService(session)
    a1 = await svc.create(name="A", type="bank", opening_balance="0")
    _a2 = await svc.create(name="B", type="savings", opening_balance="0")
    accounts = await svc.list()
    assert len(accounts) == 2
    got = await svc.get(a1.id)
    assert got.name == "A"


@pytest.mark.asyncio
async def test_archive_account(session):
    svc = AccountService(session)
    acc = await svc.create(name="ArchiveMe", type="cash", opening_balance="0")
    await svc.archive(acc.id)
    active = await svc.list()
    archived = await svc.list(include_archived=True)
    assert len(active) == 0
    assert len(archived) == 1
    assert archived[0].is_archived is True


@pytest.mark.asyncio
async def test_balance_derivable_from_transactions(session):
    from app.repositories.account_repository import AccountRepository

    svc = AccountService(session)
    acc = await svc.create(name="Acc", type="cash", opening_balance="100.00")
    repo = AccountRepository(session)
    # derive from transactions (opening balance is not a transaction; current_balance set manually)
    derived = await repo.recalculate_balance(acc.id)
    assert derived == 0  # no transactions yet
