from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from app.models.reminder import Reminder
from app import db
from app.services.payment_reminder_service import PaymentReminderService

reminders_bp = Blueprint('reminders', __name__, url_prefix='/reminders')


@reminders_bp.route('/', methods=['GET'])
@login_required
def list_reminders():
    """Listar recordatorios (pendientes, vencidos y próximos)."""
    pending_reminders = PaymentReminderService.get_pending_reminders(current_user.id)
    overdue_reminders = PaymentReminderService.get_overdue_reminders(current_user.id)
    upcoming_reminders = PaymentReminderService.get_upcoming_reminders(current_user.id, 30)

    return render_template('reminders/list.html',
                           pending_reminders=pending_reminders,
                           overdue_reminders=overdue_reminders,
                           upcoming_reminders=upcoming_reminders)


@reminders_bp.route('/create', methods=['GET', 'POST'])
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

            if not title or not due_date_str:
                flash('Título y fecha son obligatorios.', 'error')
                return render_template('reminders/create.html')

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
            return redirect(url_for('reminders.list_reminders'))

        except ValueError:
            flash('Datos inválidos. Verifica montos y fecha.', 'error')
        except Exception:
            flash('Error al crear el recordatorio.', 'error')

    return render_template('reminders/create.html')


@reminders_bp.route('/<int:reminder_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_reminder(reminder_id):
    """Editar recordatorio existente"""
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        try:
            reminder.title = request.form.get('title')
            reminder.description = request.form.get('description')
            due_date_str = request.form.get('due_date')
            amount_str = request.form.get('amount')
            is_recurring = request.form.get('is_recurring') == 'on'
            recurrence_days = request.form.get('recurrence_days')

            if due_date_str:
                reminder.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            reminder.amount = float(amount_str) if amount_str else None
            reminder.is_recurring = is_recurring
            reminder.recurrence_days = int(recurrence_days) if (recurrence_days and is_recurring) else None

            db.session.commit()
            flash('Recordatorio actualizado exitosamente.', 'success')
            return redirect(url_for('reminders.list_reminders'))
        except ValueError:
            db.session.rollback()
            flash('Datos inválidos. Verifica montos y fecha.', 'error')
        except Exception:
            db.session.rollback()
            flash('Error al actualizar el recordatorio.', 'error')

    return render_template('reminders/edit.html', reminder=reminder)


@reminders_bp.route('/<int:reminder_id>/complete', methods=['POST'])
@login_required
def complete_reminder(reminder_id):
    """Marcar recordatorio como completado"""
    from flask import abort
    try:
        PaymentReminderService.mark_reminder_completed(reminder_id)
        flash('Recordatorio completado.', 'success')
        return redirect(url_for('reminders.list_reminders'))
    except Exception:
        # Si el servicio aborta con 404 por falta de propiedad, propagar
        # Otros errores: 400 genérico
        abort(404)


@reminders_bp.route('/<int:reminder_id>/delete', methods=['POST'])
@login_required
def delete_reminder(reminder_id):
    """Eliminar recordatorio"""
    from flask import abort
    try:
        PaymentReminderService.delete_reminder(reminder_id)
        flash('Recordatorio eliminado.', 'success')
        return redirect(url_for('reminders.list_reminders'))
    except Exception:
        abort(404)


# Opcional: endpoint JSON rápido (podría ampliarse)
@reminders_bp.route('/api', methods=['GET'])
@login_required
def reminders_api_list():
    reminders = Reminder.query.filter_by(user_id=current_user.id).order_by(Reminder.due_date).all()
    return {
        'reminders': [
            {
                'id': r.id,
                'title': r.title,
                'due_date': r.due_date.isoformat() if r.due_date else None,
                'amount': r.amount,
                'type': r.reminder_type,
                'is_completed': r.is_completed
            } for r in reminders
        ]
    }
