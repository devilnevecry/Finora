"""FastAPI application factory and entry point.

Creates and configures the Finora application: routers, static files, Jinja2
templates, CSRF middleware, and startup database initialization.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api import (
    accounts,
    backup,
    budgets,
    categories,
    import_export,
    recurring,
    reports,
    search,
    transactions,
)
from app.api import (
    settings as settings_api,
)
from app.config import get_settings
from app.database import Base, engine
from app.middleware.csrf import CSRFMiddleware, generate_csrf_token

settings = get_settings()

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def flash_message(request: Request, message: str, category: str = "info") -> None:
    request.session.setdefault("_flash", []).append((category, message))


def get_flashed_messages(request: Request, with_categories: bool = False):
    messages = request.session.pop("_flash", [])
    if with_categories:
        return messages
    return [m for _, m in messages]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Finora",
        description="Privacy-first local personal finance management",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )

    app.add_middleware(CSRFMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    # API routes
    app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
    app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
    app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
    app.include_router(budgets.router, prefix="/api/budgets", tags=["budgets"])
    app.include_router(recurring.router, prefix="/api/recurring", tags=["recurring"])
    app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
    app.include_router(import_export.router, prefix="/api/import-export", tags=["import-export"])
    app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
    app.include_router(search.router, prefix="/api/search", tags=["search"])
    app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])

    # Static files
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
        name="static",
    )

    # Jinja2 globals
    templates.env.globals["csrf_token"] = generate_csrf_token
    templates.env.globals["url_for"] = app.url_path_for
    templates.env.globals["get_flashed_messages"] = get_flashed_messages
    templates.env.globals["lang"] = settings.default_language
    templates.env.globals["theme"] = ""

    # UI routes
    @app.get("/", include_in_schema=False)
    async def root(request: Request):
        return RedirectResponse(url="/dashboard")

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard(request: Request):
        return templates.TemplateResponse("dashboard.html", {"request": request})

    @app.get("/transactions", include_in_schema=False)
    async def transactions_page(request: Request):
        return templates.TemplateResponse("transactions.html", {"request": request})

    @app.get("/accounts", include_in_schema=False)
    async def accounts_page(request: Request):
        return templates.TemplateResponse("accounts.html", {"request": request})

    @app.get("/categories", include_in_schema=False)
    async def categories_page(request: Request):
        return templates.TemplateResponse("categories.html", {"request": request})

    @app.get("/budgets", include_in_schema=False)
    async def budgets_page(request: Request):
        return templates.TemplateResponse("budgets.html", {"request": request})

    @app.get("/recurring", include_in_schema=False)
    async def recurring_page(request: Request):
        return templates.TemplateResponse("recurring.html", {"request": request})

    @app.get("/reports", include_in_schema=False)
    async def reports_page(request: Request):
        return templates.TemplateResponse("reports.html", {"request": request})

    @app.get("/import", include_in_schema=False)
    async def import_page(request: Request):
        return templates.TemplateResponse("import.html", {"request": request})

    @app.get("/export", include_in_schema=False)
    async def export_page(request: Request):
        return templates.TemplateResponse("export.html", {"request": request})

    @app.get("/backup", include_in_schema=False)
    async def backup_page(request: Request):
        return templates.TemplateResponse("backup.html", {"request": request})

    @app.get("/settings", include_in_schema=False)
    async def settings_page(request: Request):
        return templates.TemplateResponse("settings.html", {"request": request})

    @app.on_event("startup")
    async def on_startup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    return app


def run() -> None:
    """Run the application with uvicorn (used by the ``finora`` console script)."""
    import uvicorn

    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers if not settings.reload else 1,
    )


__all__ = ["create_app", "run"]
