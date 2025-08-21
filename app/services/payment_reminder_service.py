from datetime import datetime, timedelta
from app import db
from app.models.reminder import Reminder
from app.models.credit_card import CreditCard

class PaymentReminderService:
    """Servicio para manejar recordatorios de pagos"""
    
    @staticmethod
    def create_credit_card_reminders(user_id):
        """Crear recordatorios para todas las tarjetas de crédito del usuario"""
        credit_cards = CreditCard.query.filter_by(user_id=user_id, is_active=True).all()
        
        for card in credit_cards:
            # Verificar si ya existe un recordatorio para esta tarjeta
            existing_reminder = Reminder.query.filter_by(
                user_id=user_id,
                credit_card_id=card.id,
                is_completed=False
            ).first()
            
            if not existing_reminder:
                due_date = card.get_next_due_date()
                
                # Crear recordatorio 3 días antes del vencimiento
                reminder_date = due_date - timedelta(days=3)
                
                reminder = Reminder(
                    user_id=user_id,
                    title=f"Pago de {card.name}",
                    description=f"Pago mínimo: ${card.minimum_payment:.2f}\nSaldo actual: ${card.current_balance:.2f}",
                    reminder_type='credit_card',
                    due_date=reminder_date,
                    amount=card.minimum_payment,
                    is_recurring=True,
                    recurrence_days=30,  # Mensual
                    credit_card_id=card.id
                )
                
                db.session.add(reminder)
        
        db.session.commit()
    
    @staticmethod
    def create_custom_reminder(user_id, title, description, due_date, amount=None, 
                             reminder_type='custom', is_recurring=False, recurrence_days=None):
        """Crear un recordatorio personalizado"""
        reminder = Reminder(
            user_id=user_id,
            title=title,
            description=description,
            reminder_type=reminder_type,
            due_date=due_date,
            amount=amount,
            is_recurring=is_recurring,
            recurrence_days=recurrence_days
        )
        
        db.session.add(reminder)
        db.session.commit()
        return reminder
    
    @staticmethod
    def get_pending_reminders(user_id):
        """Obtener recordatorios pendientes para un usuario"""
        return Reminder.query.filter_by(
            user_id=user_id,
            is_completed=False
        ).order_by(Reminder.due_date).all()
    
    @staticmethod
    def get_overdue_reminders(user_id):
        """Obtener recordatorios vencidos para un usuario"""
        return Reminder.query.filter(
            Reminder.user_id == user_id,
            Reminder.is_completed == False,
            Reminder.due_date < datetime.now()
        ).order_by(Reminder.due_date).all()
    
    @staticmethod
    def get_upcoming_reminders(user_id, days_ahead=7):
        """Obtener recordatorios próximos a vencer"""
        future_date = datetime.now() + timedelta(days=days_ahead)
        
        return Reminder.query.filter(
            Reminder.user_id == user_id,
            Reminder.is_completed == False,
            Reminder.due_date.between(datetime.now(), future_date)
        ).order_by(Reminder.due_date).all()
    
    @staticmethod
    def mark_reminder_completed(reminder_id):
        """Marcar un recordatorio como completado"""
        reminder = Reminder.query.get(reminder_id)
        if reminder:
            reminder.mark_completed()
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def update_all_credit_card_reminders():
        """Actualizar todos los recordatorios de tarjetas de crédito"""
        # Actualizar pagos mínimos de todas las tarjetas
        credit_cards = CreditCard.query.filter_by(is_active=True).all()
        for card in credit_cards:
            card.update_minimum_payment()
        
        # Crear recordatorios faltantes
        users_with_cards = db.session.query(CreditCard.user_id).distinct().all()
        for (user_id,) in users_with_cards:
            PaymentReminderService.create_credit_card_reminders(user_id)
        
        db.session.commit()
    
    @staticmethod
    def delete_reminder(reminder_id):
        """Eliminar un recordatorio"""
        reminder = Reminder.query.get(reminder_id)
        if reminder:
            db.session.delete(reminder)
            db.session.commit()
            return True
        return False
