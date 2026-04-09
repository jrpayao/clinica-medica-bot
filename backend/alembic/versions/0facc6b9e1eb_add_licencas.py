"""add_licencas

Revision ID: 0facc6b9e1eb
Revises: 7d076b3ea7af
Create Date: 2026-04-04 01:43:03.985610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0facc6b9e1eb'
down_revision: Union[str, None] = '7d076b3ea7af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'licencas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('estabelecimento_id', sa.Integer(), nullable=False),
        sa.Column('plano', sa.String(length=20), server_default='basico', nullable=False),
        sa.Column('status', sa.Enum('TRIAL', 'ATIVA', 'EXPIRADA', 'SUSPENSA', name='licenca_status'), server_default='TRIAL', nullable=False),
        sa.Column('modalidade', sa.String(length=10), server_default='mensal', nullable=False),
        sa.Column('trial_expira_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('licenca_expira_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('suspensa_por', sa.Integer(), nullable=True),
        sa.Column('suspensa_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('motivo_suspensao', sa.String(length=500), nullable=True),
        sa.Column('gateway_customer_id', sa.String(length=100), nullable=True),
        sa.Column('gateway_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['estabelecimento_id'], ['estabelecimentos.id']),
        sa.ForeignKeyConstraint(['suspensa_por'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_licencas_estabelecimento_id'), 'licencas', ['estabelecimento_id'], unique=True)
    op.create_index(op.f('ix_licencas_gateway_customer_id'), 'licencas', ['gateway_customer_id'], unique=False)
    op.create_index(op.f('ix_licencas_gateway_subscription_id'), 'licencas', ['gateway_subscription_id'], unique=False)

    # Backfill: criar licença TRIAL para cada estabelecimento existente
    # trial_expira_em = created_at + 14 dias, plano = valor atual de estabelecimentos.plano
    op.execute("""
        INSERT INTO licencas (
            estabelecimento_id, plano, status, modalidade,
            trial_expira_em, created_at, updated_at
        )
        SELECT
            id,
            plano,
            'TRIAL',
            'mensal',
            created_at + INTERVAL '14 days',
            now(),
            now()
        FROM estabelecimentos
        ON CONFLICT (estabelecimento_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_licencas_gateway_subscription_id'), table_name='licencas')
    op.drop_index(op.f('ix_licencas_gateway_customer_id'), table_name='licencas')
    op.drop_index(op.f('ix_licencas_estabelecimento_id'), table_name='licencas')
    op.drop_table('licencas')
    op.execute("DROP TYPE IF EXISTS licenca_status")
