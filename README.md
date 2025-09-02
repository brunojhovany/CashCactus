# CashCactus (Personal Finance) [![SonarQube Cloud](https://sonarcloud.io/images/project_badges/sonarcloud-highlight.svg)](https://sonarcloud.io/summary/new_code?id=brunojhovany_CashCactus)

![CashCactus demo](images/image.png)

Open-source Flask application to manage personal finances: accounts, credit cards, debts, transactions, reminders, and reports.

## Features
- Accounts (checking, savings, investment) with balances
- Credit cards and debt tracking
- Transactions with categories and transfers
- Reports: monthly, quarterly, annual; charts with trends
- Reminders for credit card payments
- Dark mode and modern UI

## Requirements
- Python 3.8+
- SQLite (default) or any SQLAlchemy-supported DB

## Quick start
```fish
# Create virtual environment (fish shell)
python -m venv .venv
source .venv/bin/activate.fish
pip install --upgrade pip
pip install -r requirements.txt

# Run the app
export FLASK_APP=run.py
export SECRET_KEY=change-me
python run.py
```

Open http://localhost:5000.

## Configuration
All configuration via environment variables (`.env` or deployment env). See `config.py` and `.env.example`.

Core:
- SECRET_KEY: required; stable for session signing.
- DATABASE_URL: SQLAlchemy URL (defaults to local SQLite).
- TIMEZONE: affects scheduler cron times (default UTC).
- SESSION_HOURS, REMEMBER_DAYS: session persistence.

Security / Proxy:
- SESSION_COOKIE_SECURE / FORCE_COOKIE_SECURE
- FORCE_HTTPS (adjust URL generation behind TLS proxy)

Closed Beta:
- BETA_MODE=1 enables restriction.
- BETA_ALLOWED_EMAILS (comma list) and/or BETA_ALLOWED_DOMAIN.

Google OAuth:
- GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET (from Google Cloud Console)
- GOOGLE_REDIRECT_PATH (default /auth/google/callback)

Other:
- REPORT_FREQUENCY_DAYS, REMINDER_ADVANCE_DAYS

For local development: copy `.env.example` to `.env` and edit.

## Daily jobs
APScheduler runs in-process:
- 03:00 Daily maintenance (update balances, auto interest entries)
- 09:00 Update credit card reminders

## Development
- Run tests: `pytest`
- Linting/formatting: (optional) black/ruff

## Migrations
The repository includes `migrations/` (Alembic + Flask-Migrate).

Typical local flow:
```fish
export DATABASE_URL=sqlite:///$(pwd)/instance/finanzas.db
flask db upgrade          # apply all existing revisions
# Change / add models...
flask db migrate -m "add X"
flask db upgrade
```

Show history / current head:
```fish
flask db history
flask db current
```

Downgrade (only if the migration supports it):
```fish
flask db downgrade -1
```

Optional additive script: `migrations/auto_schema_sync.py` / `schema_upgrade.py`:
Provides minimal additive sync (create missing tables / columns / simple indexes) for prototyping. For production always rely on formal Alembic migrations.

Best practices (summary):
- Review every generated script in `migrations/versions/`.
- Use concise messages: `"create reminders table"`, `"add oauth_sub to users"`.
- Do not edit already published migrations; create a new one instead.
- For multiple heads (divergence): use `alembic merge`.

See more details in `migrations/README`.

### Automatic startup migrations (optional)

Set `AUTO_MIGRATE=1` to run `alembic upgrade head` when the app boots (see `app/migrations_runner.py`).

Environment variables:
- `AUTO_MIGRATE=1` activate automated upgrade.
- `MIGRATIONS_FAIL_FAST=0` continue serving even if upgrade fails (NOT recommended).
- `MIGRATIONS_ADVISORY_LOCK_ID=<int>` custom Postgres advisory lock id (default 815551) to avoid race conditions across replicas.

Use this for small/simple deployments; in larger environments consider a dedicated migration job in your pipeline.

## License
MIT — see `LICENSE`.
