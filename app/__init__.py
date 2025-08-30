# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
import os
from sqlalchemy import inspect, text  # noqa: F401 (podrían usarse en futuras inicializaciones condicionales)
from werkzeug.middleware.proxy_fix import ProxyFix

# Avoid attribute expiration after commit so test fixtures can access model fields
# without needing an active session context (helps in unit tests where objects
# are returned outside the app context). Production impact is minimal here and
# simplifies tests.
db = SQLAlchemy(session_options={'expire_on_commit': False})
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='views/templates')
    app.config.from_object(Config)

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
    except Exception:
        pass

    # Crear tablas
    with app.app_context():
        db.create_all()
    
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
