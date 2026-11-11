# Finora — Private Personal Finance Manager

Finora is an open-source, local-first personal finance application designed to run
on your own computer. It helps you understand where your money goes, plan budgets,
keep track of accounts, and spot spending patterns.

## Core principles

- Privacy first — data is stored locally only (SQLite on your machine).
- No mandatory registration and no cloud accounts.
- No integration with external financial APIs and no external analytics.
- No advertising and no hidden data transmission.
- Reliable financial calculations (integer minor currency units, no binary floats).
- Full control over data export and backups.
- Server bound to `127.0.0.1` by default (not exposed to the network).

## Technology stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x (async)
- SQLite (file database at `app/data/finora.db`)
- Alembic (migrations)
- Jinja2, HTML5, CSS3, Vanilla JavaScript
- pytest, Ruff

## Features

- Accounts: cash, bank, savings, credit, custom — with balances.
- Income, expenses, and transfers between accounts (transfers are not counted as
  income or expense).
- Income/expense categories with colors, icons, and archiving.
- Budgets: monthly and per-category, progress, remaining amount, overspending indicator.
- Recurring transactions (daily, weekly, monthly, yearly, custom interval) with
  duplicate prevention.
- Dashboard: total balance, income, expenses, net cash flow, comparison with the
  previous period, spending by category, recent transactions, account overview.
- Filtering, search, sorting, and pagination for transactions.
- CSV export and import with column mapping and preview.
- Backup and restore (JSON archive of the whole database).
- Search by descriptions and notes.
- Localization: Russian (default) and English; light and dark themes.
- CSRF protection, input validation, upload size limits.

## Architecture

Modular structure:

```
app/
  config.py         configuration (environment variables)
  database.py       SQLAlchemy engine/session
  models/           ORM models (accounts, categories, transactions, budgets, recurrence, tags)
  repositories/     data access layer
  services/         business logic (money math, transfers, reports, import/export, backups)
  api/              FastAPI HTTP routes
  middleware/       CSRF protection
  templates/        Jinja2 UI templates
  static/           CSS and JS (i18n, shared logic, Canvas charts)
  locales/          translation files (ru, en)
  migrations/       Alembic migrations
  data/             working directory with the SQLite database (created on startup)
```

All monetary amounts are stored as integer minor currency units (cents), avoiding
binary floating-point arithmetic errors.

## Installation and launch (Windows PowerShell)

```powershell
# Clone or copy the repository
cd C:\Users\nu11\Documents\GitHub\Finora

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# First launch
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
# or, after installing the package:
finora
```

The database is initialized automatically on first launch (`app/data/finora.db`).
Open `http://127.0.0.1:8000/` in your browser.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `FINORA_HOST` | `127.0.0.1` | Server bind address |
| `FINORA_PORT` | `8000` | Server port |
| `FINORA_BASE_CURRENCY` | `USD` | Base currency (3-letter code) |
| `FINORA_CURRENCY_SYMBOL` | `$` | Currency symbol |
| `FINORA_DEFAULT_LANGUAGE` | `ru` | Default language |
| `FINORA_DATA_DIR` | `app/data` | Data directory |
| `FINORA_DATABASE_FILE` | `finora.db` | Database file name |
| `FINORA_DEBUG` | `0` | Debug mode |

## Testing

```powershell
pip install -r requirements.txt
pytest
```

Tests use isolated temporary SQLite databases and synthetic data. No external
websites or APIs are used.

## Backup and restore

- Create a backup: "Backup" section → "Create backup" (JSON file in `app/data`).
- Download and restore from a file with explicit confirmation.
- Backups are validated before restore; the working database is replaced atomically.

## Security and privacy

Finora is intended for local, single-user use. It is not a multi-user banking
platform and makes no claims of bank-grade certification. The server binds to
`127.0.0.1`, financial data never leaves your computer, and there is no analytics
or telemetry.

## Limitations

- One base currency for analytics (multi-currency is not implemented).
- Recurring transfers between accounts are not supported (only income/expense).
- Local single-user application, not designed for concurrent multi-user access.

## License

MIT. Copyright (c) 2026 devilnevecry.
