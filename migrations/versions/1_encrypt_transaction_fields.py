"""Introduce columnas cifradas para campos sensibles en transactions

Revision ID: 1_encrypt_tx
Revises: 0b21c29b8e76
Create Date: 2025-09-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '1_encrypt_tx'
down_revision = '0b21c29b8e76'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    if 'transactions' not in tables:
        return
    existing_cols = {c['name'] for c in inspector.get_columns('transactions')}
    # Agregar columnas nuevas si faltan
    add_cols = []
    mapping = {
        'description_enc': sa.LargeBinary(),
        'description_bidx': sa.String(length=64),
        'notes_enc': sa.LargeBinary(),
        'notes_bidx': sa.String(length=64),
        'creditor_name_enc': sa.LargeBinary(),
        'creditor_name_bidx': sa.String(length=64),
        'enc_version': sa.SmallInteger(),
    }
    for col, typ in mapping.items():
        if col not in existing_cols:
            add_cols.append(sa.Column(col, typ, nullable=True))
    for col in add_cols:
        try:
            op.add_column('transactions', col)
        except Exception:
            pass
    # Índices para blind indexes
    try:
        idx_names = {ix['name'] for ix in inspector.get_indexes('transactions')}
        if 'ix_transactions_description_bidx' not in idx_names and 'description_bidx' in mapping.keys():
            op.create_index('ix_transactions_description_bidx', 'transactions', ['description_bidx'])
        if 'ix_transactions_notes_bidx' not in idx_names and 'notes_bidx' in mapping.keys():
            op.create_index('ix_transactions_notes_bidx', 'transactions', ['notes_bidx'])
        if 'ix_transactions_creditor_name_bidx' not in idx_names and 'creditor_name_bidx' in mapping.keys():
            op.create_index('ix_transactions_creditor_name_bidx', 'transactions', ['creditor_name_bidx'])
    except Exception:
        pass
    # Inicializar enc_version en 1 para filas existentes
    try:
        bind.execute(text("UPDATE transactions SET enc_version = 1 WHERE enc_version IS NULL"))
    except Exception:
        pass
    # NOTA: No se realiza migración automática de datos antiguos en claro porque
    # el modelo ya no tiene esas columnas; si existían (description, notes, creditor_name)
    # en instalaciones previas, el admin debe ejecutar un script de migración
    # personalizado antes de eliminar columnas antiguas. Mantener compat.


def downgrade():
    # Downgrade no elimina columnas para evitar pérdida de datos cifrados.
    pass
