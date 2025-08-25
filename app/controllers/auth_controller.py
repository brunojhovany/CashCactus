from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
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
                flash(f'¡Bienvenido, {user.get_full_name()}!', 'success')
                return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
            flash('Usuario o contraseña incorrectos.', 'error')
        return render_template('auth/login.html')

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
