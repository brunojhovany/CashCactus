import os
from datetime import timedelta


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Application configuration (safe defaults for open source).

    All sensitive values should come from environment variables. The defaults
    below are development-friendly and NOT intended for production.
    """

    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')  # MUST override via env in production
    if SECRET_KEY == 'change-me' and os.environ.get('ALLOW_DEFAULT_SECRET') != '1':
        # Fail fast to avoid predictable session signing allowing impersonation
        raise RuntimeError('Insecure SECRET_KEY in use. Set SECRET_KEY env var (export SECRET_KEY="super-random-value").')

    # Database (default to SQLite in the instance folder)
    # Examples:
    #   export DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
    #   export DATABASE_URL=mysql+pymysql://user:pass@host:3306/dbname
    _default_sqlite = os.path.join(BASE_DIR, 'instance', 'finanzas.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f'sqlite:///{_default_sqlite}'
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
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    # Force refresh interval for remember cookie (mitigate stolen cookie reuse)
    REMEMBER_COOKIE_DURATION = timedelta(days=int(os.environ.get('REMEMBER_DAYS', '7')))
