"""
Servicio para mantenimiento y recalculo de saldos cifrados.
Centraliza la lógica de recalculo para evitar código duplicado en controladores/rutas.
"""
from app import db
from app.models.account import Account
from app.models.credit_card import CreditCard


class BalanceMaintenanceService:
    """Servicio para mantener saldos actualizados y corregir problemas de cifrado."""
    
    @staticmethod
    def recalculate_user_balances(user_id: int) -> dict:
        """
        Recalcula todos los saldos de cuentas y tarjetas de un usuario.
        
        Útil para:
        - Corregir problemas de cifrado (cuando decrypt devuelve None/0)
        - Sincronizar saldos con transacciones reales
        - Mantenimiento preventivo
        
        Args:
            user_id: ID del usuario
            
        Returns:
            dict con estadísticas de la operación:
            {
                'accounts_updated': int,
                'cards_updated': int,
                'errors': list
            }
        """
        stats = {
            'accounts_updated': 0,
            'cards_updated': 0,
            'errors': []
        }
        
        try:
            # Recalcular cuentas
            accounts = Account.query.filter_by(user_id=user_id, is_active=True).all()
            for account in accounts:
                try:
                    account.update_balance()
                    stats['accounts_updated'] += 1
                except Exception as e:
                    stats['errors'].append(f"Account {account.id}: {str(e)}")
            
            # Recalcular tarjetas
            cards = CreditCard.query.filter_by(user_id=user_id, is_active=True).all()
            for card in cards:
                try:
                    card.update_balance()
                    card.update_minimum_payment()
                    stats['cards_updated'] += 1
                except Exception as e:
                    stats['errors'].append(f"CreditCard {card.id}: {str(e)}")
            
            # Commit solo si no hubo errores críticos
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            stats['errors'].append(f"Critical error: {str(e)}")
        
        return stats
    
    @staticmethod
    def recalculate_all_balances() -> dict:
        """
        Recalcula saldos para TODOS los usuarios (usar con precaución).
        
        Útil para:
        - Mantenimiento programado
        - Después de migración de claves de cifrado
        - Corrección masiva de datos
        
        Returns:
            dict con estadísticas globales
        """
        from app.models.user import User
        
        total_stats = {
            'users_processed': 0,
            'accounts_updated': 0,
            'cards_updated': 0,
            'errors': []
        }
        
        users = User.query.all()
        
        for user in users:
            user_stats = BalanceMaintenanceService.recalculate_user_balances(user.id)
            total_stats['users_processed'] += 1
            total_stats['accounts_updated'] += user_stats['accounts_updated']
            total_stats['cards_updated'] += user_stats['cards_updated']
            total_stats['errors'].extend(user_stats['errors'])
        
        return total_stats
    
    @staticmethod
    def fix_account_balance(account_id: int, user_id: int) -> bool:
        """
        Recalcula y corrige el balance de una cuenta específica.
        
        Args:
            account_id: ID de la cuenta
            user_id: ID del usuario (para validación de propiedad)
            
        Returns:
            True si se actualizó correctamente, False si hubo error
        """
        try:
            account = Account.query.filter_by(
                id=account_id,
                user_id=user_id
            ).first()
            
            if not account:
                return False
            
            account.update_balance()
            db.session.commit()
            return True
            
        except Exception:
            db.session.rollback()
            return False
    
    @staticmethod
    def fix_card_balance(card_id: int, user_id: int) -> bool:
        """
        Recalcula y corrige el balance de una tarjeta específica.
        
        Args:
            card_id: ID de la tarjeta
            user_id: ID del usuario (para validación de propiedad)
            
        Returns:
            True si se actualizó correctamente, False si hubo error
        """
        try:
            card = CreditCard.query.filter_by(
                id=card_id,
                user_id=user_id
            ).first()
            
            if not card:
                return False
            
            card.update_balance()
            card.update_minimum_payment()
            db.session.commit()
            return True
            
        except Exception:
            db.session.rollback()
            return False
