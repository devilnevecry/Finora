"""API endpoint and CSRF protection tests using an isolated temp database."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

import app.database as database_module
from app.database import Base
from app.main import create_app


@pytest.fixture
async def client(temp_db_path):
    database_url = "sqlite+aiosqlite:///" + temp_db_path.replace("\\", "/")
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(
        engine, class_=database_module.AsyncSession, expire_on_commit=False
    )
    database_module.engine = engine
    database_module.async_session_factory = session_factory

    app = create_app()
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


def _csrf_token(res):
    return res.headers.get("x-csrf-token")


@pytest.mark.asyncio
async def test_accounts_crud(client):
    # Establish CSRF token via a safe GET.
    res = await client.get("/dashboard")
    token = _csrf_token(res)
    assert token, "CSRF token should be issued"

    headers = {"X-CSRF-Token": token}

    res = await client.get("/api/accounts")
    assert res.status_code == 200
    assert res.json() == []

    res = await client.post(
        "/api/accounts",
        data={
            "name": "Wallet",
            "type": "cash",
            "currency": "USD",
            "opening_balance": "100.00",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Wallet"
    acc_id = body["id"]

    res = await client.get("/api/accounts")
    assert len(res.json()) == 1

    res = await client.get(f"/api/accounts/{acc_id}")
    assert res.status_code == 200

    res = await client.put(f"/api/accounts/{acc_id}", data={"name": "Wallet2"}, headers=headers)
    assert res.status_code == 200

    res = await client.delete(f"/api/accounts/{acc_id}", headers=headers)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_csrf_protection(client):
    # No page load yet -> no token; mutating request rejected.
    res = await client.post("/api/accounts", data={"name": "NoToken", "type": "cash"})
    assert res.status_code == 403

    # Establish token, then a wrong token is rejected.
    res = await client.get("/dashboard")
    token = _csrf_token(res)
    res = await client.post(
        "/api/accounts",
        data={"name": "BadToken", "type": "cash"},
        headers={"X-CSRF-Token": "wrong"},
    )
    assert res.status_code == 403

    # Correct token is accepted.
    res = await client.post(
        "/api/accounts", data={"name": "Good", "type": "cash"}, headers={"X-CSRF-Token": token}
    )
    assert res.status_code == 201, res.text


@pytest.mark.asyncio
async def test_categories_and_transactions_endpoints(client):
    res = await client.get("/dashboard")
    token = _csrf_token(res)
    headers = {"X-CSRF-Token": token}

    await client.post(
        "/api/accounts",
        data={"name": "Wallet", "type": "cash", "opening_balance": "100.00"},
        headers=headers,
    )
    res = await client.post(
        "/api/categories",
        data={"name": "Food", "type": "expense", "color": "#dc2626"},
        headers=headers,
    )
    assert res.status_code == 201

    # GET (safe) works without CSRF concerns
    res = await client.get("/api/transactions")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_backup_and_settings_endpoints(client):
    res = await client.get("/api/backup")
    assert res.status_code == 200
    res = await client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "base_currency" in data
    assert "supported_languages" in data
