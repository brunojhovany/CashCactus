"""Helpers de búsqueda sobre campos de Transaction.

Uso:
    from app.services.transaction_search import find_by_description
    results = find_by_description(user_id, "Compra super")
"""
from __future__ import annotations

from typing import List
from app.models.transaction import Transaction
from app.utils.validators import sanitize_search_term


def _normalize(value: str) -> str:
    return value.strip().lower()


def find_by_description(user_id: int, text: str) -> List[Transaction]:
    """Buscar transacciones por descripción (búsqueda parcial, case-insensitive)"""
    normalized = _normalize(text)
    if not normalized or len(normalized) < 2:
        return []
    
    # Sanitizar para prevenir inyección SQL y DoS
    sanitized = sanitize_search_term(normalized)
    
    return Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.description.ilike(f'%{sanitized}%', escape='\\')
    ).all()


def find_by_notes(user_id: int, text: str) -> List[Transaction]:
    """Buscar transacciones por notas (búsqueda parcial, case-insensitive)"""
    normalized = _normalize(text)
    if not normalized or len(normalized) < 2:
        return []
    
    # Sanitizar para prevenir inyección SQL y DoS
    sanitized = sanitize_search_term(normalized)
    
    return Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.notes.ilike(f'%{sanitized}%', escape='\\')
    ).all()


def find_by_creditor(user_id: int, creditor: str) -> List[Transaction]:
    """Buscar transacciones por nombre del acreedor (búsqueda parcial, case-insensitive)"""
    normalized = _normalize(creditor)
    if not normalized or len(normalized) < 2:
        return []
    
    # Sanitizar para prevenir inyección SQL y DoS
    sanitized = sanitize_search_term(normalized)
    
    return Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.creditor_name.ilike(f'%{sanitized}%', escape='\\')
    ).all()
