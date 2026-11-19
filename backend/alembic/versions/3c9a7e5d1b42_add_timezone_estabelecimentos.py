"""Fuso horário por estabelecimento

Revision ID: 3c9a7e5d1b42
Revises: 1f6e2b61bdd1
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa

revision = '3c9a7e5d1b42'
down_revision = '1f6e2b61bdd1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'estabelecimentos',
        sa.Column('timezone', sa.String(64), nullable=False, server_default='America/Sao_Paulo'),
    )


def downgrade() -> None:
    op.drop_column('estabelecimentos', 'timezone')
