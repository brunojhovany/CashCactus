import os
from datetime import timedelta


class Config:
    """Application configuration (safe defaults for open source).

    All sensitive values should come from environment variables. The defaults
    below are development-friendly and NOT intended for production.
    """

    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')  # override via env in production

    # Database (default to SQLite in the instance folder)
    # Examples:
    #   export DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
    #   export DATABASE_URL=mysql+pymysql://user:pass@host:3306/dbname
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///instance/finanzas.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Timezone
    TIMEZONE = os.environ.get('TIMEZONE', 'UTC')

    # Reports
    REPORT_FREQUENCY_DAYS = int(os.environ.get('REPORT_FREQUENCY_DAYS', '90'))  # quarterly

    # Reminders
    REMINDER_ADVANCE_DAYS = int(os.environ.get('REMINDER_ADVANCE_DAYS', '3'))  # days before due

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get('SESSION_HOURS', '24')))
