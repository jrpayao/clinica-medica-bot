"""G26 — Módulo de Convênios: expand convenios, add convenio_planos, cliente_convenios, atendimento fields

Revision ID: e58f016718ba
Revises: 12f315194748
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e58f016718ba'
down_revision: Union[str, None] = '12f315194748'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Expandir tabela convenios
    op.add_column('convenios', sa.Column('codigo_ans', sa.String(20), nullable=True))
    op.add_column('convenios', sa.Column('cnpj', sa.String(14), nullable=True))
    op.add_column('convenios', sa.Column('telefone_autorizacao', sa.String(20), nullable=True))
    op.add_column('convenios', sa.Column('email', sa.String(254), nullable=True))
    op.add_column('convenios', sa.Column('website', sa.String(500), nullable=True))

    # 2. Criar tabela convenio_planos
    op.create_table(
        'convenio_planos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('convenio_id', sa.Integer(),
                  sa.ForeignKey('convenios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nome', sa.String(100), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_convenio_planos_convenio', 'convenio_planos', ['convenio_id'])

    # 3. Criar tabela cliente_convenios
    op.create_table(
        'cliente_convenios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cliente_id', sa.Integer(),
                  sa.ForeignKey('clientes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('convenio_id', sa.Integer(),
                  sa.ForeignKey('convenios.id'), nullable=False),
        sa.Column('plano_id', sa.Integer(),
                  sa.ForeignKey('convenio_planos.id'), nullable=True),
        sa.Column('numero_carteirinha', sa.String(50), nullable=False),
        sa.Column('nome_titular', sa.String(200), nullable=True),
        sa.Column('validade', sa.Date(), nullable=True),
        sa.Column('principal', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_cliente_convenios_cliente', 'cliente_convenios', ['cliente_id'])
    op.create_index('ix_cliente_convenios_convenio', 'cliente_convenios', ['convenio_id'])

    # 4. Adicionar campos de convênio em atendimentos
    op.add_column('atendimentos',
        sa.Column('cliente_convenio_id', sa.Integer(),
                  sa.ForeignKey('cliente_convenios.id', ondelete='SET NULL'),
                  nullable=True))
    op.add_column('atendimentos',
        sa.Column('numero_autorizacao', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('atendimentos', 'numero_autorizacao')
    op.drop_column('atendimentos', 'cliente_convenio_id')
    op.drop_table('cliente_convenios')
    op.drop_table('convenio_planos')
    op.drop_column('convenios', 'website')
    op.drop_column('convenios', 'email')
    op.drop_column('convenios', 'telefone_autorizacao')
    op.drop_column('convenios', 'cnpj')
    op.drop_column('convenios', 'codigo_ans')
