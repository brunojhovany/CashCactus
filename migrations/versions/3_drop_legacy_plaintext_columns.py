"""Drop legacy plaintext columns from transactions.

Revision ID: 3_drop_legacy_plaintext_columns
Revises: 2_merge_heads
Create Date: 2025-09-05

Esta migración elimina las columnas plaintext antiguas (description, notes, creditor_name)
si todavía existen. Debe ejecutarse solo después de:
 1. Haber migrado los datos plaintext a los campos cifrados mediante el script
    scripts/migrate_legacy_transaction_plaintext.py
 2. Verificar que las columnas cifradas contienen los datos y que las plaintext
    no son necesarias para rollback.

La migración detecta dinámicamente si las columnas existen antes de intentar
eliminarlas (idempotente). Para SQLite se omite porque requiere table rebuild.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '3_drop_legacy_plaintext'
down_revision = '2_merge_heads'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('transactions')}
    legacy = ['description', 'notes', 'creditor_name']

    # SQLite requiere recrear tabla: omitimos para simplicidad
    if dialect == 'sqlite':
        return

    for col in legacy:
        if col in cols:
            try:
                op.drop_column('transactions', col)
            except Exception:
                pass


def downgrade():
    # Downgrade recrea columnas como texto nullable (sin restaurar datos)
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'sqlite':
        return
    existing = {c['name'] for c in inspect(bind).get_columns('transactions')}
    for name in ['description', 'notes', 'creditor_name']:
        if name not in existing:
            op.add_column('transactions', sa.Column(name, sa.Text(), nullable=True))
