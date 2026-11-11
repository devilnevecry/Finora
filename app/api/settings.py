"""Settings API routes (language, currency, app info)."""

from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from app.config import get_settings

router = APIRouter()

settings = get_settings()


@router.get("")
async def get_settings_route():
    return JSONResponse(
        {
            "default_language": settings.default_language,
            "supported_languages": list(settings.supported_languages),
            "base_currency": settings.base_currency,
            "currency_symbol": settings.currency_symbol,
            "host": settings.host,
            "port": settings.port,
        }
    )


@router.post("/language")
async def set_language(language: str = Form(...)):
    settings = get_settings()
    if language not in settings.supported_languages:
        return JSONResponse({"error": "unsupported language"}, status_code=400)
    # Stored in session by the frontend; here we just acknowledge.
    return JSONResponse({"language": language, "ok": True})
