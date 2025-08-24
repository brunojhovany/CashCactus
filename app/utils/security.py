from flask import abort
from flask_login import current_user
from app.models.account import Account
from app.models.credit_card import CreditCard

def get_user_account(account_id, active_only=False):
    """Obtener una cuenta que pertenezca al usuario actual o abortar 404."""
    query = Account.query.filter_by(id=account_id, user_id=current_user.id)
    if active_only:
        query = query.filter_by(is_active=True)
    account = query.first()
    if not account:
        abort(404)
    return account

def get_user_credit_card(card_id, active_only=False):
    """Obtener una tarjeta que pertenezca al usuario actual o abortar 404."""
    query = CreditCard.query.filter_by(id=card_id, user_id=current_user.id)
    if active_only:
        query = query.filter_by(is_active=True)
    card = query.first()
    if not card:
        abort(404)
    return card

def ensure_transaction_account_ownership(account_id):
    """Validar que la cuenta exista y sea del usuario actual para uso en transacciones."""
    if not account_id:
        return None
    return get_user_account(account_id)

def ensure_transaction_credit_card_ownership(card_id):
    """Validar que la tarjeta exista y sea del usuario actual para uso en transacciones."""
    if not card_id:
        return None
    return get_user_credit_card(card_id)
