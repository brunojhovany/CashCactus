from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.controllers.auth_controller import AuthController
from app.controllers.account_controller import AccountController
from app.controllers.transaction_controller import TransactionController
from app.controllers.credit_card_controller import CreditCardController
from app.controllers.report_controller import ReportController
from app.controllers.debt_controller import DebtController
from app.services.payment_reminder_service import PaymentReminderService
from app.services.report_service import ReportService
from datetime import datetime

# Crear blueprint principal
main_bp = Blueprint('main', __name__)

# Blueprint para autenticación (independiente)
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Rutas de autenticación
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    return AuthController.login()

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    return AuthController.register()

@auth_bp.route('/logout')
def logout():
    return AuthController.logout()

@auth_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    return AuthController.profile()

# Rutas principales
@main_bp.route('/')
def index():
    """Página de inicio"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal"""
    # Obtener resumen financiero
    current_date = datetime.now()
    monthly_summary = ReportService.get_monthly_summary(
        current_user.id, current_date.year, current_date.month
    )
    debt_summary = ReportService.get_debt_summary(current_user.id)
    net_worth = ReportService.get_net_worth(current_user.id)
    
    # Recordatorios pendientes y vencidos
    pending_reminders = PaymentReminderService.get_pending_reminders(current_user.id)[:5]  # Solo 5 más recientes
    overdue_reminders = PaymentReminderService.get_overdue_reminders(current_user.id)
    upcoming_reminders = PaymentReminderService.get_upcoming_reminders(current_user.id, 7)
    
    # Transacciones recientes
    from app.models.transaction import Transaction
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc()).limit(10).all()
    
    return render_template('dashboard.html',
                         monthly_summary=monthly_summary,
                         debt_summary=debt_summary,
                         net_worth=net_worth,
                         pending_reminders=pending_reminders,
                         overdue_reminders=overdue_reminders,
                         upcoming_reminders=upcoming_reminders,
                         recent_transactions=recent_transactions)

# Rutas de cuentas
@main_bp.route('/accounts')
@login_required
def accounts():
    return AccountController.list_accounts()

@main_bp.route('/accounts/create', methods=['GET', 'POST'])
@login_required
def create_account():
    return AccountController.create_account()

