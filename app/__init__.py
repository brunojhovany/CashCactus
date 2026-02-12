# -*- coding: utf-8 -*-
from flask import Flask, request, abort, session, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from config import Config
import os
from sqlalchemy import inspect, text  # noqa: F401 (podrían usarse en futuras inicializaciones condicionales)
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import logging
import re

# Filtro de sanitización de logs
class SensitiveDataFilter(logging.Filter):
    """Filtro para remover datos sensibles de logs"""
    SENSITIVE_PATTERNS = [
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
        (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD_REDACTED]'),
        (r'\$\d+[\d,]*\.\d{2}', '[AMOUNT_REDACTED]'),
        (r"password['\"]?\s*[:=]\s*['\"]?[\w\d]+", "password=[REDACTED]"),
        (r"token['\"]?\s*[:=]\s*['\"]?[\w\d]+", "token=[REDACTED]"),
    ]
    
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                record.msg = re.sub(pattern, replacement, record.msg, flags=re.IGNORECASE)
        return True

# Configurar logging con filtro
for handler in logging.getLogger().handlers:
    handler.addFilter(SensitiveDataFilter())

# Avoid attribute expiration after commit so test fixtures can access model fields
# without needing an active session context (helps in unit tests where objects
# are returned outside the app context). Production impact is minimal here and
# simplifies tests.
db = SQLAlchemy(session_options={'expire_on_commit': False})
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",  # Usar Redis en producción
)

