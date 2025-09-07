"""Add encrypted numeric columns for amounts and balances.

Revision ID: 4_encrypt_numeric_fields
Revises: 3_drop_legacy_plaintext_columns
Create Date: 2025-09-05

- transactions.amount_enc (BLOB)
- accounts.balance_enc (BLOB) + enc_version
- credit_cards.current_balance_enc (BLOB) + enc_version

Leaves legacy float columns in place but nullable, app stops writing them.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '4_encrypt_numeric_fields'
down_revision = '3_drop_legacy_plaintext'
branch_labels = None
depends_on = None


def _add_column_if_missing(table, column, coltype):
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {c['name'] for c in inspector.get_columns(table)}
    if column not in cols:
        op.add_column(table, sa.Column(column, coltype, nullable=True))


def upgrade():
    # transactions.amount_enc
    _add_column_if_missing('transactions', 'amount_enc', sa.LargeBinary())

    # accounts.balance_enc and enc_version
    _add_column_if_missing('accounts', 'balance_enc', sa.LargeBinary())
    _add_column_if_missing('accounts', 'enc_version', sa.SmallInteger())

    # credit_cards.current_balance_enc and enc_version
    _add_column_if_missing('credit_cards', 'current_balance_enc', sa.LargeBinary())
    _add_column_if_missing('credit_cards', 'enc_version', sa.SmallInteger())


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    def _drop_if_exists(table, column):
        cols = {c['name'] for c in inspector.get_columns(table)}
        if column in cols:
            op.drop_column(table, column)

    _drop_if_exists('transactions', 'amount_enc')
    _drop_if_exists('accounts', 'balance_enc')
    _drop_if_exists('accounts', 'enc_version')
    _drop_if_exists('credit_cards', 'current_balance_enc')
    _drop_if_exists('credit_cards', 'enc_version')
