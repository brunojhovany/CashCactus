"""
Tests unitarios para AccountService

Estos tests verifican la lógica de negocio del servicio de cuentas,
sin depender del controlador HTTP.
"""

import pytest
from datetime import datetime
from app.services.account_service import AccountService, AccountDTO
from app.models.account import Account
from app.models.transaction import Transaction
from app import db


class TestAccountDTO:
    """Tests para AccountDTO y validación"""
    
    def test_dto_from_form_basic(self):
        """Test creación de DTO desde formulario básico"""
        form_data = {
            'name': 'Mi Cuenta',
            'account_type': 'checking',
            'initial_balance': '1000.50',
            'bank_name': 'Banco Ejemplo'
        }
        
        dto = AccountDTO.from_form(form_data)
        
        assert dto.name == 'Mi Cuenta'
        assert dto.account_type == 'checking'
        assert dto.initial_balance == 1000.50
        assert dto.bank_name == 'Banco Ejemplo'
        assert dto.generates_interest == False
    
    def test_dto_from_form_investment(self):
        """Test creación de DTO con datos de inversión"""
        form_data = {
            'name': 'Cuenta Ahorro',
            'account_type': 'savings',
            'initial_balance': '5000',
            'generates_interest': 'on',
            'interest_rate': '3.5',
            'investment_type': 'savings',
            'compound_frequency': 'monthly'
        }
        
        dto = AccountDTO.from_form(form_data)
        
        assert dto.generates_interest == True
        assert dto.interest_rate == 3.5
        assert dto.investment_type == 'savings'
        assert dto.compound_frequency == 'monthly'
    
    def test_dto_invalid_balance_defaults_to_zero(self):
        """Test que balance inválido se convierte a 0"""
        form_data = {
            'name': 'Test',
            'account_type': 'checking',
            'initial_balance': 'invalid'
        }
        
        dto = AccountDTO.from_form(form_data)
        assert dto.initial_balance == 0.0
    
    def test_dto_validation_missing_name(self):
        """Test validación: nombre obligatorio"""
        dto = AccountDTO(
            name='',
            account_type='checking'
        )
        
        errors = dto.validate()
        assert len(errors) > 0
        assert any('nombre' in e.lower() for e in errors)
    
    def test_dto_validation_invalid_type(self):
        """Test validación: tipo de cuenta inválido"""
        dto = AccountDTO(
            name='Test',
            account_type='invalid_type'
        )
        
        errors = dto.validate()
        assert len(errors) > 0
        assert any('tipo' in e.lower() for e in errors)
    
    def test_dto_validation_invalid_interest_rate(self):
        """Test validación: tasa de interés fuera de rango"""
        dto = AccountDTO(
            name='Test',
            account_type='savings',
            interest_rate=150  # Inválido: >100%
        )
        
        errors = dto.validate()
        assert len(errors) > 0
        assert any('interés' in e.lower() or 'interest' in e.lower() for e in errors)