def create_app():
    app = Flask(__name__, template_folder='views/templates')
    app.config.from_object(Config)
    # Logging básico si no hay handlers configurados (evitar duplicados en WSGI reload)
    import logging, sys, os
    if not logging.getLogger().handlers:
        level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logging.basicConfig(
            level=level,
            format='%(asctime)s %(levelname)s %(name)s %(message)s',
            stream=sys.stdout
        )

    # Aplicar ProxyFix si está habilitado (por defecto sí). Esto permite que url_for(_external=True)
    # use el Host y esquema reales enviados por el Ingress (cabeceras X-Forwarded-*).
    if any([
        app.config.get('PROXY_FIX_X_FOR'),
        app.config.get('PROXY_FIX_X_PROTO'),
        app.config.get('PROXY_FIX_X_HOST'),
        app.config.get('PROXY_FIX_X_PORT'),
        app.config.get('PROXY_FIX_X_PREFIX')
    ]):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config['PROXY_FIX_X_FOR'],
            x_proto=app.config['PROXY_FIX_X_PROTO'],
            x_host=app.config['PROXY_FIX_X_HOST'],
            x_port=app.config['PROXY_FIX_X_PORT'],
            x_prefix=app.config['PROXY_FIX_X_PREFIX']
        )
    
    # Inicializar extensiones
    db.init_app(app)
    csrf.init_app(app)
    
    # Configurar rate limiter
    if app.config.get('RATELIMIT_ENABLED', True):
        limiter.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
    login_manager.session_protection = 'strong'
    
    # Importar modelos
    from app.models.user import User
    from app.models.account import Account
    from app.models.transaction import Transaction
    from app.models.credit_card import CreditCard
    from app.models.reminder import Reminder
    
    # Registro de blueprints
    from app.routes import main_bp, auth_bp
    from app.controllers.reminder_controller import reminders_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(reminders_bp)

    # Beta gate: bloquear registro y acceso a login normal si beta activa y email no permitido
    if app.config.get('BETA_MODE'):
        from app.controllers.auth_controller import AuthController
        @app.before_request
        def enforce_beta():
            if request.endpoint in ('auth.login', 'auth.register') and request.method == 'POST':
                email = request.form.get('email') or request.form.get('username')
                if email and not AuthController._is_beta_email_allowed(email):
                    abort(403)
    
    # Timeout de inactividad de sesión
    @app.before_request
    def check_session_timeout():
        """Cerrar sesión si excede el tiempo de inactividad"""
        if current_user.is_authenticated:
            session.permanent = True
            last_activity = session.get('last_activity')
            if last_activity:
                try:
                    last_activity = datetime.fromisoformat(last_activity)
                    inactive_time = datetime.utcnow() - last_activity
                    timeout = app.config.get('SESSION_INACTIVITY_TIMEOUT', timedelta(minutes=30))
                    if inactive_time > timeout:
                        session.clear()
                        from flask_login import logout_user
                        logout_user()
                        from flask import flash
                        flash('Sesión cerrada por inactividad.', 'info')
                        return redirect(url_for('auth.login'))
                except (ValueError, TypeError):
                    pass
            session['last_activity'] = datetime.utcnow().isoformat()
    
    # Manejo genérico de errores (sin exponer detalles en producción)
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if app.config.get('ENV') == 'production':
            # Log completo en servidor, mensaje genérico al usuario
            logging.getLogger(__name__).exception('Internal server error')
            return render_template('errors/500.html'), 500
        else:
            # En desarrollo mostrar el error real
            raise error
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        db.session.rollback()
        if app.config.get('ENV') == 'production':
            logging.getLogger(__name__).exception('Unhandled exception')
            return render_template('errors/500.html'), 500
        else:
            raise error
    
    # Filtros personalizados para plantillas
    @app.template_filter('month_name')
    def month_name_filter(month_num):
        """Convertir número de mes a nombre en español"""
        months = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return months.get(month_num, 'Desconocido')
    
    @app.template_filter('format_currency')
    def format_currency_filter(amount):
        """Formatear cantidad como moneda"""
        return f"${amount:,.2f}"
    
    # Ensure instance folder exists for SQLite
    instance_path = os.path.join(app.root_path, '..', 'instance')
    try:
        os.makedirs(os.path.abspath(instance_path), exist_ok=True)
    except OSError as e:
        logging.getLogger(__name__).warning(f"No se pudo crear directorio instance: {e}")

    # Crear tablas
    with app.app_context():
        db.create_all()
        # Auto-migración mínima para nuevas columnas cifradas de transactions si faltan
        from sqlalchemy import inspect
        try:

            
            inspector = inspect(db.engine)
            cols = {c['name'] for c in inspector.get_columns('transactions')}
            alter_stmts = []
            wanted = {
                'description_enc': 'BLOB',
                'description_bidx': 'VARCHAR(64)',
                'notes_enc': 'BLOB',
                'notes_bidx': 'VARCHAR(64)',
                'creditor_name_enc': 'BLOB',
                'creditor_name_bidx': 'VARCHAR(64)',
                'enc_version': 'SMALLINT',
                # nuevos campos cifrados numéricos
                'amount_enc': 'BLOB',
                # en account y credit_card hay columnas en otras tablas; sólo las de transactions aquí
            }
            for col, ddl in wanted.items():
                if col not in cols:
                    # SQLite soporta ALTER TABLE ADD COLUMN sencillo
                    alter_stmts.append(f'ALTER TABLE transactions ADD COLUMN {col} {ddl}')
            with db.engine.begin() as conn:
                for stmt in alter_stmts:
                    try:
                        conn.exec_driver_sql(stmt)
                    except Exception as e:
                        logging.getLogger(__name__).debug(f"Columna ya existe o error al agregar: {stmt[:50]}... - {e}")
                # Relajar NOT NULL de columnas legacy (description, notes, creditor_name, amount) si existen en DB
                try:
                    txn_columns = inspector.get_columns('transactions')
                    legacy_targets = {c['name']: c for c in txn_columns if c['name'] in ('description','notes','creditor_name','amount')}
                    dialect_name = db.engine.dialect.name
                    for name, meta in legacy_targets.items():
                        if not meta.get('nullable', True):
                            if dialect_name == 'postgresql':
                                # Drop NOT NULL
                                conn.exec_driver_sql(f'ALTER TABLE transactions ALTER COLUMN {name} DROP NOT NULL')
                            elif dialect_name == 'sqlite':
                                # SQLite no permite DROP NOT NULL fácilmente sin recrear tabla; se omite.
                                logging.getLogger(__name__).debug(f"SQLite: no se puede relajar NOT NULL en {name}")
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Error relajando NOT NULL en transactions: {e}")
                # Auto-alter para cuentas: balance_enc y enc_version
                try:
                    acct_cols = {c['name'] for c in inspector.get_columns('accounts')}
                    acct_alters = []
                    if 'balance_enc' not in acct_cols:
                        acct_alters.append('ALTER TABLE accounts ADD COLUMN balance_enc BLOB')
                    if 'enc_version' not in acct_cols:
                        acct_alters.append('ALTER TABLE accounts ADD COLUMN enc_version SMALLINT')
                    for stmt in acct_alters:
                        try:
                            conn.exec_driver_sql(stmt)
                        except Exception as e:
                            logging.getLogger(__name__).debug(f"Error al alterar accounts: {stmt[:50]}... - {e}")
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Error en auto-migración de accounts: {e}")
                # Auto-alter para tarjetas: current_balance_enc y enc_version
                try:
                    cc_cols = {c['name'] for c in inspector.get_columns('credit_cards')}
                    cc_alters = []
                    if 'current_balance_enc' not in cc_cols:
                        cc_alters.append('ALTER TABLE credit_cards ADD COLUMN current_balance_enc BLOB')
                    if 'enc_version' not in cc_cols:
                        cc_alters.append('ALTER TABLE credit_cards ADD COLUMN enc_version SMALLINT')
                    for stmt in cc_alters:
                        try:
                            conn.exec_driver_sql(stmt)
                        except Exception as e:
                            logging.getLogger(__name__).debug(f"Error al alterar credit_cards: {stmt[:50]}... - {e}")
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Error en auto-migración de credit_cards: {e}")
                # Relajar NOT NULL en cuentas.balance y tarjetas.current_balance (Postgres)
                try:
                    if db.engine.dialect.name == 'postgresql':
                        acct_cols_meta = {c['name']: c for c in inspector.get_columns('accounts')}
                        if 'balance' in acct_cols_meta and not acct_cols_meta['balance'].get('nullable', True):
                            conn.exec_driver_sql('ALTER TABLE accounts ALTER COLUMN balance DROP NOT NULL')
                        cc_cols_meta = {c['name']: c for c in inspector.get_columns('credit_cards')}
                        if 'current_balance' in cc_cols_meta and not cc_cols_meta['current_balance'].get('nullable', True):
                            conn.exec_driver_sql('ALTER TABLE credit_cards ALTER COLUMN current_balance DROP NOT NULL')
                except Exception as e:
                    logging.getLogger(__name__).debug(f"No se pudo relajar NOT NULL en PostgreSQL: {e}")
                # Backfill de columnas cifradas numéricas si están vacías (opcional)
                try:
                    if os.environ.get('AUTO_BACKFILL_ENCRYPTED', '1') == '1':
                        from decimal import Decimal
                        from app.models.transaction import Transaction as _Tx
                        from app.models.account import Account as _Acct
                        from app.models.credit_card import CreditCard as _CC
                        active_ver = int(os.getenv('APP_ENC_ACTIVE_VERSION', '1'))

                        # Helper: existe columna en tabla
                        def _has_col(table: str, col: str) -> bool:
                            try:
                                return col in {c['name'] for c in inspector.get_columns(table)}
                            except Exception as e:
                                logging.getLogger(__name__).debug(f"Error verificando columna {col} en {table}: {e}")
                                return False

                        # 1) Rellenar transactions.amount_enc desde transactions.amount (si existe)
                        if _has_col('transactions', 'amount_enc') and _has_col('transactions', 'amount'):
                            more = True
                            while more:
                                rows = conn.exec_driver_sql(
                                    'SELECT id, amount FROM transactions WHERE amount_enc IS NULL AND amount IS NOT NULL LIMIT 500'
                                ).fetchall()
                                more = len(rows) == 500
                                if not rows:
                                    break
                                for rid, amt in rows:
                                    try:
                                        tx = _Tx.query.get(rid)
                                        if tx is None:
                                            continue
                                        # setter cifrará y fijará enc_version si falta
                                        tx.amount = float(amt)
                                    except Exception as e:
                                        # continuar con el siguiente
                                        logging.getLogger(__name__).debug(f"Error backfilling transaction {rid}: {e}")
                                try:
                                    db.session.commit()
                                except Exception as e:
                                    logging.getLogger(__name__).error(f"Error commit backfilling transactions: {e}")
                                    db.session.rollback()
                                    break

                        # 2) Asegurar enc_version en tablas con *_enc poblado
                        try:
                            if _has_col('accounts', 'enc_version') and _has_col('accounts', 'balance_enc'):
                                conn.exec_driver_sql('UPDATE accounts SET enc_version = :v WHERE enc_version IS NULL AND balance_enc IS NOT NULL', {'v': active_ver})
                        except Exception as e:
                            logging.getLogger(__name__).warning(f"Error actualizando enc_version en accounts: {e}")
                        try:
                            if _has_col('credit_cards', 'enc_version') and _has_col('credit_cards', 'current_balance_enc'):
                                conn.exec_driver_sql('UPDATE credit_cards SET enc_version = :v WHERE enc_version IS NULL AND current_balance_enc IS NOT NULL', {'v': active_ver})
                        except Exception as e:
                            logging.getLogger(__name__).warning(f"Error actualizando enc_version en credit_cards: {e}")

                        # 3) Rellenar accounts.balance_enc: si existe columna legacy 'balance', úsala; si no, recalcula
                        if _has_col('accounts', 'balance_enc'):
                            if _has_col('accounts', 'balance'):
                                rows = conn.exec_driver_sql(
                                    'SELECT id, COALESCE(balance, 0) FROM accounts WHERE balance_enc IS NULL'
                                ).fetchall()
                                for rid, bal in rows:
                                    try:
                                        acct = _Acct.query.get(rid)
                                        if acct is None:
                                            continue
                                        acct.balance = float(bal)
                                    except Exception as e:
                                        logging.getLogger(__name__).debug(f"Error backfilling account {rid}: {e}")
                                try:
                                    db.session.commit()
                                except Exception as e:
                                    logging.getLogger(__name__).error(f"Error commit backfilling accounts: {e}")
                                    db.session.rollback()
                            else:
                                # Recalcular desde transacciones si no hay columna legacy
                                ids = [r[0] for r in conn.exec_driver_sql('SELECT id FROM accounts WHERE balance_enc IS NULL').fetchall()]
                                for rid in ids:
                                    acct = _Acct.query.get(rid)
                                    if not acct:
                                        continue
                                    try:
                                        acct.update_balance()
                                    except Exception as e:
                                        logging.getLogger(__name__).debug(f"Error recalculando balance account {rid}: {e}")
                                try:
                                    db.session.commit()
                                except Exception as e:
                                    logging.getLogger(__name__).error(f"Error commit recalculando accounts: {e}")
                                    db.session.rollback()

                        # 4) Rellenar credit_cards.current_balance_enc: usar legacy si existe; si no, recalcular
                        if _has_col('credit_cards', 'current_balance_enc'):
                            if _has_col('credit_cards', 'current_balance'):
                                rows = conn.exec_driver_sql(
                                    'SELECT id, COALESCE(current_balance, 0) FROM credit_cards WHERE current_balance_enc IS NULL'
                                ).fetchall()
                                for rid, bal in rows:
                                    try:
                                        cc = _CC.query.get(rid)
                                        if not cc:
                                            continue
                                        cc.current_balance = float(bal)
                                        cc.update_minimum_payment()
                                    except Exception as e:
                                        logging.getLogger(__name__).debug(f"Error backfilling credit_card {rid}: {e}")
                                try:
                                    db.session.commit()
                                except Exception as e:
                                    logging.getLogger(__name__).error(f"Error commit backfilling credit_cards: {e}")
                                    db.session.rollback()
                            else:
                                ids = [r[0] for r in conn.exec_driver_sql('SELECT id FROM credit_cards WHERE current_balance_enc IS NULL').fetchall()]
                                for rid in ids:
                                    cc = _CC.query.get(rid)
                                    if not cc:
                                        continue
                                    try:
                                        cc.update_balance()
                                        cc.update_minimum_payment()
                                    except Exception as e:
                                        logging.getLogger(__name__).debug(f"Error recalculando credit_card {rid}: {e}")
                                try:
                                    db.session.commit()
                                except Exception as e:
                                    logging.getLogger(__name__).error(f"Error commit recalculando credit_cards: {e}")
                                    db.session.rollback()
                except Exception as e:
                    logging.getLogger(__name__).error(f"Error en backfill automático de campos cifrados: {e}")
        except Exception as e:
            logging.getLogger(__name__).error(f"Error en auto-migración de esquema: {e}", exc_info=True)
    
    # Inicializar scheduler para recordatorios
    from app.services.scheduler import init_scheduler
    init_scheduler(app)

    # Si se definió FORCE_EXTERNAL_HOST, sobre-escribimos SERVER_NAME sólo para generación
    # de URLs absolutas. Nota: esto puede afectar subdominios / testing, úsese con cuidado.
    if app.config.get('FORCE_EXTERNAL_HOST'):
        app.config['SERVER_NAME'] = app.config['FORCE_EXTERNAL_HOST']

    # Las imágenes ahora se sirven desde app/static, no se necesita ruta personalizada
    
    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))

# Crear instancia de la app
app = create_app()
