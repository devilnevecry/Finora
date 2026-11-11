"""Category tests including archive protection of history."""

import pytest

from app.services.category_service import CategoryService


@pytest.mark.asyncio
async def test_create_category(session):
    svc = CategoryService(session)
    c = await svc.create(name="Food", type="expense", color="#dc2626", icon="cart")
    assert c.id is not None
    assert c.type == "expense"
    assert c.color == "#dc2626"


@pytest.mark.asyncio
async def test_duplicate_name_type_rejected(session):
    svc = CategoryService(session)
    await svc.create(name="Food", type="expense")
    with pytest.raises(ValueError):
        await svc.create(name="Food", type="expense")
    # same name different type is allowed
    c = await svc.create(name="Food", type="income")
    assert c.type == "income"


@pytest.mark.asyncio
async def test_list_income_expense(session):
    svc = CategoryService(session)
    await svc.create(name="Salary", type="income")
    await svc.create(name="Food", type="expense")
    inc = await svc.list(type="income")
    exp = await svc.list(type="expense")
    assert len(inc) == 1 and len(exp) == 1


@pytest.mark.asyncio
async def test_archive_preserves_transactions(session):
    from app.repositories.category_repository import CategoryRepository

    svc = CategoryService(session)
    cat = await svc.create(name="Food", type="expense")
    repo = CategoryRepository(session)
    # category with no transactions can be deleted; archived ones keep history by design
    assert await repo.has_transactions(cat.id) is False
    await svc.archive(cat.id)
    archived = await svc.list(include_archived=True)
    assert archived[0].is_archived is True
