"""Financial integrity regression tests.

Covers balance invariants, amount editing with rebalancing, transfer
conservation, currency precision, and backup/restore integrity. These are
regression tests for defects found during Phase 3 QA.
"""

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.account_service import AccountService
from app.services.backup_service import (
    BackupError,
    create_backup,
    restore_backup,
    validate_backup,
)
from app.services.category_service import CategoryService
from app.services.currency import (
    MoneyError,
    from_minor_units,
    to_minor_units,
)
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


# ---------------------------------------------------------------------------
# Currency precision (3.1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_currency_precision_boundary_values(session):
    for text, expected in [
        ("0.01", 1),
        ("0.10", 10),
        ("0.29", 29),
        ("1.99", 199),
        ("10.01", 1001),
        ("999.99", 99999),
        ("1000000.00", 100000000),
    ]:
        assert to_minor_units(text) == expected, f"failed for {text}"
        assert from_minor_units(to_minor_units(text)) == __import__("decimal").Decimal(text)


@pytest.mark.asyncio
async def test_repeated_operations_no_rounding_drift(session):
    tx_svc, acc, inc_cat, _ = await _setup(session)
    # Apply 1000 tiny income operations of 0.01 each.
    total_applied = 0
    for _ in range(1000):
        await tx_svc.create_income(
            account_id=acc.id,
            amount="0.01",
            category_id=inc_cat.id,
            transaction_date=datetime(2026, 1, 1),
            description="tiny",
        )
        total_applied += 1
    acc2 = await AccountService(session).get(acc.id)
    assert acc2.current_balance == 100000 + 1000  # 1000.00 + 1000 * 0.01


@pytest.mark.asyncio
async def test_invalid_amounts_rejected(session):
    tx_svc, acc, _, exp_cat = await _setup(session)
    for bad in ["", "abc", "1.2.3", "-5.00", "0.00", "NaN", "inf"]:
        with pytest.raises((MoneyError, ValueError)):
            await tx_svc.create_expense(
                account_id=acc.id,
                amount=bad,
                category_id=exp_cat.id,
                transaction_date=datetime(2026, 1, 1),
                description="bad",
            )


# ---------------------------------------------------------------------------
# Amount editing with rebalancing (3.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_income_amount_rebalances(session):
    tx_svc, acc, inc_cat, _ = await _setup(session)
    tx = await tx_svc.create_income(
        account_id=acc.id,
        amount="100.00",
        category_id=inc_cat.id,
        transaction_date=datetime(2026, 1, 10),
        description="Salary",
    )
    after_create = (await AccountService(session).get(acc.id)).current_balance
    assert after_create == 100000 + 10000

    # Edit amount 100.00 -> 250.00: balance should increase by 150.00
    updated = await tx_svc.update(tx.id, amount="250.00")
    assert updated.amount == 25000
    after_edit = (await AccountService(session).get(acc.id)).current_balance
    assert after_edit == after_create + 15000  # 1000.00 + 250.00


@pytest.mark.asyncio
async def test_edit_expense_amount_rebalances(session):
    tx_svc, acc, _, exp_cat = await _setup(session)
    tx = await tx_svc.create_expense(
        account_id=acc.id,
        amount="100.00",
        category_id=exp_cat.id,
        transaction_date=datetime(2026, 1, 10),
        description="Groceries",
    )
    after_create = (await AccountService(session).get(acc.id)).current_balance
    assert after_create == 100000 - 10000

    # Edit amount 100.00 -> 40.00: balance should increase by 60.00 (less spent)
    updated = await tx_svc.update(tx.id, amount="40.00")
    assert updated.amount == 4000
    after_edit = (await AccountService(session).get(acc.id)).current_balance
    assert after_edit == after_create + 6000  # 1000.00 - 40.00


@pytest.mark.asyncio
async def test_edit_expense_amount_insufficient_funds_rejected(session):
    tx_svc, acc, _, exp_cat = await _setup(session)
    tx = await tx_svc.create_expense(
        account_id=acc.id,
        amount="10.00",
        category_id=exp_cat.id,
        transaction_date=datetime(2026, 1, 10),
        description="Groceries",
    )
    # Try to raise amount to 2000.00 which would overdraft the cash account.
    with pytest.raises(MoneyError):
        await tx_svc.update(tx.id, amount="2000.00")


@pytest.mark.asyncio
async def test_edit_transfer_amount_rejected(session):
    acc_svc = AccountService(session)
    cat_svc = CategoryService(session)
    tx_svc = TransactionService(session)
    src = await acc_svc.create(name="Source", type="bank", opening_balance="500.00")
    dst = await acc_svc.create(name="Dest", type="savings", opening_balance="200.00")
    _exp_cat = await cat_svc.create(name="Food", type="expense")

    expense_tx, _income_tx = await tx_svc.create_transfer(
        source_account_id=src.id,
        destination_account_id=dst.id,
        amount="150.00",
        transaction_date=datetime(2026, 1, 10),
        description="Move money",
    )
    with pytest.raises(MoneyError):
        await tx_svc.update(expense_tx.id, amount="500.00")


@pytest.mark.asyncio
async def test_edit_category_compatibility_enforced(session):
    tx_svc, acc, inc_cat, exp_cat = await _setup(session)
    tx = await tx_svc.create_income(
        account_id=acc.id,
        amount="100.00",
        category_id=inc_cat.id,
        transaction_date=datetime(2026, 1, 10),
        description="Salary",
    )
    # Changing an income transaction to an expense category must be rejected.
    with pytest.raises(MoneyError):
        await tx_svc.update(tx.id, category_id=exp_cat.id)


