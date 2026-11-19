"""Papel timbrado por unidade: logo, marca-d'agua e rodape dos documentos clinicos

Revision ID: 8b2d5f0a3c74
Revises: 7a1c4e9f2b63
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa

revision = '8b2d5f0a3c74'
down_revision = '7a1c4e9f2b63'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'papeis_timbrados',
        sa.Column(
            'estabelecimento_id', sa.Integer(),
            sa.ForeignKey('estabelecimentos.id', ondelete='CASCADE'), primary_key=True,
        ),
        sa.Column('logo', sa.LargeBinary(), nullable=True),
        sa.Column('marca_dagua', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('rodape', sa.String(300), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('papeis_timbrados')
