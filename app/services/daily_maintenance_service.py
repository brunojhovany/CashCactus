from datetime import datetime
from app import db
from app.models.user import User
from app.models.account import Account
from app.models.credit_card import CreditCard


class DailyMaintenanceService:
    """Tareas diarias: ajustar cuentas, crear asientos automáticos y actualizar balances."""

    @staticmethod
    def run_daily_maintenance():
        """Ejecuta el mantenimiento diario para todos los usuarios.

        Acciones:
        - Actualizar balances de cuentas y tarjetas basados en transacciones.
        - Aplicar rendimientos/intereses de inversión según frecuencia configurada (si corresponde).
        - Recalcular pagos mínimos de tarjetas.
        Nota: No aplica intereses de cuentas de deuda automáticamente a diario para evitar duplicados.
        """
        # Procesar usuarios por lotes
        users = User.query.all()

        total_accounts = 0
        total_cards = 0
        created_auto_entries = 0

        for user in users:
            # Cuentas del usuario
            accounts = Account.query.filter_by(user_id=user.id, is_active=True).all()
            for account in accounts:
                total_accounts += 1

                # Aplicar rendimientos de inversión/ahorro si corresponde (idempotente por _should_apply_interest)
                try:
                    if not account.is_debt_account and getattr(account, 'generates_interest', False):
                        freq = (account.compound_frequency or 'monthly').lower()
                        # Normalizar valores inconsistentes del formulario
                        if freq in ('annual', 'annually', 'semi_annual'):
                            period_type = 'annually'
                        elif freq == 'quarterly':
                            period_type = 'quarterly'
                        else:
                            period_type = 'monthly'

                        tx = account.apply_investment_interest(period_type=period_type)
                        if tx is not None:
                            created_auto_entries += 1
                except Exception:
                    # Continuar con siguientes cuentas sin interrumpir el batch
                    pass

                # Recalcular balance en base a transacciones
                try:
                    account.update_balance()
                except Exception:
                    pass

            # Tarjetas de crédito del usuario
            cards = CreditCard.query.filter_by(user_id=user.id, is_active=True).all()
            for card in cards:
                total_cards += 1
                try:
                    card.update_balance()
                    card.update_minimum_payment()
                except Exception:
                    pass

        # Commit de todos los cambios
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return {
            'users': len(users),
            'accounts_processed': total_accounts,
            'cards_processed': total_cards,
            'auto_entries_created': created_auto_entries,
            'run_at': datetime.utcnow().isoformat()
        }
