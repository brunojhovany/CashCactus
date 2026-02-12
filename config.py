import os
from datetime import timedelta


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Application configuration (safe defaults for open source).

    All sensitive values should come from environment variables. The defaults
    below are development-friendly and NOT intended for production.
    """

    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError(
            'SECRET_KEY must be set in environment variables.\n'
            'Generate a secure key with: python -c "import secrets; print(secrets.token_hex(32))"\n'
            'Then set: export SECRET_KEY="<generated_key>"'
        )
    if len(SECRET_KEY) < 32:
        raise RuntimeError('SECRET_KEY must be at least 32 characters long for security.')

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

    # Proxy / esquema (cuando está detrás de Cloudflare / Traefik con TLS)
    PREFERRED_URL_SCHEME = 'https' if os.environ.get('FORCE_HTTPS', '0') == '1' else 'http'

    # Ajustes ProxyFix (para reconstrucción correcta de URLs cuando la app corre detrás
    # de un Ingress / Load Balancer que añade cabeceras X-Forwarded-*)
    # Número de proxies de los que se deben aceptar encabezados. Normalmente 1 si sólo hay
    # un Ingress / Reverse Proxy delante del contenedor.
    PROXY_FIX_X_FOR = int(os.environ.get('PROXY_FIX_X_FOR', '1')) if os.environ.get('ENABLE_PROXY_FIX', '1') == '1' else 0
    PROXY_FIX_X_PROTO = int(os.environ.get('PROXY_FIX_X_PROTO', '1')) if os.environ.get('ENABLE_PROXY_FIX', '1') == '1' else 0
    PROXY_FIX_X_HOST = int(os.environ.get('PROXY_FIX_X_HOST', '0')) if os.environ.get('ENABLE_PROXY_FIX', '1') == '1' else 0
    PROXY_FIX_X_PORT = int(os.environ.get('PROXY_FIX_X_PORT', '0')) if os.environ.get('ENABLE_PROXY_FIX', '1') == '1' else 0
    PROXY_FIX_X_PREFIX = int(os.environ.get('PROXY_FIX_X_PREFIX', '0')) if os.environ.get('ENABLE_PROXY_FIX', '1') == '1' else 0

    # Permite forzar un dominio externo específico si, por alguna razón, los encabezados
    # de proxy no son fiables. Evitar usarlo salvo necesidad puntual (ej: tareas offline que
    # construyen URLs absolutas). Formato sin esquema, ej: "app.ejemplo.com".
    FORCE_EXTERNAL_HOST = os.environ.get('FORCE_EXTERNAL_HOST')  # opcional

    # Closed Beta
    BETA_MODE = os.environ.get('BETA_MODE', '0') == '1'  # si True restringe acceso solo a emails permitidos
    # Lista explícita de correos permitidos (coma separada) o dominio permitido
    BETA_ALLOWED_EMAILS = {e.strip().lower() for e in os.environ.get('BETA_ALLOWED_EMAILS', '').split(',') if e.strip()}
    BETA_ALLOWED_DOMAIN = os.environ.get('BETA_ALLOWED_DOMAIN', '').lower().strip()

    # OAuth Google (usar Secrets reales en despliegue)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    # Redirect URI (si no se define, se construirá dinámicamente en runtime)
    GOOGLE_REDIRECT_PATH = os.environ.get('GOOGLE_REDIRECT_PATH', '/auth/google/callback')

    # Reports
    REPORT_FREQUENCY_DAYS = int(os.environ.get('REPORT_FREQUENCY_DAYS', '90'))  # quarterly

    # Reminders
    REMINDER_ADVANCE_DAYS = int(os.environ.get('REMINDER_ADVANCE_DAYS', '3'))  # days before due

    # Session (más seguro: reducir tiempos)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get('SESSION_HOURS', '2')))  # Reducido a 2 horas
    SESSION_INACTIVITY_TIMEOUT = timedelta(minutes=int(os.environ.get('SESSION_INACTIVITY_MINUTES', '30')))  # 30 min inactividad
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'  # Cambio de Lax a Strict para mayor seguridad
    SESSION_COOKIE_SECURE = True  # Siempre True (Cloudflare maneja HTTPS)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Strict'
    REMEMBER_COOKIE_SECURE = True
    # Force refresh interval for remember cookie (mitigate stolen cookie reuse)
    REMEMBER_COOKIE_DURATION = timedelta(days=int(os.environ.get('REMEMBER_DAYS', '7')))
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No expiración de tokens
    WTF_CSRF_SSL_STRICT = True
    
    # Rate Limiting
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', '1') == '1'
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_HEADERS_ENABLED = True
    
    # OAuth Security
    OAUTH_REDIRECT_URIS = {
        'google': os.environ.get('GOOGLE_REDIRECT_URI', 'https://localhost/auth/google/callback')
    }
    ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]