@main_bp.route('/accounts/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_account(account_id):
    return AccountController.edit_account(account_id)

@main_bp.route('/accounts/<int:account_id>/delete', methods=['POST'])
@login_required
def delete_account(account_id):
    return AccountController.delete_account(account_id)

@main_bp.route('/accounts/<int:account_id>')
@login_required
def account_details(account_id):
    return AccountController.account_details(account_id)

@main_bp.route('/accounts/<int:account_id>/transactions')
@login_required
def account_transactions(account_id):
    return TransactionController.list_account_transactions(account_id)

# Rutas de transacciones
@main_bp.route('/transactions')
@login_required
def transactions():
    return TransactionController.list_transactions()

@main_bp.route('/transactions/create', methods=['GET', 'POST'])
@login_required
def create_transaction():
    return TransactionController.create_transaction()

@main_bp.route('/transactions/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    return TransactionController.edit_transaction(transaction_id)

@main_bp.route('/transactions/<int:transaction_id>/delete', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    return TransactionController.delete_transaction(transaction_id)

# Rutas de tarjetas de crédito
@main_bp.route('/credit-cards')
@login_required
def credit_cards():
    return CreditCardController.list_credit_cards()

@main_bp.route('/credit-cards/create', methods=['GET', 'POST'])
@login_required
def create_credit_card():
    return CreditCardController.create_credit_card()

@main_bp.route('/credit-cards/<int:card_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_credit_card(card_id):
    return CreditCardController.edit_credit_card(card_id)

@main_bp.route('/credit-cards/<int:card_id>/delete', methods=['POST'])
@login_required
def delete_credit_card(card_id):
    return CreditCardController.delete_credit_card(card_id)

@main_bp.route('/credit-cards/<int:card_id>')
@login_required
def card_details(card_id):
    return CreditCardController.card_details(card_id)

@main_bp.route('/credit-cards/<int:card_id>/payment', methods=['GET', 'POST'])
@login_required
def make_payment(card_id):
    return CreditCardController.make_payment(card_id)

# Rutas de reportes
@main_bp.route('/reports/monthly')
@login_required
def monthly_report():
    return ReportController.monthly_report()

@main_bp.route('/reports/quarterly')
@login_required
def quarterly_report():
    return ReportController.quarterly_report()

@main_bp.route('/reports/annual')
@login_required
def annual_summary():
    return ReportController.annual_summary()

@main_bp.route('/reports/debt-analysis')
@login_required
def debt_analysis():
    return ReportController.debt_analysis()

@main_bp.route('/reports/income-by-account')
@login_required
def income_by_account_report():
    return ReportController.income_by_account_report()

@main_bp.route('/reports/export')
@login_required
def export_data():
    return ReportController.export_data()

# Rutas de recordatorios
@main_bp.route('/reminders')
@login_required
def reminders():
    """Página de recordatorios"""
    pending_reminders = PaymentReminderService.get_pending_reminders(current_user.id)
    overdue_reminders = PaymentReminderService.get_overdue_reminders(current_user.id)
    upcoming_reminders = PaymentReminderService.get_upcoming_reminders(current_user.id, 30)
    
    return render_template('reminders/list.html',
                         pending_reminders=pending_reminders,
                         overdue_reminders=overdue_reminders,
                         upcoming_reminders=upcoming_reminders)

@main_bp.route('/reminders/create', methods=['GET', 'POST'])
@login_required
def create_reminder():
    """Crear recordatorio personalizado"""
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            description = request.form.get('description')
            due_date_str = request.form.get('due_date')
            amount = request.form.get('amount')
            reminder_type = request.form.get('reminder_type', 'custom')
            is_recurring = request.form.get('is_recurring') == 'on'
            recurrence_days = request.form.get('recurrence_days')
            
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            amount_float = float(amount) if amount else None
            recurrence_days_int = int(recurrence_days) if recurrence_days and is_recurring else None
            
            PaymentReminderService.create_custom_reminder(
                user_id=current_user.id,
                title=title,
                description=description,
                due_date=due_date,
                amount=amount_float,
                reminder_type=reminder_type,
                is_recurring=is_recurring,
                recurrence_days=recurrence_days_int
            )
            
            flash('Recordatorio creado exitosamente.', 'success')
            return redirect(url_for('main.reminders'))
            
        except Exception as e:
            flash('Error al crear el recordatorio.', 'error')
    
    return render_template('reminders/create.html')

@main_bp.route('/reminders/<int:reminder_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_reminder(reminder_id):
    """Editar recordatorio"""
    from app.models.reminder import Reminder
    from app import db
    
    reminder = Reminder.query.get_or_404(reminder_id)
    
    if request.method == 'POST':
        try:
            reminder.title = request.form['title']
            reminder.description = request.form.get('description', '')
            reminder.due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
            reminder.amount = float(request.form['amount'])
            
            db.session.commit()
            flash('Recordatorio actualizado exitosamente.', 'success')
            return redirect(url_for('main.reminders'))
            
        except Exception as e:
            flash('Error al actualizar el recordatorio.', 'error')
    
    return render_template('reminders/edit.html', reminder=reminder)

@main_bp.route('/reminders/<int:reminder_id>/complete', methods=['POST'])
@login_required
def complete_reminder(reminder_id):
    """Marcar recordatorio como completado"""
    success = PaymentReminderService.mark_reminder_completed(reminder_id)
    if success:
        flash('Recordatorio marcado como completado.', 'success')
    else:
        flash('Error al completar el recordatorio.', 'error')
    
    return redirect(url_for('main.reminders'))

@main_bp.route('/reminders/<int:reminder_id>/delete', methods=['POST'])
@login_required
def delete_reminder(reminder_id):
    """Eliminar recordatorio"""
    success = PaymentReminderService.delete_reminder(reminder_id)
    if success:
        flash('Recordatorio eliminado exitosamente.', 'success')
    else:
        flash('Error al eliminar el recordatorio.', 'error')
    
    return redirect(url_for('main.reminders'))

# ================================
# RUTAS DE DEUDAS
# ================================

@main_bp.route('/debts')
@login_required
def debt_accounts():
    """Listar cuentas de deuda"""
    return DebtController.list_debt_accounts()

@main_bp.route('/debts/create', methods=['GET', 'POST'])
@login_required
def create_debt_account():
    """Crear nueva cuenta de deuda"""
    return DebtController.create_debt_account()

@main_bp.route('/debts/<int:debt_id>')
@login_required
def debt_detail(debt_id):
    """Ver detalles de una cuenta de deuda"""
    return DebtController.debt_detail(debt_id)

@main_bp.route('/debts/<int:debt_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_debt_account(debt_id):
    """Editar cuenta de deuda"""
    return DebtController.edit_debt_account(debt_id)

@main_bp.route('/debts/payment', methods=['GET', 'POST'])
@login_required
def make_debt_payment():
    """Realizar pago a deuda"""
    return DebtController.make_debt_payment()

@main_bp.route('/debts/apply-interests', methods=['POST'])
@login_required
def apply_debt_interests():
    """Aplicar intereses mensuales a todas las deudas"""
    return DebtController.apply_interests()
