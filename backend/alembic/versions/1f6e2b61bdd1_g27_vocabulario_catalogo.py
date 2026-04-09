"""G27 — Vocabulário configurável + catálogo TipoAtendimento

Revision ID: 1f6e2b61bdd1
Revises: e58f016718ba
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa

revision = '1f6e2b61bdd1'
down_revision = 'e58f016718ba'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Adicionar labels de vocabulário em estabelecimentos
    op.add_column('estabelecimentos', sa.Column('label_profissional', sa.String(50),
                  nullable=False, server_default='Médico'))
    op.add_column('estabelecimentos', sa.Column('label_atendimento', sa.String(50),
                  nullable=False, server_default='Consulta'))
    op.add_column('estabelecimentos', sa.Column('label_cliente', sa.String(50),
                  nullable=False, server_default='Paciente'))
    op.add_column('estabelecimentos', sa.Column('label_especialidade', sa.String(50),
                  nullable=False, server_default='Especialidade'))

    # 2. Criar tabela tipo_atendimentos
    op.create_table(
        'tipo_atendimentos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('estabelecimento_id', sa.Integer(),
                  sa.ForeignKey('estabelecimentos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nome', sa.String(100), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('duracao_min', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('preco', sa.Numeric(10, 2), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_tipo_atendimentos_estabelecimento', 'tipo_atendimentos', ['estabelecimento_id'])

    # 3. Criar tabela profissional_tipo_atendimentos (N:N)
    op.create_table(
        'profissional_tipo_atendimentos',
        sa.Column('profissional_id', sa.Integer(),
                  sa.ForeignKey('profissionais.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo_atendimento_id', sa.Integer(),
                  sa.ForeignKey('tipo_atendimentos.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('profissional_id', 'tipo_atendimento_id'),
    )


def downgrade() -> None:
    op.drop_table('profissional_tipo_atendimentos')
    op.drop_index('ix_tipo_atendimentos_estabelecimento', table_name='tipo_atendimentos')
    op.drop_table('tipo_atendimentos')
    op.drop_column('estabelecimentos', 'label_especialidade')
    op.drop_column('estabelecimentos', 'label_cliente')
    op.drop_column('estabelecimentos', 'label_atendimento')
    op.drop_column('estabelecimentos', 'label_profissional')
