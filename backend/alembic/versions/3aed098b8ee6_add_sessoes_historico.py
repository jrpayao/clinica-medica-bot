"""add_sessoes_historico

Revision ID: 3aed098b8ee6
Revises: 3fd7ef4fde57
Create Date: 2026-04-04 11:38:47.915411

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3aed098b8ee6'
down_revision: Union[str, None] = '3fd7ef4fde57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('sessoes_historico',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('paciente_id', sa.Integer(), nullable=False),
    sa.Column('sessao_id', sa.Integer(), nullable=True),
    sa.Column('sintomas_relatados', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('especialidade_sugerida', sa.String(length=100), nullable=True),
    sa.Column('urgencia', sa.String(length=50), nullable=True),
    sa.Column('resumo_triagem', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['paciente_id'], ['pacientes.id'], ),
    sa.ForeignKeyConstraint(['sessao_id'], ['sessoes_chat.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sessoes_historico_paciente_id'), 'sessoes_historico', ['paciente_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sessoes_historico_paciente_id'), table_name='sessoes_historico')
    op.drop_table('sessoes_historico')
