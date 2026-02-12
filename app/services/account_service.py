"""
Servicio de Lógica de Negocio para Cuentas (Accounts)

Este servicio centraliza toda la lógica de negocio relacionada con cuentas bancarias,
siguiendo el patrón Service Layer para mantener los controladores simples y enfocados
en la coordinación HTTP.

Responsabilidades:
- Creación y configuración de cuentas
- Actualización de cuentas y balances
- Desactivación de cuentas
- Consultas y estadísticas de cuentas
- Cálculo de intereses para cuentas de inversión/ahorro
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
import logging

from app import db
from app.models.account import Account
from app.models.transaction import Transaction
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)


class AccountDTO:
    """Data Transfer Object para creación/actualización de cuentas"""
    
    def __init__(
        self,
        name: str,
        account_type: str,
        initial_balance: float = 0.0,
        bank_name: Optional[str] = None,
        generates_interest: bool = False,
        interest_rate: float = 0.0,
        investment_type: Optional[str] = None,
        compound_frequency: str = 'monthly',
        is_active: bool = True
    ):
        self.name = name
        self.account_type = account_type
        self.initial_balance = initial_balance
        self.bank_name = bank_name
        self.generates_interest = generates_interest
        self.interest_rate = interest_rate
        self.investment_type = investment_type
        self.compound_frequency = compound_frequency
        self.is_active = is_active
    
    @classmethod
    def from_form(cls, form_data: dict) -> 'AccountDTO':
        """Crear DTO desde datos de formulario Flask"""
        # Parsear balance inicial (soporta 'initial_balance' o 'balance')
        balance_raw = form_data.get('initial_balance')
        if balance_raw is None or balance_raw == '':
            balance_raw = form_data.get('balance', 0)
        
        try:
            initial_balance = float(balance_raw) if balance_raw not in (None, '') else 0.0
        except (ValueError, TypeError):
            logger.warning(f"Balance inválido recibido: {balance_raw}, usando 0.0")
            initial_balance = 0.0
        
        # Parsear tasa de interés
        try:
            interest_rate = float(form_data.get('interest_rate', 0))
        except (ValueError, TypeError):
            logger.warning(f"Tasa de interés inválida: {form_data.get('interest_rate')}, usando 0.0")
            interest_rate = 0.0
        
        return cls(
            name=form_data.get('name', '').strip(),
            account_type=form_data.get('account_type', ''),
            initial_balance=initial_balance,
            bank_name=form_data.get('bank_name', '').strip() or None,
            generates_interest=form_data.get('generates_interest') == 'on',
            interest_rate=interest_rate,
            investment_type=form_data.get('investment_type'),
            compound_frequency=form_data.get('compound_frequency', 'monthly'),
            is_active=form_data.get('is_active', 'on') == 'on'
        )
    
    def validate(self) -> List[str]:
        """Validar datos del DTO. Retorna lista de errores."""
        errors = []
        
        if not self.name:
            errors.append('El nombre de la cuenta es obligatorio')
        elif len(self.name) > 100:
            errors.append('El nombre de la cuenta no puede exceder 100 caracteres')
        
        valid_types = ['checking', 'savings', 'investment', 'debt']
        if not self.account_type:
            errors.append('El tipo de cuenta es obligatorio')
        elif self.account_type not in valid_types:
            errors.append(f'Tipo de cuenta inválido. Debe ser uno de: {", ".join(valid_types)}')
        
        if self.interest_rate < 0 or self.interest_rate > 100:
            errors.append('La tasa de interés debe estar entre 0 y 100')
        
        if self.bank_name and len(self.bank_name) > 100:
            errors.append('El nombre del banco no puede exceder 100 caracteres')
        
        return errors


class AccountService:
    """Servicio de lógica de negocio para cuentas"""
    
    @staticmethod
    def create_account(user_id: int, dto: AccountDTO) -> Account:
        """
        Crear nueva cuenta bancaria
        
        Args:
            user_id: ID del usuario propietario
            dto: Data Transfer Object con datos de la cuenta
        
        Returns:
            Account: Cuenta creada
        
        Raises:
            ValueError: Si los datos son inválidos
            IntegrityError: Si hay conflicto de base de datos
        """
        # Validar DTO
        errors = dto.validate()
        if errors:
            error_msg = '; '.join(errors)
            logger.warning(f"Validación fallida al crear cuenta para user {user_id}: {error_msg}")
            raise ValueError(error_msg)
        
        try:
            logger.debug(f"Creando cuenta para user {user_id}: {dto.name} ({dto.account_type})")
            
            # Crear cuenta
            account = Account(
                user_id=user_id,
                name=dto.name,
                account_type=dto.account_type,
                balance=dto.initial_balance,
                bank_name=dto.bank_name,
                is_active=dto.is_active,
                is_debt_account=(dto.account_type == 'debt')
            )
            
            # Configurar campos específicos de inversión/ahorro
            if dto.account_type in ['savings', 'investment']:
                account.generates_interest = dto.generates_interest
                account.interest_rate = dto.interest_rate
                account.investment_type = dto.investment_type
                account.compound_frequency = dto.compound_frequency
                
                if dto.generates_interest:
                    account.last_interest_calculation = datetime.utcnow()
                    logger.debug(f"Cuenta de inversión configurada con interés {dto.interest_rate}%")
            
            db.session.add(account)
            db.session.flush()  # Asignar ID sin commit
            
            logger.debug(f"Cuenta provisional creada: id={account.id}, balance={account.balance}")
            
            # Crear transacción de saldo inicial si es necesario
            if dto.initial_balance != 0:
                AccountService._create_initial_balance_transaction(
                    user_id=user_id,
                    account_id=account.id,
                    amount=dto.initial_balance
                )
            
            db.session.commit()
            logger.info(f"Cuenta creada exitosamente: id={account.id}, user={user_id}, tipo={dto.account_type}")
            
            return account
            
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Error de integridad al crear cuenta para user {user_id}: {e}", exc_info=True)
            raise IntegrityError("Error de integridad en base de datos", params=None, orig=e.orig)
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de BD al crear cuenta para user {user_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error inesperado al crear cuenta para user {user_id}")
            raise
    
    @staticmethod
    def _create_initial_balance_transaction(user_id: int, account_id: int, amount: float) -> Transaction:
        """
        Crear transacción de saldo inicial
        
        Método interno para crear la transacción que representa el balance inicial
        de una cuenta recién creada.
        """
        transaction = Transaction(
            user_id=user_id,
            account_id=account_id,
            amount=abs(amount),
            description="Saldo inicial",
            category="other",
            transaction_type="income" if amount > 0 else "expense",
            date=datetime.now().date()
        )
        
        # Workaround transitorio para columna legacy 'description' NOT NULL
        # TODO: Remover después de migración completa a campos encriptados
        if hasattr(transaction, 'description_enc') and not hasattr(Transaction, 'description_col_checked'):
            from sqlalchemy import inspect as _insp
            try:
                insp = _insp(db.engine)
                cols = {c['name']: c for c in insp.get_columns('transactions')}
                if 'description' in cols and not cols['description'].get('nullable', True):
                    setattr(transaction, 'description', 'Saldo inicial')
            except Exception as e:
                logger.warning(f"No se pudo verificar columna legacy description: {e}")
            Transaction.description_col_checked = True
        
        db.session.add(transaction)
        logger.debug(f"Transacción de saldo inicial creada: user={user_id}, account={account_id}, amount={amount}")
        
        return transaction
    
    @staticmethod
    def update_account(account_id: int, user_id: int, dto: AccountDTO) -> Account:
        """
        Actualizar cuenta existente
        
        Args:
            account_id: ID de la cuenta a actualizar
            user_id: ID del usuario (para verificar propiedad)
            dto: Datos actualizados
        
        Returns:
            Account: Cuenta actualizada
        
        Raises:
            ValueError: Si los datos son inválidos
            PermissionError: Si la cuenta no pertenece al usuario
        """
        # Validar DTO
        errors = dto.validate()
        if errors:
            error_msg = '; '.join(errors)
            logger.warning(f"Validación fallida al actualizar cuenta {account_id}: {error_msg}")
            raise ValueError(error_msg)
        
        try:
            # Obtener cuenta y verificar propiedad
            account = Account.query.filter_by(id=account_id, user_id=user_id).first()
            if not account:
                logger.warning(f"Intento de actualizar cuenta inexistente o sin permisos: id={account_id}, user={user_id}")
                raise PermissionError("Cuenta no encontrada o sin permisos")
            
            logger.debug(f"Actualizando cuenta {account_id} para user {user_id}")
            
            # Guardar balance anterior para calcular diferencia
            old_balance = float(account.balance)
            
            # Actualizar campos básicos
            account.name = dto.name
            account.account_type = dto.account_type
            account.bank_name = dto.bank_name
            account.balance = dto.initial_balance
            account.is_active = dto.is_active
            account.is_debt_account = (dto.account_type == 'debt')
            
            # Actualizar o limpiar campos de inversión
            if dto.account_type in ['savings', 'investment']:
                account.generates_interest = dto.generates_interest
                account.interest_rate = dto.interest_rate
                account.investment_type = dto.investment_type
                account.compound_frequency = dto.compound_frequency
                
                if dto.generates_interest and not account.last_interest_calculation:
                    account.last_interest_calculation = datetime.utcnow()
            else:
                # Limpiar campos de inversión para otros tipos
                account.generates_interest = False
                account.interest_rate = 0.0
                account.investment_type = None
                account.compound_frequency = 'monthly'
            
            # Si el balance cambió, crear transacción de ajuste
            balance_difference = dto.initial_balance - old_balance
            if balance_difference != 0:
                logger.debug(f"Balance cambió de {old_balance} a {dto.initial_balance}, creando ajuste")
                
                adjustment_transaction = Transaction(
                    user_id=user_id,
                    account_id=account_id,
                    amount=abs(balance_difference),
                    description='Ajuste de saldo - Edición de cuenta',
                    category='other',
                    transaction_type='income' if balance_difference > 0 else 'expense',
                    date=datetime.now().date()
                )
                db.session.add(adjustment_transaction)
                db.session.flush()
                
                # Recalcular balance basado en transacciones
                account.update_balance()
            
            db.session.commit()
            logger.info(f"Cuenta actualizada exitosamente: id={account_id}, user={user_id}")
            
            return account
            
        except PermissionError:
            raise
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Error de integridad al actualizar cuenta {account_id}: {e}", exc_info=True)
            raise
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de BD al actualizar cuenta {account_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error inesperado al actualizar cuenta {account_id}")
            raise
    
    @staticmethod
    def delete_account(account_id: int, user_id: int) -> None:
        """
        Desactivar cuenta (soft delete)
        
        Args:
            account_id: ID de la cuenta a desactivar
            user_id: ID del usuario (para verificar propiedad)
        
        Raises:
            PermissionError: Si la cuenta no pertenece al usuario
        """
        try:
            account = Account.query.filter_by(id=account_id, user_id=user_id).first()
            if not account:
                logger.warning(f"Intento de eliminar cuenta inexistente o sin permisos: id={account_id}, user={user_id}")
                raise PermissionError("Cuenta no encontrada o sin permisos")
            
            logger.info(f"Desactivando cuenta {account_id} para user {user_id}")
            
            account.is_active = False
            db.session.commit()
            
            logger.info(f"Cuenta desactivada exitosamente: id={account_id}")
            
        except PermissionError:
            raise
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de BD al desactivar cuenta {account_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error inesperado al desactivar cuenta {account_id}")
            raise
    
    @staticmethod
    def get_user_accounts(user_id: int, include_inactive: bool = False) -> List[Account]:
        """
        Obtener todas las cuentas de un usuario
        
        Args:
            user_id: ID del usuario
            include_inactive: Si incluir cuentas desactivadas
        
        Returns:
            List[Account]: Lista de cuentas
        """
        query = Account.query.filter_by(user_id=user_id)
        
        if not include_inactive:
            query = query.filter_by(is_active=True)
        
        accounts = query.all()
        logger.debug(f"Obtenidas {len(accounts)} cuentas para user {user_id} (inactive={include_inactive})")
        
        return accounts
    
    @staticmethod
    def get_account_by_id(account_id: int, user_id: int) -> Optional[Account]:
        """
        Obtener cuenta por ID verificando propiedad
        
        Args:
            account_id: ID de la cuenta
            user_id: ID del usuario (para verificar propiedad)
        
        Returns:
            Optional[Account]: Cuenta si existe y pertenece al usuario
        """
        account = Account.query.filter_by(id=account_id, user_id=user_id).first()
        
        if not account:
            logger.debug(f"Cuenta no encontrada: id={account_id}, user={user_id}")
        
        return account
    
    @staticmethod
    def get_total_balance(user_id: int) -> float:
        """
        Calcular balance total de todas las cuentas activas del usuario
        
        Args:
            user_id: ID del usuario
        
        Returns:
            float: Balance total
        """
        accounts = AccountService.get_user_accounts(user_id, include_inactive=False)
        total = float(sum(account.balance for account in accounts))
        
        logger.debug(f"Balance total calculado para user {user_id}: {total}")
        
        return total
    
    @staticmethod
    def get_account_statistics(account_id: int, user_id: int) -> Dict:
        """
        Obtener estadísticas de una cuenta
        
        Args:
            account_id: ID de la cuenta
            user_id: ID del usuario
        
        Returns:
            Dict: Estadísticas incluyendo ingresos/gastos mensuales, transacciones recientes
        
        Raises:
            PermissionError: Si la cuenta no pertenece al usuario
        """
        account = AccountService.get_account_by_id(account_id, user_id)
        if not account:
            raise PermissionError("Cuenta no encontrada o sin permisos")
        
        # Obtener transacciones recientes
        recent_transactions = Transaction.query.filter(
            Transaction.account_id == account_id,
            Transaction.user_id == user_id
        ).order_by(Transaction.date.desc()).limit(20).all()
        
        # Calcular estadísticas del mes actual
        current_date = datetime.now()
        month_start = datetime(current_date.year, current_date.month, 1)
        
        monthly_transactions = Transaction.query.filter(
            Transaction.account_id == account_id,
            Transaction.user_id == user_id,
            Transaction.date >= month_start
        ).all()
        
        monthly_income = float(sum(t.amount for t in monthly_transactions if t.transaction_type == 'income'))
        monthly_expenses = float(sum(t.amount for t in monthly_transactions if t.transaction_type == 'expense'))
        
        logger.debug(f"Estadísticas calculadas para cuenta {account_id}: income={monthly_income}, expenses={monthly_expenses}")
        
        return {
            'account': account,
            'recent_transactions': recent_transactions,
            'monthly_income': monthly_income,
            'monthly_expenses': monthly_expenses,
            'transaction_count': len(monthly_transactions)
        }
    
    @staticmethod
    def get_account_types() -> List[Tuple[str, str]]:
        """
        Obtener lista de tipos de cuenta disponibles
        
        Returns:
            List[Tuple[str, str]]: Lista de (código, nombre) de tipos de cuenta
        """
        return [
            ('checking', 'Cuenta Corriente'),
            ('savings', 'Cuenta de Ahorros'),
            ('investment', 'Inversión')
        ]
