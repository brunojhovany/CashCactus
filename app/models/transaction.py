from datetime import datetime
from app import db

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    credit_card_id = db.Column(db.Integer, db.ForeignKey('credit_cards.id'), nullable=True)
    
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'income', 'expense', 'transfer'
    date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    # Para transferencias entre cuentas
    transfer_to_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    
    # Para pagos de deudas a terceros
    creditor_name = db.Column(db.String(100))  # Nombre del acreedor
    is_debt_payment = db.Column(db.Boolean, default=False)
    
    # Para transacciones automáticas (como intereses)
    is_automatic = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_category_display(self):
        """Obtener nombre legible de la categoría"""
        categories = {
            'food': 'Alimentación',
            'transport': 'Transporte',
            'entertainment': 'Entretenimiento',
            'utilities': 'Servicios',
            'healthcare': 'Salud',
            'shopping': 'Compras',
            'education': 'Educación',
            'travel': 'Viajes',
            'debt_payment': 'Pago de Deudas',
            'debt_interest': 'Interés de Deuda',
            'investment_income': 'Rendimiento de Inversión',
            'salary': 'Salario',
            'freelance': 'Trabajos Independientes',
            'investment': 'Inversiones',
            'other': 'Otros'
        }
        return categories.get(self.category, self.category)
    
    def get_type_display(self):
        """Obtener nombre legible del tipo de transacción"""
        types = {
            'income': 'Ingreso',
            'expense': 'Gasto',
            'transfer': 'Transferencia'
        }
        return types.get(self.transaction_type, self.transaction_type)
    
    def update_affected_balances(self):
        """Actualizar balances de todas las cuentas/tarjetas afectadas por esta transacción"""
        from app.models.account import Account
        from app.models.credit_card import CreditCard
        
        # Actualizar cuenta principal si existe
        if self.account_id:
            account = Account.query.get(self.account_id)
            if account:
                account.update_balance()
        
        # Actualizar tarjeta de crédito si existe
        if self.credit_card_id:
            credit_card = CreditCard.query.get(self.credit_card_id)
            if credit_card:
                credit_card.update_balance()
        
        # Actualizar cuenta destino si es transferencia
        if self.transfer_to_account_id:
            target_account = Account.query.get(self.transfer_to_account_id)
            if target_account:
                target_account.update_balance()
    
    def delete_with_cascade_update(self):
        """Eliminar transacción y actualizar balances automáticamente"""
        from app import db
        
        # Guardar referencias antes de eliminar
        account_id = self.account_id
        credit_card_id = self.credit_card_id
        transfer_to_account_id = self.transfer_to_account_id
        
        # Eliminar la transacción
        db.session.delete(self)
        
        # Actualizar balances de las cuentas afectadas
        if account_id:
            from app.models.account import Account
            account = Account.query.get(account_id)
            if account:
                account.update_balance()
        
        if credit_card_id:
            from app.models.credit_card import CreditCard
            credit_card = CreditCard.query.get(credit_card_id)
            if credit_card:
                credit_card.update_balance()
        
        if transfer_to_account_id:
            from app.models.account import Account
            target_account = Account.query.get(transfer_to_account_id)
            if target_account:
                target_account.update_balance()
    
    @staticmethod
    def create_with_balance_update(transaction_data):
        """Crear transacción y actualizar balances automáticamente"""
        from app import db
        
        # Crear la transacción
        transaction = Transaction(**transaction_data)
        db.session.add(transaction)
        db.session.flush()  # Para obtener el ID sin hacer commit
        
        # Actualizar balances
        transaction.update_affected_balances()
        
        return transaction
    
    def __repr__(self):
        return f'<Transaction {self.description}: ${self.amount}>'
