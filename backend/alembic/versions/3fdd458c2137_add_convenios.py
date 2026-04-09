"""add_convenios

Revision ID: 3fdd458c2137
Revises: 0facc6b9e1eb
Create Date: 2026-04-04 11:11:07.344032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fdd458c2137'
down_revision: Union[str, None] = '0facc6b9e1eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'convenios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('estabelecimento_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['estabelecimento_id'], ['estabelecimentos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_convenios_estabelecimento_id', 'convenios', ['estabelecimento_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_convenios_estabelecimento_id', table_name='convenios')
    op.drop_table('convenios')
