from datetime import datetime, timedelta
from app import db

class Reminder(db.Model):
    __tablename__ = 'reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    reminder_type = db.Column(db.String(50), nullable=False)  # 'credit_card', 'debt', 'income', 'custom'
    due_date = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Float)
    is_completed = db.Column(db.Boolean, default=False)
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_days = db.Column(db.Integer)  # Días entre recurrencias
    
    # Referencias opcionales
    credit_card_id = db.Column(db.Integer, db.ForeignKey('credit_cards.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    def get_days_until_due(self):
        """Obtener días hasta el vencimiento"""
        today = datetime.now()
        
        # Handle both date and datetime objects
        if hasattr(self.due_date, 'date'):
            # It's a datetime object
            due_date = self.due_date
        else:
            # It's a date object, convert to datetime
            due_date = datetime.combine(self.due_date, datetime.min.time())
            
        return (due_date - today).days
    
    def is_overdue(self):
        """Verificar si está vencido"""
        now = datetime.now()
        
        # Handle both date and datetime objects
        if hasattr(self.due_date, 'date'):
            # It's a datetime object
            due_date = self.due_date
        else:
            # It's a date object, convert to datetime
            due_date = datetime.combine(self.due_date, datetime.min.time())
            
        return now > due_date and not self.is_completed
    
    def is_due_soon(self, days_ahead=3):
        """Verificar si vence pronto"""
        days_until = self.get_days_until_due()
        return 0 <= days_until <= days_ahead and not self.is_completed
    
    def mark_completed(self):
        """Marcar como completado"""
        self.is_completed = True
        self.completed_at = datetime.utcnow()
        
        # Si es recurrente, crear el próximo recordatorio
        if self.is_recurring and self.recurrence_days:
            self.create_next_occurrence()
    
    def create_next_occurrence(self):
        """Crear la próxima ocurrencia para recordatorios recurrentes"""
        next_reminder = Reminder(
            user_id=self.user_id,
            title=self.title,
            description=self.description,
            reminder_type=self.reminder_type,
            due_date=self.due_date + timedelta(days=self.recurrence_days),
            amount=self.amount,
            is_recurring=self.is_recurring,
            recurrence_days=self.recurrence_days,
            credit_card_id=self.credit_card_id
        )
        db.session.add(next_reminder)
    
    def get_type_display(self):
        """Obtener nombre legible del tipo de recordatorio"""
        types = {
            'credit_card': 'Tarjeta de Crédito',
            'debt': 'Deuda a Terceros',
            'income': 'Ingreso Esperado',
            'custom': 'Personalizado'
        }
        return types.get(self.reminder_type, self.reminder_type)
    
    def get_priority_class(self):
        """Obtener clase CSS según la prioridad"""
        if self.is_overdue():
            return 'danger'
        elif self.is_due_soon():
            return 'warning'
        else:
            return 'info'
    
    def __repr__(self):
        return f'<Reminder {self.title}>'
