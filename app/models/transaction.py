from datetime import datetime
from app import db
from decimal import Decimal, ROUND_HALF_UP
from app.utils.crypto_fields import encrypt_field, decrypt_field, blind_index, dual_encrypt, get_active_enc_version

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    credit_card_id = db.Column(db.Integer, db.ForeignKey('credit_cards.id'), nullable=True)
    
    # Monto sensible: almacenar sólo cifrado
    amount_enc = db.Column(db.LargeBinary, nullable=False)
    # Campos en claro previos: description, notes, creditor_name.
    # Se migran a *_enc (BYTEA) + blind indexes para consultas futuras.
    description_enc = db.Column(db.LargeBinary, nullable=True)
    description_bidx = db.Column(db.String(64), index=True)  # HMAC hex
    category = db.Column(db.String(50), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'income', 'expense', 'transfer'
    date = db.Column(db.DateTime, default=datetime.utcnow)
    notes_enc = db.Column(db.LargeBinary, nullable=True)
    notes_bidx = db.Column(db.String(64), index=True)
    
    # Para transferencias entre cuentas
    transfer_to_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    
    # Para pagos de deudas a terceros
    creditor_name_enc = db.Column(db.LargeBinary, nullable=True)
    creditor_name_bidx = db.Column(db.String(64), index=True)
    is_debt_payment = db.Column(db.Boolean, default=False)
    
    # Para transacciones automáticas (como intereses)
    is_automatic = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Versión de cifrado aplicada a los campos *_enc / *_bidx.
    # Se obtiene dinámicamente de APP_ENC_ACTIVE_VERSION para nuevas filas.
    enc_version = db.Column(db.SmallInteger, default=get_active_enc_version)

    # ---- Accesores de alto nivel (mantienen API lógica) ----
    @property
    def amount(self) -> float:
        """Monto desencriptado como float. Se almacena internamente como string decimal cifrada.

        Nota: se usa cuantización a 2 decimales para evitar sorpresas de float.
        """
        txt = decrypt_field(self.amount_enc, 'amount', self.enc_version)
        if txt is None:
            return 0.0
        return float(Decimal(txt))

    @amount.setter
    def amount(self, value: float | int | str):
        if value is None:
            raise ValueError('amount no puede ser None')
        if not self.enc_version:
            self.enc_version = get_active_enc_version()
        # Normalizar a string decimal con 2 decimales
        dec = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        enc = encrypt_field(str(dec), 'amount', self.enc_version)
        self.amount_enc = enc
    @property
    def description(self) -> str | None:  # type: ignore[override]
        return decrypt_field(self.description_enc, 'description', self.enc_version)

    @description.setter
    def description(self, value: str | None):  # type: ignore[override]
        # Si aún no se asignó versión (nuevo objeto), tomar versión activa.
        if not self.enc_version:
            self.enc_version = get_active_enc_version()
        version = self.enc_version
        enc, bidx = dual_encrypt(value, 'description', version)
        self.description_enc = enc
        self.description_bidx = bidx

    @property
    def notes(self) -> str | None:  # type: ignore[override]
        return decrypt_field(self.notes_enc, 'notes', self.enc_version)

    @notes.setter
    def notes(self, value: str | None):  # type: ignore[override]
        if not self.enc_version:
            self.enc_version = get_active_enc_version()
        version = self.enc_version
        enc, bidx = dual_encrypt(value, 'notes', version)
        self.notes_enc = enc
        self.notes_bidx = bidx

    @property
    def creditor_name(self) -> str | None:  # type: ignore[override]
        return decrypt_field(self.creditor_name_enc, 'creditor_name', self.enc_version)

    @creditor_name.setter
    def creditor_name(self, value: str | None):  # type: ignore[override]
        if not self.enc_version:
            self.enc_version = get_active_enc_version()
        version = self.enc_version
        enc, bidx = dual_encrypt(value, 'creditor_name', version)
        self.creditor_name_enc = enc
        self.creditor_name_bidx = bidx
    
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
        return f'<Transaction {self.description or "(enc)"}: ${self.amount}>'
