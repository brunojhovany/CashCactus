"""Merge heads: encryption + placeholder

Revision ID: 2_merge_heads
Revises: 1_encrypt_tx, 9170ffa36099
Create Date: 2025-09-05

Este merge consolida las dos ramas que divergieron desde '0b21c29b8e76'.
No realiza cambios de esquema adicionales.
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = '2_merge_heads'
down_revision = ('1_encrypt_tx', '9170ffa36099')
branch_labels = None
depends_on = None


def upgrade():  # noqa: D401
    """No-op merge."""
    pass


def downgrade():  # noqa: D401
    """No-op (mantener merge)."""
    pass
