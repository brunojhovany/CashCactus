"""Bootstrap + asegurar columnas oauth/avatar

Revision ID: 0001
Revises: None
Create Date: 2025-08-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # La tabla users puede existir (producción) o no (nueva instalación).
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('username', sa.String(length=80), nullable=False, unique=True),
            sa.Column('email', sa.String(length=120), nullable=False, unique=True),
            sa.Column('password_hash', sa.String(length=200), nullable=False),
            sa.Column('oauth_provider', sa.String(length=50), nullable=True),
            sa.Column('oauth_sub', sa.String(length=255), nullable=True),
            sa.Column('avatar_url', sa.String(length=300), nullable=True),
            sa.Column('is_beta_allowed', sa.Boolean(), nullable=True, server_default=sa.text('0')),
            sa.Column('first_name', sa.String(length=50), nullable=False),
            sa.Column('last_name', sa.String(length=50), nullable=False),
            sa.Column('monthly_income', sa.Float(), nullable=True, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_users_oauth_sub', 'users', ['oauth_sub'])
    else:
        # Asegurar columnas que pudieron faltar
        existing_cols = {c['name'] for c in inspector.get_columns('users')}
        to_add = []
        if 'oauth_provider' not in existing_cols:
            to_add.append(sa.Column('oauth_provider', sa.String(length=50), nullable=True))
        if 'oauth_sub' not in existing_cols:
            to_add.append(sa.Column('oauth_sub', sa.String(length=255), nullable=True))
        if 'avatar_url' not in existing_cols:
            to_add.append(sa.Column('avatar_url', sa.String(length=300), nullable=True))
        if 'is_beta_allowed' not in existing_cols:
            to_add.append(sa.Column('is_beta_allowed', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        if 'monthly_income' not in existing_cols:
            to_add.append(sa.Column('monthly_income', sa.Float(), nullable=True, server_default=sa.text('0')))
        if to_add:
            for col in to_add:
                try:
                    op.add_column('users', col)
                except Exception:
                    pass
        # Índice oauth_sub
        try:
            indexes = {ix['name'] for ix in inspector.get_indexes('users')}
            if 'ix_users_oauth_sub' not in indexes and 'oauth_sub' in existing_cols:
                op.create_index('ix_users_oauth_sub', 'users', ['oauth_sub'])
        except Exception:
            pass


def downgrade():
    # Downgrade simplificado: no eliminar columnas para evitar pérdida de datos en rollback.
    pass