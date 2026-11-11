"""Transaction arithmetic, transfers, and balance invariants."""

from datetime import datetime

import pytest

from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.services.currency import MoneyError
from app.services.transaction_service import TransactionService


async def _setup(session):
    acc_svc = AccountService(session)
    cat_svc = CategoryService(session)
    tx_svc = TransactionService(session)
    acc = await acc_svc.create(
        name="Wallet", type="cash", currency="USD", opening_balance="1000.00"
    )
    inc_cat = await cat_svc.create(name="Salary", type="income")
    exp_cat = await cat_svc.create(name="Food", type="expense")
    return tx_svc, acc, inc_cat, exp_cat


@pytest.mark.asyncio
async def test_income_increases_balance(session):
    tx_svc, acc, inc_cat, _ = await _setup(session)
    tx = await tx_svc.create_income(
        account_id=acc.id,
        amount="250.00",
        category_id=inc_cat.id,
        transaction_date=datetime(2026, 1, 10, 12, 0),
        description="Salary",
    )
    assert tx.amount == 25000
    assert tx.type == "income"
    acc2 = await AccountService(session).get(acc.id)
    assert acc2.current_balance == 125000  # 1000.00 + 250.00


@pytest.mark.asyncio
async def test_expense_decreases_balance(session):
    tx_svc, acc, _, exp_cat = await _setup(session)
    tx = await tx_svc.create_expense(
        account_id=acc.id,
        amount="100.00",
        category_id=exp_cat.id,
        transaction_date=datetime(2026, 1, 10, 12, 0),
        description="Groceries",
    )
    assert tx.amount == 10000
    acc2 = await AccountService(session).get(acc.id)
    assert acc2.current_balance == 90000


@pytest.mark.asyncio
async def test_expense_insufficient_funds_rejected(session):
    tx_svc, acc, _, exp_cat = await _setup(session)
    with pytest.raises(MoneyError):
        await tx_svc.create_expense(
            account_id=acc.id,
            amount="2000.00",
            category_id=exp_cat.id,
            transaction_date=datetime(2026, 1, 10, 12, 0),
            description="Too expensive",
        )


@pytest.mark.asyncio
async def test_transfer_updates_both_accounts_not_income_expense(session):
    acc_svc = AccountService(session)
    cat_svc = CategoryService(session)
    tx_svc = TransactionService(session)
    src = await acc_svc.create(name="Source", type="bank", opening_balance="500.00")
    dst = await acc_svc.create(name="Dest", type="savings", opening_balance="200.00")
    _exp_cat = await cat_svc.create(name="Food", type="expense")

    expense_tx, income_tx = await tx_svc.create_transfer(
        source_account_id=src.id,
        destination_account_id=dst.id,
        amount="150.00",
        transaction_date=datetime(2026, 1, 10, 12, 0),
        description="Move money",
    )
    assert expense_tx.type == "transfer"
    assert income_tx.type == "transfer"
    assert expense_tx.linked_transaction_id == income_tx.id
    assert income_tx.linked_transaction_id == expense_tx.id

    s2 = await acc_svc.get(src.id)
    d2 = await acc_svc.get(dst.id)
    assert s2.current_balance == 35000  # 500 - 150
    assert d2.current_balance == 35000  # 200 + 150

    # Transfers must not appear as income/expense in analytics
    rows, _ = await tx_svc.list(type="income")
    assert all(t.id != income_tx.id for t in rows)
    rows, _ = await tx_svc.list(type="expense")
    assert all(t.id != expense_tx.id for t in rows)


@pytest.mark.asyncio
async def test_category_compatibility(session):
    tx_svc, acc, inc_cat, exp_cat = await _setup(session)
    # expense with income category must be rejected
    with pytest.raises(MoneyError):
        await tx_svc.create_expense(
            account_id=acc.id,
            amount="10.00",
            category_id=inc_cat.id,
            transaction_date=datetime(2026, 1, 10, 12, 0),
            description="X",
        )
    # income with expense category must be rejected
    with pytest.raises(MoneyError):
        await tx_svc.create_income(
            account_id=acc.id,
            amount="10.00",
            category_id=exp_cat.id,
            transaction_date=datetime(2026, 1, 10, 12, 0),
            description="X",
        )


@pytest.mark.asyncio
async def test_balance_invariant_after_delete(session):
    tx_svc, acc, _, exp_cat = await _setup(session)
    await tx_svc.create_expense(
        account_id=acc.id,
        amount="100.00",
        category_id=exp_cat.id,
        transaction_date=datetime(2026, 1, 10, 12, 0),
        description="D",
    )
    before = (await AccountService(session).get(acc.id)).current_balance
    # delete the actual expense we just created
    rows, _ = await tx_svc.list(account_id=acc.id, type="expense")
    tx_id = rows[0].id
    await tx_svc.delete(tx_id)
    after = (await AccountService(session).get(acc.id)).current_balance
    assert after == before + 10000  # expense removed, balance restored
