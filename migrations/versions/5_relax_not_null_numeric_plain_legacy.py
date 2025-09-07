"""Relax NOT NULL on legacy numeric columns to support encrypted values.

Revision ID: 5_relax_not_null_numeric_plain_legacy
Revises: 4_encrypt_numeric_fields
Create Date: 2025-09-06

- transactions.amount -> DROP NOT NULL
- accounts.balance -> DROP NOT NULL
- credit_cards.current_balance -> DROP NOT NULL

Safe on Postgres; SQLite no-op.
"""
from alembic import op
from sqlalchemy import inspect

revision = '5_relax_nn_numeric_plain'
down_revision = '4_encrypt_numeric_fields'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    # Drop NOT NULL if present
    insp = inspect(bind)
    txn_cols = {c['name']: c for c in insp.get_columns('transactions')}
    if 'amount' in txn_cols and not txn_cols['amount'].get('nullable', True):
        op.execute('ALTER TABLE transactions ALTER COLUMN amount DROP NOT NULL')
    acct_cols = {c['name']: c for c in insp.get_columns('accounts')}
    if 'balance' in acct_cols and not acct_cols['balance'].get('nullable', True):
        op.execute('ALTER TABLE accounts ALTER COLUMN balance DROP NOT NULL')
    cc_cols = {c['name']: c for c in insp.get_columns('credit_cards')}
    if 'current_balance' in cc_cols and not cc_cols['current_balance'].get('nullable', True):
        op.execute('ALTER TABLE credit_cards ALTER COLUMN current_balance DROP NOT NULL')


def downgrade():
    # No revertimos NOT NULL automáticamente para evitar romper datos existentes
    pass
