from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from app import db
from app.utils.crypto_fields import encrypt_field, decrypt_field, get_active_enc_version

class CreditCard(db.Model):
    __tablename__ = 'credit_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    bank_name = db.Column(db.String(100))
    last_four_digits = db.Column(db.String(4))
    credit_limit = db.Column(db.Float, nullable=False)
    current_balance_enc = db.Column(db.LargeBinary, nullable=False)
    enc_version = db.Column(db.SmallInteger, default=get_active_enc_version)
    minimum_payment = db.Column(db.Float, default=0.0)
    due_date = db.Column(db.Integer)  # Día del mes (1-31)
    closing_date = db.Column(db.Integer)  # Día del mes (1-31)
    interest_rate = db.Column(db.Float, default=0.0)  # Tasa de interés mensual
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    transactions = db.relationship('Transaction', backref='credit_card', lazy=True)
    
    def get_available_credit(self):
        """Obtener crédito disponible"""
        return self.credit_limit - self.current_balance
    
    def get_utilization_percentage(self):
        """Obtener porcentaje de utilización"""
        if self.credit_limit == 0:
            return 0
        return (self.current_balance / self.credit_limit) * 100
    
    def get_next_due_date(self):
        """Obtener próxima fecha de vencimiento"""
        today = datetime.now()
        year = today.year
        month = today.month
        
        # Si ya pasó la fecha de vencimiento este mes, calcular para el próximo
        if today.day > self.due_date:
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
        
        try:
            return datetime(year, month, self.due_date)
        except ValueError:
            # Para casos como 31 de febrero, usar el último día del mes
            if month == 2:
                # Febrero
                if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    return datetime(year, month, 29)
                else:
                    return datetime(year, month, 28)
            elif month in [4, 6, 9, 11]:
                # Meses con 30 días
                return datetime(year, month, 30)
            else:
                return datetime(year, month, 31)
    
    def get_days_until_due(self):
        """Obtener días hasta el vencimiento"""
        next_due = self.get_next_due_date()
        today = datetime.now()
        return (next_due - today).days
    
    def calculate_minimum_payment(self):
        """Calcular pago mínimo (generalmente 5% del saldo)"""
        return max(self.current_balance * 0.05, 50.0) if self.current_balance > 0 else 0.0
    
    def update_minimum_payment(self):
        """Actualizar el pago mínimo"""
        self.minimum_payment = self.calculate_minimum_payment()
    
    def update_balance(self):
        """Actualizar balance basado en las transacciones"""
        from app.models.transaction import Transaction

        transactions = Transaction.query.filter_by(credit_card_id=self.id).all()
        calculated_balance = 0.0

        for transaction in transactions:
            if transaction.transaction_type == 'expense':
                # Gastos aumentan la deuda de la tarjeta
                calculated_balance += transaction.amount
            elif transaction.transaction_type == 'income':
                # Pagos reducen la deuda de la tarjeta
                calculated_balance -= transaction.amount

        self.current_balance = max(0.0, calculated_balance)  # No permitir balance negativo
        self.update_minimum_payment()
        return self.current_balance
    
    def __repr__(self):
        return f'<CreditCard {self.name}>'

    # ---- Accesores cifrados ----
    @property
    def current_balance(self) -> float:
        txt = decrypt_field(self.current_balance_enc, 'cc_current_balance', self.enc_version)
        if txt is None:
            return 0.0
        return float(Decimal(txt))

    @current_balance.setter
    def current_balance(self, value: float | int | str):
        if value is None:
            raise ValueError('current_balance no puede ser None')
        if not self.enc_version:
            self.enc_version = get_active_enc_version()
        dec = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.current_balance_enc = encrypt_field(str(dec), 'cc_current_balance', self.enc_version)
