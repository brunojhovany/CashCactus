"""Helpers de búsqueda sobre campos cifrados de Transaction usando blind indexes.

Uso:
    from app.services.transaction_search import find_by_description
    results = find_by_description(user_id, "Compra super")
"""
from __future__ import annotations

from typing import List
from app.models.transaction import Transaction
from app.utils.crypto_fields import blind_index


def _normalize(value: str) -> str:
    return value.strip()


def find_by_description(user_id: int, text: str) -> List[Transaction]:
    h = blind_index(_normalize(text), 'description')
    if not h:
        return []
    return Transaction.query.filter_by(user_id=user_id, description_bidx=h).all()


def find_by_notes(user_id: int, text: str) -> List[Transaction]:
    h = blind_index(_normalize(text), 'notes')
    if not h:
        return []
    return Transaction.query.filter_by(user_id=user_id, notes_bidx=h).all()


def find_by_creditor(user_id: int, creditor: str) -> List[Transaction]:
    h = blind_index(_normalize(creditor), 'creditor_name')
    if not h:
        return []
    return Transaction.query.filter_by(user_id=user_id, creditor_name_bidx=h).all()