class TestAccountService:
    """Tests para lógica de negocio de AccountService"""
    
    def test_create_account_basic(self, app, test_user):
        """Test crear cuenta básica"""
        with app.app_context():
            dto = AccountDTO(
                name='Cuenta Corriente',
                account_type='checking',
                initial_balance=1000.0,
                bank_name='Banco Test'
            )
            
            account = AccountService.create_account(test_user.id, dto)
            
            assert account.id is not None
            assert account.name == 'Cuenta Corriente'
            assert account.account_type == 'checking'
            assert account.balance == 1000.0
            assert account.bank_name == 'Banco Test'
            assert account.user_id == test_user.id
            assert account.is_active == True
    
    def test_create_account_with_initial_balance_creates_transaction(self, app, test_user):
        """Test que crear cuenta con balance inicial crea transacción"""
        with app.app_context():
            dto = AccountDTO(
                name='Cuenta Test',
                account_type='checking',
                initial_balance=500.0
            )
            
            account = AccountService.create_account(test_user.id, dto)
            
            # Verificar que se creó la transacción
            transactions = Transaction.query.filter_by(
                account_id=account.id,
                user_id=test_user.id
            ).all()
            
            assert len(transactions) == 1
            assert transactions[0].amount == 500.0
            assert transactions[0].description == 'Saldo inicial'
            assert transactions[0].transaction_type == 'income'
    
    def test_create_account_investment_with_interest(self, app, test_user):
        """Test crear cuenta de inversión con interés"""
        with app.app_context():
            dto = AccountDTO(
                name='Cuenta Inversión',
                account_type='investment',
                initial_balance=10000.0,
                generates_interest=True,
                interest_rate=5.0,
                investment_type='stocks',
                compound_frequency='monthly'
            )
            
            account = AccountService.create_account(test_user.id, dto)
            
            assert account.generates_interest == True
            assert account.interest_rate == 5.0
            assert account.investment_type == 'stocks'
            assert account.compound_frequency == 'monthly'
            assert account.last_interest_calculation is not None
    
    def test_create_account_validation_error(self, app, test_user):
        """Test que crear cuenta con datos inválidos lanza ValueError"""
        with app.app_context():
            dto = AccountDTO(
                name='',  # Nombre vacío - inválido
                account_type='checking'
            )
            
            with pytest.raises(ValueError) as exc_info:
                AccountService.create_account(test_user.id, dto)
            
            assert 'nombre' in str(exc_info.value).lower()
    
    def test_update_account(self, app, test_user):
        """Test actualizar cuenta existente"""
        with app.app_context():
            # Crear cuenta
            dto = AccountDTO(
                name='Original',
                account_type='checking',
                initial_balance=100.0
            )
            account = AccountService.create_account(test_user.id, dto)
            account_id = account.id
            
            # Actualizar
            update_dto = AccountDTO(
                name='Actualizado',
                account_type='savings',
                initial_balance=100.0,  # Sin cambio de balance
                bank_name='Banco Nuevo'
            )
            
            updated_account = AccountService.update_account(account_id, test_user.id, update_dto)
            
            assert updated_account.name == 'Actualizado'
            assert updated_account.account_type == 'savings'
            assert updated_account.bank_name == 'Banco Nuevo'
    
    def test_update_account_balance_creates_adjustment_transaction(self, app, test_user):
        """Test que cambiar balance crea transacción de ajuste"""
        with app.app_context():
            # Crear cuenta
            dto = AccountDTO(
                name='Test',
                account_type='checking',
                initial_balance=1000.0
            )
            account = AccountService.create_account(test_user.id, dto)
            account_id = account.id
            
            # Contar transacciones iniciales
            initial_tx_count = Transaction.query.filter_by(account_id=account_id).count()
            
            # Actualizar balance
            update_dto = AccountDTO(
                name='Test',
                account_type='checking',
                initial_balance=1500.0  # Incremento de 500
            )
            
            updated_account = AccountService.update_account(account_id, test_user.id, update_dto)
            
            # Verificar nueva transacción de ajuste
            final_tx_count = Transaction.query.filter_by(account_id=account_id).count()
            assert final_tx_count == initial_tx_count + 1
            
            # Verificar transacción de ajuste
            adjustment_tx = Transaction.query.filter_by(
                account_id=account_id
            ).order_by(Transaction.id.desc()).first()
            
            assert 'Ajuste de saldo' in adjustment_tx.description
            assert adjustment_tx.amount == 500.0
    
    def test_update_account_wrong_user_raises_permission_error(self, app, test_user, test_user2):
        """Test que actualizar cuenta de otro usuario lanza PermissionError"""
        with app.app_context():
            # Crear cuenta como test_user
            dto = AccountDTO(name='Test', account_type='checking')
            account = AccountService.create_account(test_user.id, dto)
            
            # Intentar actualizar como test_user2
            update_dto = AccountDTO(name='Hacked', account_type='checking')
            
            with pytest.raises(PermissionError):
                AccountService.update_account(account.id, test_user2.id, update_dto)
    
    def test_delete_account(self, app, test_user):
        """Test desactivar cuenta (soft delete)"""
        with app.app_context():
            # Crear cuenta
            dto = AccountDTO(name='Test', account_type='checking')
            account = AccountService.create_account(test_user.id, dto)
            account_id = account.id
            
            # Verificar que está activa
            assert account.is_active == True
            
            # Desactivar
            AccountService.delete_account(account_id, test_user.id)
            
            # Verificar que se desactivó
            deleted_account = Account.query.get(account_id)
            assert deleted_account.is_active == False
    
    def test_delete_account_wrong_user_raises_permission_error(self, app, test_user, test_user2):
        """Test que eliminar cuenta de otro usuario lanza PermissionError"""
        with app.app_context():
            # Crear cuenta como test_user
            dto = AccountDTO(name='Test', account_type='checking')
            account = AccountService.create_account(test_user.id, dto)
            
            # Intentar eliminar como test_user2
            with pytest.raises(PermissionError):
                AccountService.delete_account(account.id, test_user2.id)
    
    def test_get_user_accounts(self, app, test_user):
        """Test obtener cuentas de usuario"""
        with app.app_context():
            # Crear varias cuentas
            for i in range(3):
                dto = AccountDTO(name=f'Cuenta {i}', account_type='checking')
                AccountService.create_account(test_user.id, dto)
            
            # Obtener cuentas
            accounts = AccountService.get_user_accounts(test_user.id)
            
            assert len(accounts) == 3
            assert all(acc.user_id == test_user.id for acc in accounts)
            assert all(acc.is_active for acc in accounts)
    
    def test_get_user_accounts_excludes_inactive(self, app, test_user):
        """Test que get_user_accounts excluye cuentas inactivas por defecto"""
        with app.app_context():
            # Crear cuenta activa e inactiva
            dto1 = AccountDTO(name='Activa', account_type='checking')
            account1 = AccountService.create_account(test_user.id, dto1)
            
            dto2 = AccountDTO(name='Inactiva', account_type='checking')
            account2 = AccountService.create_account(test_user.id, dto2)
            AccountService.delete_account(account2.id, test_user.id)
            
            # Obtener solo activas
            active_accounts = AccountService.get_user_accounts(test_user.id, include_inactive=False)
            assert len(active_accounts) == 1
            assert active_accounts[0].name == 'Activa'
            
            # Obtener todas
            all_accounts = AccountService.get_user_accounts(test_user.id, include_inactive=True)
            assert len(all_accounts) == 2
    
    def test_get_total_balance(self, app, test_user):
        """Test calcular balance total"""
        with app.app_context():
            # Crear cuentas con diferentes balances
            balances = [1000.0, 2500.0, 750.0]
            for balance in balances:
                dto = AccountDTO(
                    name=f'Cuenta {balance}',
                    account_type='checking',
                    initial_balance=balance
                )
                AccountService.create_account(test_user.id, dto)
            
            total = AccountService.get_total_balance(test_user.id)
            assert total == sum(balances)
    
    def test_get_account_statistics(self, app, test_user):
        """Test obtener estadísticas de cuenta"""
        with app.app_context():
            # Crear cuenta
            dto = AccountDTO(
                name='Test',
                account_type='checking',
                initial_balance=1000.0
            )
            account = AccountService.create_account(test_user.id, dto)
            
            # Obtener estadísticas
            stats = AccountService.get_account_statistics(account.id, test_user.id)
            
            assert 'account' in stats
            assert 'recent_transactions' in stats
            assert 'monthly_income' in stats
            assert 'monthly_expenses' in stats
            assert stats['account'].id == account.id
            assert len(stats['recent_transactions']) >= 1  # Al menos transacción inicial
    
    def test_get_account_by_id(self, app, test_user):
        """Test obtener cuenta por ID"""
        with app.app_context():
            dto = AccountDTO(name='Test', account_type='checking')
            created_account = AccountService.create_account(test_user.id, dto)
            
            retrieved_account = AccountService.get_account_by_id(created_account.id, test_user.id)
            
            assert retrieved_account is not None
            assert retrieved_account.id == created_account.id
            assert retrieved_account.name == 'Test'
    
    def test_get_account_by_id_wrong_user_returns_none(self, app, test_user, test_user2):
        """Test que obtener cuenta de otro usuario retorna None"""
        with app.app_context():
            # Crear cuenta como test_user
            dto = AccountDTO(name='Test', account_type='checking')
            account = AccountService.create_account(test_user.id, dto)
            
            # Intentar obtener como test_user2
            retrieved = AccountService.get_account_by_id(account.id, test_user2.id)
            assert retrieved is None
