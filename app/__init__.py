"""Finora — privacy-first local personal finance application.

Package entry point. The FastAPI application is created by ``create_app``
and exposed for uvicorn via ``app``.
"""

from app.main import create_app

app = create_app()

__all__ = ["app", "create_app"]
