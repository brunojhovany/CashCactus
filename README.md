# CashCactus (Personal Finance)

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
All configuration via environment variables (see `config.py`):
- SECRET_KEY: application secret
- DATABASE_URL: SQLAlchemy URL (default: sqlite:///instance/finanzas.db)
- TIMEZONE: default UTC
- REPORT_FREQUENCY_DAYS: default 90
- REMINDER_ADVANCE_DAYS: default 3
- SESSION_HOURS: default 24

## Daily jobs
APScheduler runs in-process:
- 03:00 Daily maintenance (update balances, auto interest entries)
- 09:00 Update credit card reminders

## Development
- Run tests: `pytest`
- Linting/formatting: (optional) black/ruff

## Security
Never commit secrets or production databases. Use environment variables and the `instance/` folder for local data.

## License
MIT — see `LICENSE`.
