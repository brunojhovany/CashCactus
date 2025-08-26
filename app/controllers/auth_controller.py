from flask import render_template, request, redirect, url_for, flash, session, current_app
import os
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin
from app.models.user import User
from app import db

class AuthController:
    @staticmethod
    def login():
        """Manejar inicio de sesión"""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            if not username or not password:
                flash('Por favor, completa todos los campos.', 'error')
                return render_template('auth/login.html')

            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                # Regenerar identificador de sesión (mitigar fijación)
                session.clear()
                login_user(user, remember=('remember' in request.form))
                next_page = request.args.get('next')
                # Validar que next sea URL interna para evitar open redirect
                def is_safe_url(target):
                    if not target:
                        return False
                    ref_url = urlparse(request.host_url)
                    test_url = urlparse(urljoin(request.host_url, target))
                    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
                if not is_safe_url(next_page):
                    next_page = None
                flash(f'¡Bienvenido, {user.get_full_name()}!', 'success')
                return redirect(url_for(next_page) or url_for('main.dashboard'))
            flash('Usuario o contraseña incorrectos.', 'error')
        return render_template('auth/login.html')

    # ---------------- GOOGLE OAUTH ----------------
    @staticmethod
    def login_google_start():
        """Redirigir a Google para autenticación"""
        from authlib.integrations.flask_client import OAuth
        oauth = OAuth(current_app)
        # Validar que haya credenciales configuradas
        if not current_app.config.get('GOOGLE_CLIENT_ID') or not current_app.config.get('GOOGLE_CLIENT_SECRET'):
            flash('Autenticación con Google no configurada.', 'error')
            return redirect(url_for('auth.login'))
        AuthController._ensure_google_client(oauth)
        redirect_uri = url_for('auth.login_google_callback', _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    @staticmethod
    def login_google_callback():
        from authlib.integrations.flask_client import OAuth
        from app import db
        oauth = OAuth(current_app)
        AuthController._ensure_google_client(oauth)
        token = oauth.google.authorize_access_token()
        userinfo = token.get('userinfo') or oauth.google.parse_id_token(token)
        if not userinfo:
            flash('No se pudo obtener información de Google.', 'error')
            return redirect(url_for('auth.login'))
        email = userinfo.get('email')
        sub = userinfo.get('sub')
        given_name = userinfo.get('given_name', '')
        family_name = userinfo.get('family_name', '')
        picture_url = userinfo.get('picture')

        from app.models.user import User
        user = User.query.filter_by(oauth_provider='google', oauth_sub=sub).first()
        if not user:
            # Buscar por email existente
            user = User.query.filter_by(email=email).first()
            if user:
                user.oauth_provider = 'google'
                user.oauth_sub = sub
            else:
                # En beta: validar permisos antes de crear
                if current_app.config.get('BETA_MODE'):
                    if not AuthController._is_beta_email_allowed(email):
                        flash('Acceso restringido (beta cerrada).', 'error')
                        return redirect(url_for('auth.login'))
                user = User(
                    username=email.split('@')[0],
                    email=email,
                    first_name=given_name or 'Usuario',
                    last_name=family_name or '',
                    oauth_provider='google',
                    oauth_sub=sub,
                    is_beta_allowed=True if current_app.config.get('BETA_MODE') else False,
                    monthly_income=0.0,
                    avatar_url=picture_url[:300] if picture_url else None
                )
                # Establecer un password aleatorio (no usado) para cumplir no-null
                user.set_password(os.urandom(16).hex())
                db.session.add(user)
        # En beta, si el usuario existe sin permiso, validar
        if current_app.config.get('BETA_MODE') and not AuthController._is_beta_email_allowed(email):
            flash('Acceso restringido (beta cerrada).', 'error')
            return redirect(url_for('auth.login'))
        # Actualizar avatar si no está guardado
        if picture_url and (not user.avatar_url):
            user.avatar_url = picture_url[:300]
        db.session.commit()
        session.clear()
        login_user(user)
        flash('Inicio de sesión con Google exitoso.', 'success')
        return redirect(url_for('main.dashboard'))

    @staticmethod
    def _is_beta_email_allowed(email):
        email = (email or '').lower().strip()
        cfg = current_app.config
        allowed_emails = cfg.get('BETA_ALLOWED_EMAILS') or set()
        allowed_domain = cfg.get('BETA_ALLOWED_DOMAIN')
        if not cfg.get('BETA_MODE'):
            return True
        if email in allowed_emails:
            return True
        if allowed_domain and email.endswith('@' + allowed_domain):
            return True
        return False

    @staticmethod
    def _ensure_google_client(oauth):
        """Register google client once using internal registry dict."""
        # oauth._clients is a dict internal in Authlib; safer is to try/except attribute access
        try:
            _ = oauth.google  # triggers attribute resolution if registered
            return
        except Exception:
            pass
        oauth.register(
            name='google',
            client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET'),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

    @staticmethod
    def register():
        """Manejar registro de usuario"""
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            monthly_income = request.form.get('monthly_income', 0)

            if not all([username, email, password, first_name, last_name]):
                flash('Por favor, completa todos los campos obligatorios.', 'error')
                return render_template('auth/register.html')
            if password != confirm_password:
                flash('Las contraseñas no coinciden.', 'error')
                return render_template('auth/register.html')
            if len(password) < 6:
                flash('La contraseña debe tener al menos 6 caracteres.', 'error')
                return render_template('auth/register.html')
            if User.query.filter_by(username=username).first():
                flash('El nombre de usuario ya está en uso.', 'error')
                return render_template('auth/register.html')
            if User.query.filter_by(email=email).first():
                flash('El email ya está registrado.', 'error')
                return render_template('auth/register.html')
            try:
                user = User(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    monthly_income=float(monthly_income) if monthly_income else 0.0
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash('¡Registro exitoso! Bienvenido a tu aplicación de finanzas.', 'success')
                return redirect(url_for('main.dashboard'))
            except Exception:
                db.session.rollback()
                flash('Error al crear la cuenta. Intenta nuevamente.', 'error')
                return render_template('auth/register.html')
        return render_template('auth/register.html')

    @staticmethod
    @login_required
    def logout():
        """Cerrar sesión"""
        session.clear()
        logout_user()
        flash('Has cerrado sesión exitosamente.', 'info')
        return redirect(url_for('auth.login'))

    @staticmethod
    @login_required
    def profile():
        """Mostrar y editar perfil de usuario"""
        if request.method == 'POST':
            try:
                current_user.first_name = request.form.get('first_name')
                current_user.last_name = request.form.get('last_name')
                current_user.email = request.form.get('email')
                current_user.monthly_income = float(request.form.get('monthly_income', 0))
                new_password = request.form.get('new_password')
                if new_password:
                    current_password = request.form.get('current_password')
                    if not current_user.check_password(current_password):
                        flash('Contraseña actual incorrecta.', 'error')
                        return render_template('auth/profile.html', user=current_user)
                    if len(new_password) < 6:
                        flash('La nueva contraseña debe tener al menos 6 caracteres.', 'error')
                        return render_template('auth/profile.html', user=current_user)
                    current_user.set_password(new_password)
                db.session.commit()
                flash('Perfil actualizado exitosamente.', 'success')
            except Exception:
                db.session.rollback()
                flash('Error al actualizar el perfil.', 'error')
        return render_template('auth/profile.html', user=current_user)
