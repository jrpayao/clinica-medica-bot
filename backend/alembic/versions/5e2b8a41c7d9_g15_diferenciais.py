"""G15 — fila de espera (oferta de slot), motivo de cancelamento, reagendamento e avaliações

Revision ID: 5e2b8a41c7d9
Revises: 3c9a7e5d1b42
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '5e2b8a41c7d9'
down_revision = '3c9a7e5d1b42'
branch_labels = None
depends_on = None

MOTIVO = postgresql.ENUM('PACIENTE', 'MEDICO', 'ESTABELECIMENTO', 'SISTEMA', name='motivo_cancelamento')
REAGENDAMENTO = postgresql.ENUM(
    'PENDENTE', 'ACEITA', 'RECUSADA', 'EXPIRADA', 'SEM_HORARIO', 'SEM_CONTATO', 'RESOLVIDA',
    name='reagendamento_status',
)
CANAL = postgresql.ENUM('WHATSAPP', 'PORTAL', name='avaliacao_canal')


def upgrade() -> None:
    bind = op.get_bind()
    for tipo in (MOTIVO, REAGENDAMENTO, CANAL):
        tipo.create(bind, checkfirst=True)

    op.add_column(
        'atendimentos',
        sa.Column(
            'motivo_cancelamento',
            postgresql.ENUM(name='motivo_cancelamento', create_type=False),
            nullable=True,
        ),
    )
    op.add_column('atendimentos', sa.Column('resumo_enviado_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'atendimentos', sa.Column('avaliacao_solicitada_em', sa.DateTime(timezone=True), nullable=True)
    )

    op.add_column(
        'fila_espera', sa.Column('slot_ofertado_id', sa.Integer(), sa.ForeignKey('slots.id'), nullable=True)
    )
    op.add_column(
        'fila_espera', sa.Column('tentativas', sa.Integer(), nullable=False, server_default='0')
    )

    op.create_table(
        'reagendamento_ofertas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'atendimento_id', sa.Integer(),
            sa.ForeignKey('atendimentos.id', ondelete='CASCADE'), nullable=False, index=True,
        ),
        sa.Column('cliente_id', sa.Integer(), sa.ForeignKey('clientes.id'), nullable=False),
        sa.Column(
            'estabelecimento_id', sa.Integer(),
            sa.ForeignKey('estabelecimentos.id'), nullable=False, index=True,
        ),
        sa.Column('slot_ids', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column(
            'status', postgresql.ENUM(name='reagendamento_status', create_type=False),
            nullable=False, server_default='PENDENTE',
        ),
        sa.Column(
            'novo_atendimento_id', sa.Integer(),
            sa.ForeignKey('atendimentos.id', ondelete='SET NULL'), nullable=True,
        ),
        sa.Column('enviado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('respondido_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'avaliacoes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'atendimento_id', sa.Integer(),
            sa.ForeignKey('atendimentos.id', ondelete='CASCADE'), nullable=False, unique=True,
        ),
        sa.Column('cliente_id', sa.Integer(), sa.ForeignKey('clientes.id'), nullable=False, index=True),
        sa.Column(
            'profissional_id', sa.Integer(), sa.ForeignKey('profissionais.id'), nullable=False, index=True
        ),
        sa.Column(
            'estabelecimento_id', sa.Integer(),
            sa.ForeignKey('estabelecimentos.id'), nullable=False, index=True,
        ),
        sa.Column('nota', sa.Integer(), nullable=False),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('canal', postgresql.ENUM(name='avaliacao_canal', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('nota BETWEEN 1 AND 5', name='ck_avaliacoes_nota'),
    )


def downgrade() -> None:
    op.drop_table('avaliacoes')
    op.drop_table('reagendamento_ofertas')
    op.drop_column('fila_espera', 'tentativas')
    op.drop_column('fila_espera', 'slot_ofertado_id')
    op.drop_column('atendimentos', 'avaliacao_solicitada_em')
    op.drop_column('atendimentos', 'resumo_enviado_em')
    op.drop_column('atendimentos', 'motivo_cancelamento')
    bind = op.get_bind()
    for tipo in (CANAL, REAGENDAMENTO, MOTIVO):
        tipo.drop(bind, checkfirst=True)
