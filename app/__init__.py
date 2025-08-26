# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
import os

# Avoid attribute expiration after commit so test fixtures can access model fields
# without needing an active session context (helps in unit tests where objects
# are returned outside the app context). Production impact is minimal here and
# simplifies tests.
db = SQLAlchemy(session_options={'expire_on_commit': False})
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='views/templates')
    app.config.from_object(Config)
    
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

    # Mitigar caching de respuestas autenticadas en navegadores compartidos
    @app.after_request
    def set_secure_headers(resp):
        resp.headers.setdefault('Cache-Control', 'no-store, no-cache, must-revalidate, private, max-age=0')
        resp.headers.setdefault('Pragma', 'no-cache')
        resp.headers.setdefault('Expires', '0')
        # Indicar al app si viene detrás de proxy HTTPS para urls absolutas
        if request.headers.get('X-Forwarded-Proto', '') == 'https':
            resp.headers.setdefault('Content-Security-Policy', "default-src 'self'")
        return resp

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

    # Las imágenes ahora se sirven desde app/static, no se necesita ruta personalizada
    
    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))

# Crear instancia de la app
app = create_app()
