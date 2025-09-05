"""Empty placeholder migration (no-op)

Revision ID: 0b21c29b8e76
Revises: 0001
Create Date: 2025-09-01
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = '0b21c29b8e76'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():  # noqa: D401
	"""No changes (placeholder)."""
	pass


def downgrade():  # noqa: D401
	"""No changes (placeholder)."""
	pass
