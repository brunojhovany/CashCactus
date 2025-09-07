"""Drop plaintext numeric columns now that encrypted fields are enforced.

Revision ID: 6_drop_plain_numeric_columns
Revises: 5_relax_not_null_numeric_plain_legacy
Create Date: 2025-09-06

- DROP COLUMN transactions.amount
- DROP COLUMN accounts.balance
- DROP COLUMN credit_cards.current_balance

SQLite no-op; Postgres only.
"""
from alembic import op
from sqlalchemy import inspect

revision = '6_drop_plain_numeric_columns'
down_revision = '5_relax_nn_numeric_plain'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    insp = inspect(bind)
    def drop_if_exists(table, col):
        cols = {c['name'] for c in insp.get_columns(table)}
        if col in cols:
            op.drop_column(table, col)
    drop_if_exists('transactions', 'amount')
    drop_if_exists('accounts', 'balance')
    drop_if_exists('credit_cards', 'current_balance')


def downgrade():
    # No recreamos las columnas plaintext
    pass
