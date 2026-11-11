"""Application configuration.

All configuration is read from environment variables with sensible defaults.
No secrets are required and none are hardcoded. The application is designed
to run exclusively on 127.0.0.1 for local, single-user use.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the Finora application."""

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    reload: bool = False
    workers: int = 1
    base_dir: str = ""
    data_dir: str = ""
    database_url: str = ""
    database_file: str = "finora.db"
    base_currency: str = "USD"
    currency_symbol: str = "$"
    csv_max_upload_mb: int = 10
    secret_key: str = ""
    default_language: str = "ru"
    supported_languages: tuple[str, ...] = ("ru", "en")
    page_size: int = 25

    @classmethod
    def load(cls) -> Settings:
        base_dir = os.environ.get("FINORA_BASE_DIR") or os.path.dirname(os.path.abspath(__file__))
        data_dir = os.environ.get("FINORA_DATA_DIR") or os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        database_file = os.environ.get("FINORA_DATABASE_FILE") or cls.database_file
        database_url = os.environ.get("FINORA_DATABASE_URL") or (
            "sqlite:///" + os.path.join(data_dir, database_file).replace("\\", "/")
        )

        return cls(
            host=os.environ.get("FINORA_HOST", cls.host),
            port=_env_int("FINORA_PORT", cls.port),
            debug=_env_bool("FINORA_DEBUG", cls.debug),
            reload=_env_bool("FINORA_RELOAD", cls.reload),
            workers=_env_int("FINORA_WORKERS", cls.workers),
            base_dir=base_dir,
            data_dir=data_dir,
            database_url=database_url,
            database_file=database_file,
            base_currency=os.environ.get("FINORA_BASE_CURRENCY", cls.base_currency),
            currency_symbol=os.environ.get("FINORA_CURRENCY_SYMBOL", cls.currency_symbol),
            csv_max_upload_mb=_env_int("FINORA_CSV_MAX_UPLOAD_MB", cls.csv_max_upload_mb),
            secret_key=os.environ.get("FINORA_SECRET_KEY") or os.urandom(24).hex(),
            default_language=os.environ.get("FINORA_DEFAULT_LANGUAGE", cls.default_language),
            supported_languages=tuple(
                lang.strip()
                for lang in os.environ.get(
                    "FINORA_SUPPORTED_LANGUAGES", ",".join(cls.supported_languages)
                ).split(",")
                if lang.strip()
            ),
            page_size=_env_int("FINORA_PAGE_SIZE", cls.page_size),
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings.load()


__all__ = ["Settings", "get_settings"]
