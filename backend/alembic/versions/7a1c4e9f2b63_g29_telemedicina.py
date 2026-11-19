"""G29 — telemedicina: horários online, modalidade do atendimento, sala, registro e documentos clínicos

Revision ID: 7a1c4e9f2b63
Revises: 5e2b8a41c7d9
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '7a1c4e9f2b63'
down_revision = '5e2b8a41c7d9'
branch_labels = None
depends_on = None

MODALIDADE = postgresql.ENUM('PRESENCIAL', 'ONLINE', name='modalidade_atendimento')
TIPO_DOC = postgresql.ENUM('RECEITA', 'ATESTADO', name='tipo_documento')


def upgrade() -> None:
    bind = op.get_bind()
    MODALIDADE.create(bind, checkfirst=True)
    TIPO_DOC.create(bind, checkfirst=True)

    op.add_column('slots', sa.Column('aceita_online', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        'atendimentos',
        sa.Column(
            'modalidade', postgresql.ENUM(name='modalidade_atendimento', create_type=False),
            nullable=False, server_default='PRESENCIAL',
        ),
    )

    op.create_table(
        'teleconsultas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'atendimento_id', sa.Integer(),
            sa.ForeignKey('atendimentos.id', ondelete='CASCADE'), nullable=False, unique=True,
        ),
        sa.Column('sala', sa.String(80), nullable=False, unique=True),
        sa.Column('token_paciente', sa.String(64), nullable=False),
        sa.Column('termo_versao', sa.String(20), nullable=True),
        sa.Column('consentimento_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consentimento_ip', sa.String(64), nullable=True),
        sa.Column('paciente_entrou_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paciente_visto_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('link_enviado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_teleconsultas_token_paciente', 'teleconsultas', ['token_paciente'], unique=True)

    op.create_table(
        'registros_clinicos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'atendimento_id', sa.Integer(),
            sa.ForeignKey('atendimentos.id', ondelete='CASCADE'), nullable=False, unique=True,
        ),
        sa.Column(
            'profissional_id', sa.Integer(), sa.ForeignKey('profissionais.id'), nullable=False, index=True
        ),
        sa.Column(
            'estabelecimento_id', sa.Integer(), sa.ForeignKey('estabelecimentos.id'), nullable=False, index=True
        ),
        sa.Column('queixa', sa.Text(), nullable=True),
        sa.Column('evolucao', sa.Text(), nullable=True),
        sa.Column('conduta', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'documentos_clinicos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'atendimento_id', sa.Integer(),
            sa.ForeignKey('atendimentos.id', ondelete='CASCADE'), nullable=False, index=True,
        ),
        sa.Column('profissional_id', sa.Integer(), sa.ForeignKey('profissionais.id'), nullable=False),
        sa.Column('cliente_id', sa.Integer(), sa.ForeignKey('clientes.id'), nullable=False),
        sa.Column(
            'estabelecimento_id', sa.Integer(), sa.ForeignKey('estabelecimentos.id'), nullable=False, index=True
        ),
        sa.Column('tipo', postgresql.ENUM(name='tipo_documento', create_type=False), nullable=False),
        sa.Column('conteudo', postgresql.JSONB(), nullable=False),
        sa.Column('codigo', sa.String(16), nullable=False, unique=True),
        sa.Column('emitido_em', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('documentos_clinicos')
    op.drop_table('registros_clinicos')
    op.drop_index('ix_teleconsultas_token_paciente', table_name='teleconsultas')
    op.drop_table('teleconsultas')
    op.drop_column('atendimentos', 'modalidade')
    op.drop_column('slots', 'aceita_online')
    bind = op.get_bind()
    TIPO_DOC.drop(bind, checkfirst=True)
    MODALIDADE.drop(bind, checkfirst=True)
