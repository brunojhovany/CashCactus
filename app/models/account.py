from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app import db

class Account(db.Model):
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)  # 'checking', 'savings', 'investment', 'debt'
    balance = db.Column(db.Float, default=0.0)
    bank_name = db.Column(db.String(100))
    # Deprecated sensitive field: previously stored full account numbers.
    # Now unused and should remain NULL. Plan: create migration to DROP COLUMN accounts.account_number.
    # Kept only so existing databases still map; application code no longer reads/writes it.
    account_number = db.Column(db.String(50))  # DO NOT USE
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Campos específicos para cuentas de deuda
    is_debt_account = db.Column(db.Boolean, default=False)
    interest_rate = db.Column(db.Float, default=0.0)  # Tasa de interés anual (%)
    creditor_name = db.Column(db.String(200))  # Nombre del acreedor
    original_debt_amount = db.Column(db.Float, default=0.0)  # Deuda original
    minimum_payment = db.Column(db.Float, default=0.0)  # Pago mínimo mensual
    payment_due_day = db.Column(db.Integer, default=1)  # Día de vencimiento del mes (1-31)
    last_interest_calculation = db.Column(db.DateTime)  # Última vez que se calcularon intereses
    status = db.Column(db.String(50), default='active')  # active, paid_off, defaulted
    notes = db.Column(db.Text)  # Notas adicionales
    
    # Campos para cuentas de inversión y ahorros
    generates_interest = db.Column(db.Boolean, default=False)  # Si genera intereses/rendimientos
    investment_type = db.Column(db.String(100))  # Tipo de inversión (ahorro, plazo fijo, acciones, etc.)
    maturity_date = db.Column(db.Date)  # Fecha de vencimiento para inversiones a plazo
    compound_frequency = db.Column(db.String(20), default='monthly')  # monthly, quarterly, annually
    
    # Relaciones
    transactions = db.relationship('Transaction', 
                                  foreign_keys='Transaction.account_id',
                                  backref='account', 
                                  lazy=True)
    transfer_transactions = db.relationship('Transaction',
                                          foreign_keys='Transaction.transfer_to_account_id',
                                          backref='transfer_to_account',
                                          lazy=True)
    
    def get_monthly_balance(self, year, month):
        """Obtener balance al final del mes especificado"""
        from app.models.transaction import Transaction
        
        # Transacciones hasta el final del mes
        end_of_month = datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
        transactions = Transaction.query.filter(
            Transaction.account_id == self.id,
            Transaction.user_id == self.user_id,
            Transaction.date < end_of_month
        ).all()
        
        monthly_balance = 0.0
        for transaction in transactions:
            if transaction.transaction_type == 'income':
                monthly_balance += transaction.amount
            else:
                monthly_balance -= transaction.amount
                
        return monthly_balance
    
    def calculate_current_balance(self):
        """Calcular el balance actual basado en todas las transacciones"""
        from app.models.transaction import Transaction
        
        transactions = Transaction.query.filter_by(account_id=self.id).all()
        
        # Para cuentas de deuda, empezar con el monto original
        if self.is_debt_account:
            calculated_balance = self.original_debt_amount or 0.0
            # Para deudas, los pagos (expense) reducen la deuda
            for transaction in transactions:
                if transaction.transaction_type == 'expense':
                    calculated_balance -= transaction.amount  # Pagos reducen la deuda
                elif transaction.transaction_type == 'income':
                    calculated_balance += transaction.amount  # Cargos aumentan la deuda
        else:
            # Para cuentas normales, lógica tradicional
            calculated_balance = 0.0
            for transaction in transactions:
                if transaction.transaction_type == 'income':
                    calculated_balance += transaction.amount
                else:  # expense or transfer
                    calculated_balance -= transaction.amount
                
        return calculated_balance
    
    def update_balance(self):
        """Actualizar el balance de la cuenta basado en las transacciones"""
        self.balance = self.calculate_current_balance()
        return self.balance
    
    def get_account_type_display(self):
        """Obtener nombre legible del tipo de cuenta"""
        types = {
            'checking': 'Cuenta Corriente',
            'savings': 'Cuenta de Ahorros',
            'investment': 'Inversión',
            'debt': 'Cuenta de Deuda'
        }
        return types.get(self.account_type, self.account_type)
    
    # Propiedades de conveniencia para deudas
    @property
    def original_amount(self):
        """Alias para original_debt_amount para compatibilidad con templates"""
        return self.original_debt_amount
    
    @original_amount.setter
    def original_amount(self, value):
        """Setter para original_amount"""
        self.original_debt_amount = value
    
    @property
    def current_balance(self):
        """Alias para balance para compatibilidad con templates de deuda"""
        return abs(self.balance) if self.balance < 0 else self.balance
    
    def calculate_monthly_interest(self):
        """Calcular interés mensual para cuentas de deuda"""
        if not self.is_debt_account or self.interest_rate == 0:
            return 0.0
        
        # Solo calcular intereses si hay deuda pendiente (balance negativo para deudas)
        if self.balance >= 0:
            return 0.0
        
        # Calcular interés mensual sobre el balance actual
        monthly_rate = self.interest_rate / 100 / 12  # Convertir % anual a decimal mensual
        interest_amount = abs(self.balance) * monthly_rate
        
        return interest_amount
    
    def apply_monthly_interest(self):
        """Aplicar interés mensual y crear transacción automática"""
        if not self.is_debt_account:
            return None
        
        interest_amount = self.calculate_monthly_interest()
        
        if interest_amount > 0:
            from app.models.transaction import Transaction
            
            # Crear transacción de interés
            interest_transaction = Transaction(
                user_id=self.user_id,
                account_id=self.id,
                amount=interest_amount,
                description=f'Interés mensual - {self.creditor_name or self.name}',
                category='debt_interest',
                transaction_type='expense',
                date=datetime.utcnow(),
                notes=f'Interés calculado automáticamente - Tasa: {self.interest_rate}% anual',
                is_automatic=True
            )
            
            db.session.add(interest_transaction)
            
            # Actualizar balance (para deudas, gastos aumentan el balance negativo)
            self.balance -= interest_amount
            self.last_interest_calculation = datetime.utcnow()
            
            return interest_transaction
        
        return None
    
    def calculate_debt_projection(self, months=12):
        """Calcular proyección de deuda con pagos mínimos"""
        if not self.is_debt_account:
            return []
        
        projections = []
        current_balance = abs(self.balance)  # Convertir a positivo para cálculos
        monthly_rate = self.interest_rate / 100 / 12
        
        for month in range(1, months + 1):
            # Aplicar interés
            interest = current_balance * monthly_rate
            current_balance += interest
            
            # Aplicar pago mínimo
            if self.minimum_payment > 0:
                payment = min(self.minimum_payment, current_balance)
                current_balance -= payment
            else:
                payment = 0
            
            projections.append({
                'month': month,
                'starting_balance': current_balance + payment - interest,
                'interest': interest,
                'payment': payment,
                'ending_balance': current_balance
            })
        
        return projections
    
    def get_next_payment_due_date(self):
        """Obtener próxima fecha de vencimiento de pago"""
        if not self.is_debt_account:
            return None
        
        today = datetime.utcnow().date()
        
        # Intentar el día de vencimiento en el mes actual
        try:
            next_due = datetime(today.year, today.month, self.payment_due_day).date()
            if next_due <= today:
                # Si ya pasó este mes, usar el próximo mes
                next_month = today.replace(day=1) + relativedelta(months=1)
                next_due = datetime(next_month.year, next_month.month, self.payment_due_day).date()
        except ValueError:
            # Si el día no existe en el mes (ej: 31 en febrero), usar el último día del mes
            next_month = today.replace(day=1) + relativedelta(months=1)
            next_due = (next_month + relativedelta(months=1) - timedelta(days=1)).date()
        
        return next_due
    
    def is_payment_overdue(self):
        """Verificar si hay pagos vencidos"""
        if not self.is_debt_account:
            return False
        
        next_due = self.get_next_payment_due_date()
        if not next_due:
            return False
        
        return datetime.utcnow().date() > next_due
    
    def calculate_investment_interest(self):
        """Calcular interés de inversión/ahorro"""
        if not self.generates_interest or self.interest_rate == 0 or self.balance <= 0:
            return 0.0
        
        # Calcular según la frecuencia de capitalización
        if self.compound_frequency == 'monthly':
            periods_per_year = 12
        elif self.compound_frequency == 'quarterly':
            periods_per_year = 4
        elif self.compound_frequency == 'annually':
            periods_per_year = 1
        else:
            periods_per_year = 12  # Default mensual
        
        # Calcular interés del período
        period_rate = self.interest_rate / 100 / periods_per_year
        interest_amount = self.balance * period_rate
        
        return interest_amount
    
    def apply_investment_interest(self, period_type='monthly'):
        """Aplicar interés de inversión y crear transacción automática"""
        if not self.generates_interest or self.is_debt_account:
            return None
        
        # Verificar si corresponde aplicar según la frecuencia
        if not self._should_apply_interest(period_type):
            return None
        
        interest_amount = self.calculate_investment_interest()
        
        if interest_amount > 0:
            from app.models.transaction import Transaction
            
            # Crear transacción de rendimiento
            interest_transaction = Transaction(
                user_id=self.user_id,
                account_id=self.id,
                amount=interest_amount,
                description=f'Rendimiento {period_type} - {self.investment_type or self.get_account_type_display()}',
                category='investment_income',
                transaction_type='income',
                date=datetime.utcnow(),
                notes=f'Rendimiento calculado automáticamente - Tasa: {self.interest_rate}% anual',
                is_automatic=True
            )
            
            db.session.add(interest_transaction)
            
            # Actualizar balance (para inversiones, los rendimientos aumentan el balance)
            self.balance += interest_amount
            self.last_interest_calculation = datetime.utcnow()
            
            return interest_transaction
        
        return None
    
    def _should_apply_interest(self, period_type):
        """Verificar si debe aplicarse el interés según la frecuencia configurada"""
        if not self.last_interest_calculation:
            return True
        
        last_calc = self.last_interest_calculation.date()
        today = datetime.utcnow().date()
        
        if self.compound_frequency == 'monthly' and period_type == 'monthly':
            # Aplicar si ha pasado al menos un mes
            return (today.year > last_calc.year or 
                   (today.year == last_calc.year and today.month > last_calc.month))
        elif self.compound_frequency == 'quarterly' and period_type == 'quarterly':
            # Aplicar si han pasado al menos 3 meses
            months_diff = (today.year - last_calc.year) * 12 + (today.month - last_calc.month)
            return months_diff >= 3
        elif self.compound_frequency == 'annually' and period_type == 'annually':
            # Aplicar si ha pasado al menos un año
            return today.year > last_calc.year
        
        return False
    
    def calculate_investment_projection(self, months=12):
        """Calcular proyección de crecimiento de inversión"""
        if not self.generates_interest:
            return []
        
        projections = []
        current_balance = self.balance
        
        # Determinar cuántas veces se aplica interés por año
        if self.compound_frequency == 'monthly':
            compounds_per_year = 12
        elif self.compound_frequency == 'quarterly':
            compounds_per_year = 4
        elif self.compound_frequency == 'annually':
            compounds_per_year = 1
        else:
            compounds_per_year = 12
        
        period_rate = self.interest_rate / 100 / compounds_per_year
        
        for month in range(1, months + 1):
            # Calcular si corresponde aplicar interés este mes
            if self.compound_frequency == 'monthly' or \
               (self.compound_frequency == 'quarterly' and month % 3 == 0) or \
               (self.compound_frequency == 'annually' and month % 12 == 0):
                
                interest = current_balance * period_rate
                current_balance += interest
            else:
                interest = 0
            
            projections.append({
                'month': month,
                'starting_balance': current_balance - interest,
                'interest': interest,
                'ending_balance': current_balance
            })
        
        return projections
    
    def get_investment_yield_info(self):
        """Obtener información del rendimiento de la inversión"""
        if not self.generates_interest:
            return None
        
        # Calcular rendimiento anual efectivo
        if self.compound_frequency == 'monthly':
            effective_rate = (1 + self.interest_rate/100/12)**12 - 1
        elif self.compound_frequency == 'quarterly':
            effective_rate = (1 + self.interest_rate/100/4)**4 - 1
        elif self.compound_frequency == 'annually':
            effective_rate = self.interest_rate/100
        else:
            effective_rate = self.interest_rate/100
        
        return {
            'nominal_rate': self.interest_rate,
            'effective_annual_rate': effective_rate * 100,
            'monthly_yield': self.calculate_investment_interest(),
            'compound_frequency': self.compound_frequency,
            'investment_type': self.investment_type
        }
    
    def __repr__(self):
        return f'<Account {self.name}>'