# ---------------------------------------------------------------------------
# Deletion restores balance (3.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_income_restores_balance(session):
    tx_svc, acc, inc_cat, _ = await _setup(session)
    await tx_svc.create_income(
        account_id=acc.id,
        amount="250.00",
        category_id=inc_cat.id,
        transaction_date=datetime(2026, 1, 10),
        description="Salary",
    )
    before = (await AccountService(session).get(acc.id)).current_balance
    rows, _ = await tx_svc.list(account_id=acc.id, type="income")
    await tx_svc.delete(rows[0].id)
    after = (await AccountService(session).get(acc.id)).current_balance
    assert after == before - 25000  # back to 1000.00


@pytest.mark.asyncio
async def test_delete_expense_restores_balance(session):
    tx_svc, acc, _, exp_cat = await _setup(session)
    await tx_svc.create_expense(
        account_id=acc.id,
        amount="100.00",
        category_id=exp_cat.id,
        transaction_date=datetime(2026, 1, 10),
        description="Groceries",
    )
    before = (await AccountService(session).get(acc.id)).current_balance
    rows, _ = await tx_svc.list(account_id=acc.id, type="expense")
    await tx_svc.delete(rows[0].id)
    after = (await AccountService(session).get(acc.id)).current_balance
    assert after == before + 10000  # back to 1000.00


@pytest.mark.asyncio
async def test_delete_transfer_conserves_funds(session):
    acc_svc = AccountService(session)
    tx_svc = TransactionService(session)
    src = await acc_svc.create(name="Source", type="bank", opening_balance="500.00")
    dst = await acc_svc.create(name="Dest", type="savings", opening_balance="200.00")

    await tx_svc.create_transfer(
        source_account_id=src.id,
        destination_account_id=dst.id,
        amount="150.00",
        transaction_date=datetime(2026, 1, 10),
        description="Move money",
    )
    src_before = (await acc_svc.get(src.id)).current_balance
    dst_before = (await acc_svc.get(dst.id)).current_balance
    assert src_before == 35000
    assert dst_before == 35000

    # Delete the transfer: both legs reversed, total conserved.
    rows, _ = await tx_svc.list(type="transfer")
    assert len(rows) == 2
    await tx_svc.delete(rows[0].id)

    src_after = (await acc_svc.get(src.id)).current_balance
    dst_after = (await acc_svc.get(dst.id)).current_balance
    assert src_after == 50000  # back to 500.00
    assert dst_after == 20000  # back to 200.00


# ---------------------------------------------------------------------------
# Backup / restore integrity (6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_restore_preserves_data(temp_db_path):
    import app.services.backup_service as bs
    from app.config import Settings
    from app.database import Base

    tmp_path = Path(temp_db_path)
    db_url = "sqlite+aiosqlite:///" + str(tmp_path).replace("\\", "/")
    test_settings = Settings(
        data_dir=str(tmp_path.parent),
        database_file=tmp_path.name,
        database_url=db_url,
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(bs, "settings", test_settings)

    # Setup: create schema and seed data with a dedicated engine.
    engine = create_async_engine(test_settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as sess:
        tx_svc, acc, inc_cat, _exp_cat = await _setup(sess)
        await tx_svc.create_income(
            account_id=acc.id,
            amount="250.00",
            category_id=inc_cat.id,
            transaction_date=datetime(2026, 1, 10),
            description="Salary",
        )
        await sess.commit()
    await engine.dispose()

    backup = create_backup()
    assert backup["filename"].endswith(".json")

    meta = validate_backup(backup["path"])
    assert meta is not None
    assert "accounts" in meta.get("tables", [])
    assert "transactions" in meta.get("tables", [])

    # Reopen engine, add another transaction, then restore - it should be gone.
    engine2 = create_async_engine(test_settings.database_url)
    async_session2 = sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)
    async with async_session2() as sess2:
        tx_svc2 = TransactionService(sess2)
        await tx_svc2.create_income(
            account_id=acc.id,
            amount="100.00",
            category_id=inc_cat.id,
            transaction_date=datetime(2026, 1, 11),
            description="Bonus",
        )
        await sess2.commit()
    await engine2.dispose()

    restore_backup(backup["path"])

    # Verify restored state with a fresh engine.
    engine3 = create_async_engine(test_settings.database_url)
    async_session3 = sessionmaker(engine3, class_=AsyncSession, expire_on_commit=False)
    async with async_session3() as sess3:
        tx_svc3 = TransactionService(sess3)
        rows, _ = await tx_svc3.list()
        descriptions = {t.description for t in rows}
        assert "Salary" in descriptions
        assert "Bonus" not in descriptions  # removed by restore
    await engine3.dispose()
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_invalid_backup_rejected(temp_db_path):
    import app.services.backup_service as bs
    from app.config import Settings

    tmp_path = Path(temp_db_path)
    test_settings = Settings(
        data_dir=str(tmp_path.parent),
        database_file=tmp_path.name,
        database_url="sqlite+aiosqlite:///" + str(tmp_path).replace("\\", "/"),
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(bs, "settings", test_settings)

    bad = tmp_path.parent / "bad_backup.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(BackupError):
        validate_backup(str(bad))

    incomplete = tmp_path.parent / "incomplete.json"
    incomplete.write_text('{"metadata": {"tables": ["accounts"]}, "data": {}}', encoding="utf-8")
    with pytest.raises(BackupError):
        validate_backup(str(incomplete))
    monkeypatch.undo()
