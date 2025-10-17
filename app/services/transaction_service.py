"""
Servicio de Lógica de Negocio para Transacciones (Transactions)

Este servicio centraliza toda la lógica de negocio relacionada con transacciones,
siguiendo el patrón Service Layer.

Responsabilidades:
- Creación y configuración de transacciones
- Actualización de transacciones y balances relacionados
- Eliminación de transacciones con actualización en cascada
- Consultas y estadísticas de transacciones
- Actualización automática de balances de cuentas/tarjetas
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
import logging

from app import db
from app.models.transaction import Transaction
from app.models.account import Account
from app.models.credit_card import CreditCard
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import or_

logger = logging.getLogger(__name__)


# Categorías de transacciones
TRANSACTION_CATEGORIES = [
    ('food', 'Alimentación'),
    ('transport', 'Transporte'),
    ('entertainment', 'Entretenimiento'),
    ('utilities', 'Servicios'),
    ('healthcare', 'Salud'),
    ('shopping', 'Compras'),
    ('education', 'Educación'),
    ('travel', 'Viajes'),
    ('debt_payment', 'Pago de Deudas'),
    ('debt_interest', 'Interés de Deuda'),
    ('investment_income', 'Rendimiento de Inversión'),
    ('salary', 'Salario'),
    ('freelance', 'Trabajos Independientes'),
    ('investment', 'Inversiones'),
    ('other', 'Otros')
]


class TransactionDTO:
    """Data Transfer Object para creación/actualización de transacciones"""
    
    def __init__(
        self,
        transaction_type: str,
        amount: float,
        description: str,
        category: str,
        date: datetime = None,
        account_id: Optional[int] = None,
        credit_card_id: Optional[int] = None,
        notes: Optional[str] = None,
        creditor_name: Optional[str] = None,
        is_debt_payment: bool = False
    ):
        self.transaction_type = transaction_type
        self.amount = amount
        self.description = description
        self.category = category
        self.date = date or datetime.now()
        self.account_id = account_id
        self.credit_card_id = credit_card_id
        self.notes = notes
        self.creditor_name = creditor_name
        self.is_debt_payment = is_debt_payment or (category == 'debt_payment')
    
    @classmethod
    def from_form(cls, form_data: dict) -> 'TransactionDTO':
        """Crear DTO desde datos de formulario Flask"""
        # Parsear monto
        try:
            amount = float(form_data.get('amount', 0))
        except (ValueError, TypeError):
            logger.warning(f"Monto inválido recibido: {form_data.get('amount')}, usando 0.0")
            amount = 0.0
        
        # Parsear fecha
        date_str = form_data.get('date')
        if date_str:
            try:
                transaction_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"Fecha inválida: {date_str}, usando fecha actual")
                transaction_date = datetime.now()
        else:
            transaction_date = datetime.now()
        
        # Parsear IDs opcionales
        account_id = form_data.get('account_id')
        if account_id:
            try:
                account_id = int(account_id)
            except (ValueError, TypeError):
                account_id = None
        
        credit_card_id = form_data.get('credit_card_id')
        if credit_card_id:
            try:
                credit_card_id = int(credit_card_id)
            except (ValueError, TypeError):
                credit_card_id = None
        
        category = form_data.get('category', 'other')
        
        return cls(
            transaction_type=form_data.get('transaction_type', ''),
            amount=amount,
            description=form_data.get('description', '').strip(),
            category=category,
            date=transaction_date,
            account_id=account_id,
            credit_card_id=credit_card_id,
            notes=form_data.get('notes', '').strip() or None,
            creditor_name=form_data.get('creditor_name', '').strip() if category == 'debt_payment' else None,
            is_debt_payment=category == 'debt_payment'
        )
    
    def validate(self) -> List[str]:
        """Validar datos del DTO. Retorna lista de errores."""
        errors = []
        
        # Validar tipo de transacción
        valid_types = ['income', 'expense', 'transfer']
        if not self.transaction_type:
            errors.append('El tipo de transacción es obligatorio')
        elif self.transaction_type not in valid_types:
            errors.append(f'Tipo de transacción inválido. Debe ser: {", ".join(valid_types)}')
        
        # Validar monto
        if self.amount is None:
            errors.append('El monto es obligatorio')
        elif self.amount <= 0:
            errors.append('El monto debe ser mayor a 0')
        elif self.amount > 999999999:
            errors.append('El monto es demasiado grande')
        
        # Validar descripción
        if not self.description:
            errors.append('La descripción es obligatoria')
        elif len(self.description) > 255:
            errors.append('La descripción no puede exceder 255 caracteres')
        
        # Validar categoría
        valid_categories = [cat[0] for cat in TRANSACTION_CATEGORIES]
        if not self.category:
            errors.append('La categoría es obligatoria')
        elif self.category not in valid_categories:
            errors.append(f'Categoría inválida')
        
        # Validar que tenga al menos una cuenta o tarjeta
        if not self.account_id and not self.credit_card_id:
            errors.append('Debe seleccionar una cuenta o tarjeta de crédito')
        
        # Validar que no tenga ambas
        if self.account_id and self.credit_card_id:
            errors.append('No puede seleccionar cuenta y tarjeta al mismo tiempo')
        
        # Validar notas
        if self.notes and len(self.notes) > 500:
            errors.append('Las notas no pueden exceder 500 caracteres')
        
        # Validar creditor_name si es pago de deuda
        if self.is_debt_payment and not self.creditor_name:
            errors.append('El nombre del acreedor es obligatorio para pagos de deuda')
        
        return errors


class TransactionService:
    """Servicio de lógica de negocio para transacciones"""
    
    @staticmethod
    def create_transaction(user_id: int, dto: TransactionDTO) -> Transaction:
        """
        Crear nueva transacción
        
        Args:
            user_id: ID del usuario propietario
            dto: Data Transfer Object con datos de la transacción
        
        Returns:
            Transaction: Transacción creada
        
        Raises:
            ValueError: Si los datos son inválidos
            PermissionError: Si la cuenta/tarjeta no pertenece al usuario
        """
        # Validar DTO
        errors = dto.validate()
        if errors:
            error_msg = '; '.join(errors)
            logger.warning(f"Validación fallida al crear transacción para user {user_id}: {error_msg}")
            raise ValueError(error_msg)
        
        try:
            logger.debug(f"Creando transacción para user {user_id}: {dto.description}")
            
            # Verificar propiedad de cuenta/tarjeta
            account = None
            credit_card = None
            
            if dto.account_id:
                account = Account.query.filter_by(id=dto.account_id, user_id=user_id).first()
                if not account:
                    raise PermissionError(f"Cuenta {dto.account_id} no encontrada o sin permisos")
            
            if dto.credit_card_id:
                credit_card = CreditCard.query.filter_by(id=dto.credit_card_id, user_id=user_id).first()
                if not credit_card:
                    raise PermissionError(f"Tarjeta {dto.credit_card_id} no encontrada o sin permisos")
            
            # Crear transacción
            transaction = Transaction(
                user_id=user_id,
                account_id=dto.account_id,
                credit_card_id=dto.credit_card_id,
                amount=dto.amount,
                description=dto.description,
                category=dto.category,
                transaction_type=dto.transaction_type,
                date=dto.date,
                notes=dto.notes,
                creditor_name=dto.creditor_name,
                is_debt_payment=dto.is_debt_payment
            )
            
            db.session.add(transaction)
            db.session.flush()  # Asignar ID
            
            # Actualizar balances
            if account:
                account.update_balance()
                logger.debug(f"Balance de cuenta {account.id} actualizado")
            
            if credit_card:
                TransactionService._update_credit_card_balance(credit_card, dto.transaction_type, dto.amount)
                logger.debug(f"Balance de tarjeta {credit_card.id} actualizado")
            
            db.session.commit()
            logger.info(f"Transacción creada exitosamente: id={transaction.id}, user={user_id}")
            
            return transaction
            
        except PermissionError:
            db.session.rollback()
            raise
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Error de integridad al crear transacción para user {user_id}: {e}", exc_info=True)
            raise
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de BD al crear transacción para user {user_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error inesperado al crear transacción para user {user_id}")
            raise
    
    @staticmethod
    def update_transaction(transaction_id: int, user_id: int, dto: TransactionDTO) -> Transaction:
        """
        Actualizar transacción existente
        
        Args:
            transaction_id: ID de la transacción a actualizar
            user_id: ID del usuario (para verificar propiedad)
            dto: Datos actualizados
        
        Returns:
            Transaction: Transacción actualizada
        
        Raises:
            ValueError: Si los datos son inválidos
            PermissionError: Si la transacción no pertenece al usuario
        """
        # Validar DTO
        errors = dto.validate()
        if errors:
            error_msg = '; '.join(errors)
            logger.warning(f"Validación fallida al actualizar transacción {transaction_id}: {error_msg}")
            raise ValueError(error_msg)
        
        try:
            # Obtener transacción y verificar propiedad
            transaction = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
            if not transaction:
                logger.warning(f"Intento de actualizar transacción inexistente o sin permisos: id={transaction_id}, user={user_id}")
                raise PermissionError("Transacción no encontrada o sin permisos")
            
            logger.debug(f"Actualizando transacción {transaction_id} para user {user_id}")
            
            # Guardar información anterior para recalcular balances
            old_account_id = transaction.account_id
            old_credit_card_id = transaction.credit_card_id
            old_amount = transaction.amount
            old_type = transaction.transaction_type
            
            # Verificar propiedad de nuevos recursos
            new_account = None
            new_credit_card = None
            
            if dto.account_id:
                new_account = Account.query.filter_by(id=dto.account_id, user_id=user_id).first()
                if not new_account:
                    raise PermissionError(f"Cuenta {dto.account_id} no encontrada o sin permisos")
            
            if dto.credit_card_id:
                new_credit_card = CreditCard.query.filter_by(id=dto.credit_card_id, user_id=user_id).first()
                if not new_credit_card:
                    raise PermissionError(f"Tarjeta {dto.credit_card_id} no encontrada o sin permisos")
            
            # Actualizar campos
            transaction.transaction_type = dto.transaction_type
            transaction.amount = dto.amount
            transaction.description = dto.description
            transaction.category = dto.category
            transaction.account_id = dto.account_id
            transaction.credit_card_id = dto.credit_card_id
            transaction.date = dto.date
            transaction.notes = dto.notes
            transaction.creditor_name = dto.creditor_name
            transaction.is_debt_payment = dto.is_debt_payment
            
            db.session.flush()
            
            # Recalcular balances de todas las cuentas afectadas
            affected_account_ids = set()
            if old_account_id:
                affected_account_ids.add(old_account_id)
            if dto.account_id:
                affected_account_ids.add(dto.account_id)
            
            for acc_id in affected_account_ids:
                account = Account.query.filter_by(id=acc_id, user_id=user_id).first()
                if account:
                    account.update_balance()
                    logger.debug(f"Balance de cuenta {acc_id} recalculado")
            
            # Manejar tarjetas de crédito
            if old_credit_card_id and old_credit_card_id != dto.credit_card_id:
                old_card = CreditCard.query.filter_by(id=old_credit_card_id, user_id=user_id).first()
                if old_card:
                    # Revertir transacción anterior
                    if old_type == 'expense':
                        old_card.current_balance -= old_amount
                    elif old_type == 'income':
                        old_card.current_balance += old_amount
                    old_card.update_minimum_payment()
                    logger.debug(f"Balance de tarjeta anterior {old_credit_card_id} revertido")
            
            if new_credit_card:
                TransactionService._update_credit_card_balance(new_credit_card, dto.transaction_type, dto.amount)
                logger.debug(f"Balance de nueva tarjeta {new_credit_card.id} actualizado")
            
            db.session.commit()
            logger.info(f"Transacción actualizada exitosamente: id={transaction_id}, user={user_id}")
            
            return transaction
            
        except PermissionError:
            db.session.rollback()
            raise
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Error de integridad al actualizar transacción {transaction_id}: {e}", exc_info=True)
            raise
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de BD al actualizar transacción {transaction_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error inesperado al actualizar transacción {transaction_id}")
            raise
    
    @staticmethod
    def delete_transaction(transaction_id: int, user_id: int) -> None:
        """
        Eliminar transacción con actualización en cascada de balances
        
        Args:
            transaction_id: ID de la transacción a eliminar
            user_id: ID del usuario (para verificar propiedad)
        
        Raises:
            PermissionError: Si la transacción no pertenece al usuario
        """
        try:
            transaction = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
            if not transaction:
                logger.warning(f"Intento de eliminar transacción inexistente o sin permisos: id={transaction_id}, user={user_id}")
                raise PermissionError("Transacción no encontrada o sin permisos")
            
            logger.info(f"Eliminando transacción {transaction_id} para user {user_id}")
            
            # Usar el método del modelo que maneja la actualización en cascada
            transaction.delete_with_cascade_update()
            
            db.session.commit()
            logger.info(f"Transacción eliminada exitosamente: id={transaction_id}")
            
        except PermissionError:
            db.session.rollback()
            raise
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de BD al eliminar transacción {transaction_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error inesperado al eliminar transacción {transaction_id}")
            raise
    
    @staticmethod
    def _update_credit_card_balance(credit_card: CreditCard, transaction_type: str, amount: float) -> None:
        """
        Actualizar balance de tarjeta de crédito según tipo de transacción
        
        Método interno para actualizar el balance de una tarjeta basándose
        en el tipo de transacción (expense aumenta, income disminuye).
        """
        if transaction_type == 'expense':
            credit_card.current_balance += amount
        elif transaction_type == 'income':  # Pago de tarjeta
            credit_card.current_balance -= amount
            credit_card.update_minimum_payment()
        
        logger.debug(f"Balance tarjeta {credit_card.id}: {credit_card.current_balance}")
    
    @staticmethod
    def get_user_transactions(
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        account_id: Optional[int] = None,
        credit_card_id: Optional[int] = None,
        category: Optional[str] = None,
        transaction_type: Optional[str] = None
    ) -> Dict:
        """
        Obtener transacciones de un usuario con paginación y filtros
        
        Args:
            user_id: ID del usuario
            page: Número de página
            per_page: Resultados por página
            account_id: Filtrar por cuenta
            credit_card_id: Filtrar por tarjeta
            category: Filtrar por categoría
            transaction_type: Filtrar por tipo
        
        Returns:
            Dict con transacciones paginadas y metadatos
        """
        query = Transaction.query.filter_by(user_id=user_id)
        
        # Aplicar filtros
        if account_id:
            query = query.filter_by(account_id=account_id)
        if credit_card_id:
            query = query.filter_by(credit_card_id=credit_card_id)
        if category:
            query = query.filter_by(category=category)
        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type)
        
        # Ordenar y paginar
        pagination = query.order_by(Transaction.date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        logger.debug(f"Obtenidas {len(pagination.items)} transacciones para user {user_id} (página {page})")
        
        return {
            'transactions': pagination.items,
            'pagination': pagination,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }
    
    @staticmethod
    def get_transaction_by_id(transaction_id: int, user_id: int) -> Optional[Transaction]:
        """
        Obtener transacción por ID verificando propiedad
        
        Args:
            transaction_id: ID de la transacción
            user_id: ID del usuario (para verificar propiedad)
        
        Returns:
            Optional[Transaction]: Transacción si existe y pertenece al usuario
        """
        transaction = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
        
        if not transaction:
            logger.debug(f"Transacción no encontrada: id={transaction_id}, user={user_id}")
        
        return transaction
    
    @staticmethod
    def get_transaction_categories() -> List[Tuple[str, str]]:
        """
        Obtener lista de categorías disponibles
        
        Returns:
            List[Tuple[str, str]]: Lista de (código, nombre) de categorías
        """
        return TRANSACTION_CATEGORIES
