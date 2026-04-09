"""G25 — Refatoração Agnóstica: renomear tabelas, colunas, enums + novos status + historico

Revision ID: 12f315194748
Revises: b7d6df81f0c1
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '12f315194748'
down_revision = 'b7d6df81f0c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Renomear tabelas
    op.rename_table('medicos', 'profissionais')
    op.rename_table('consultas', 'atendimentos')
    op.rename_table('pacientes', 'clientes')
    op.rename_table('medico_estabelecimentos', 'profissional_estabelecimentos')

    # 2. Renomear coluna crm → registro_profissional em profissionais
    op.alter_column('profissionais', 'crm',
                    new_column_name='registro_profissional')

    # 3. Renomear duracao_consulta_min → duracao_atendimento_min em profissionais
    op.alter_column('profissionais', 'duracao_consulta_min',
                    new_column_name='duracao_atendimento_min')

    # 4. Renomear duracao_consulta_min → duracao_atendimento_min em profissional_estabelecimentos
    op.alter_column('profissional_estabelecimentos', 'duracao_consulta_min',
                    new_column_name='duracao_atendimento_min')

    # 5. Renomear FK medico_id → profissional_id em profissional_estabelecimentos
    op.alter_column('profissional_estabelecimentos', 'medico_id',
                    new_column_name='profissional_id')

    # 6. Renomear FK medico_id → profissional_id em atendimentos
    op.alter_column('atendimentos', 'medico_id',
                    new_column_name='profissional_id')

    # 7. Renomear FK paciente_id → cliente_id em atendimentos
    op.alter_column('atendimentos', 'paciente_id',
                    new_column_name='cliente_id')

    # 7b. Renomear FK paciente_id → cliente_id em sessoes_chat (se existir)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessoes_chat' AND column_name='paciente_id') THEN
                ALTER TABLE sessoes_chat RENAME COLUMN paciente_id TO cliente_id;
            END IF;
        END $$
    """)
    # 7c. Renomear FK paciente_id → cliente_id em sessoes_historico (se existir)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessoes_historico' AND column_name='paciente_id') THEN
                ALTER TABLE sessoes_historico RENAME COLUMN paciente_id TO cliente_id;
            END IF;
        END $$
    """)
    # 7d. Renomear FK paciente_id → cliente_id em fila_espera (se existir)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='fila_espera' AND column_name='paciente_id') THEN
                ALTER TABLE fila_espera RENAME COLUMN paciente_id TO cliente_id;
            END IF;
        END $$
    """)

    # 8. Renomear FK medico_id → profissional_id em slots
    op.alter_column('slots', 'medico_id',
                    new_column_name='profissional_id')

    # 8b. Renomear FK medico_id → profissional_id em usuarios (se existir)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='usuarios' AND column_name='medico_id') THEN
                ALTER TABLE usuarios RENAME COLUMN medico_id TO profissional_id;
            END IF;
        END $$
    """)

    # 9. Renomear unique constraint em profissional_estabelecimentos
    op.execute('ALTER TABLE profissional_estabelecimentos RENAME CONSTRAINT uq_medico_estabelecimento TO uq_profissional_estabelecimento')

    # 9b. Renomear indexes de profissional_estabelecimentos
    op.execute('ALTER INDEX IF EXISTS ix_medico_estabelecimentos_medico_id RENAME TO ix_profissional_estabelecimentos_profissional_id')
    op.execute('ALTER INDEX IF EXISTS ix_medico_estabelecimentos_estabelecimento_id RENAME TO ix_profissional_estabelecimentos_estabelecimento_id')

    # 10. Renomear enum consulta_status → atendimento_status e adicionar novos valores
    op.execute("ALTER TYPE consulta_status RENAME TO atendimento_status")
    op.execute("ALTER TYPE atendimento_status ADD VALUE IF NOT EXISTS 'PRESENTE'")
    op.execute("ALTER TYPE atendimento_status ADD VALUE IF NOT EXISTS 'AGUARDANDO_ANAMNESE'")
    op.execute("ALTER TYPE atendimento_status ADD VALUE IF NOT EXISTS 'ANAMNESE_PREENCHIDA'")
    op.execute("ALTER TYPE atendimento_status ADD VALUE IF NOT EXISTS 'FICHA_CONCLUIDA'")
    op.execute("ALTER TYPE atendimento_status ADD VALUE IF NOT EXISTS 'AGUARDANDO_PAGAMENTO'")
    op.execute("ALTER TYPE atendimento_status ADD VALUE IF NOT EXISTS 'PAGO'")
    op.execute("ALTER TYPE atendimento_status ADD VALUE IF NOT EXISTS 'AGUARDANDO_PROFISSIONAL'")
    op.execute("ALTER TYPE atendimento_status ADD VALUE IF NOT EXISTS 'EM_ATENDIMENTO'")

    # 11. Renomear demais enums
    op.execute("ALTER TYPE consulta_tipo RENAME TO atendimento_tipo")
    op.execute("ALTER TYPE consulta_urgencia RENAME TO atendimento_urgencia")
    op.execute("ALTER TYPE consulta_canal RENAME TO atendimento_canal")

    # 12. Renomear enum tipo_atendimento → modalidade_pagamento (era CONVENIO/PARTICULAR em clientes)
    op.execute("ALTER TYPE tipo_atendimento RENAME TO modalidade_pagamento")

    # 13. Criar tabela atendimento_status_historico
    op.create_table(
        'atendimento_status_historico',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('atendimento_id', sa.Integer(),
                  sa.ForeignKey('atendimentos.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('status_anterior', postgresql.ENUM(
            'AGENDADA','CONFIRMADA','CANCELADA','PRESENTE',
            'AGUARDANDO_ANAMNESE','ANAMNESE_PREENCHIDA','FICHA_CONCLUIDA',
            'AGUARDANDO_PAGAMENTO','PAGO','AGUARDANDO_PROFISSIONAL',
            'EM_ATENDIMENTO','REALIZADA','FALTA',
            name='atendimento_status', create_type=False
        ), nullable=True),
        sa.Column('status_novo', postgresql.ENUM(
            'AGENDADA','CONFIRMADA','CANCELADA','PRESENTE',
            'AGUARDANDO_ANAMNESE','ANAMNESE_PREENCHIDA','FICHA_CONCLUIDA',
            'AGUARDANDO_PAGAMENTO','PAGO','AGUARDANDO_PROFISSIONAL',
            'EM_ATENDIMENTO','REALIZADA','FALTA',
            name='atendimento_status', create_type=False
        ), nullable=False),
        sa.Column('usuario_id', sa.Integer(),
                  sa.ForeignKey('usuarios.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_atendimento_historico_atendimento_created',
                    'atendimento_status_historico',
                    ['atendimento_id', 'created_at'])
    op.create_index('ix_atendimento_historico_usuario',
                    'atendimento_status_historico',
                    ['usuario_id'])


def downgrade() -> None:
    # NOTE: Novos valores de enum (PRESENTE, AGUARDANDO_ANAMNESE, etc.)
    # NÃO são removidos pois PostgreSQL não suporta DROP VALUE em enums.
    # O downgrade restaura apenas o nome do tipo.
    op.drop_table('atendimento_status_historico')
    op.execute("ALTER TYPE atendimento_status RENAME TO consulta_status")
    op.execute("ALTER TYPE atendimento_tipo RENAME TO consulta_tipo")
    op.execute("ALTER TYPE atendimento_urgencia RENAME TO consulta_urgencia")
    op.execute("ALTER TYPE atendimento_canal RENAME TO consulta_canal")
    op.execute("ALTER TYPE modalidade_pagamento RENAME TO tipo_atendimento")
    op.alter_column('slots', 'profissional_id', new_column_name='medico_id')
    op.alter_column('atendimentos', 'cliente_id', new_column_name='paciente_id')
    op.alter_column('atendimentos', 'profissional_id', new_column_name='medico_id')
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='fila_espera' AND column_name='cliente_id') THEN
                ALTER TABLE fila_espera RENAME COLUMN cliente_id TO paciente_id;
            END IF;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessoes_historico' AND column_name='cliente_id') THEN
                ALTER TABLE sessoes_historico RENAME COLUMN cliente_id TO paciente_id;
            END IF;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessoes_chat' AND column_name='cliente_id') THEN
                ALTER TABLE sessoes_chat RENAME COLUMN cliente_id TO paciente_id;
            END IF;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='usuarios' AND column_name='profissional_id') THEN
                ALTER TABLE usuarios RENAME COLUMN profissional_id TO medico_id;
            END IF;
        END $$
    """)
    op.execute('ALTER INDEX IF EXISTS ix_profissional_estabelecimentos_profissional_id RENAME TO ix_medico_estabelecimentos_medico_id')
    op.execute('ALTER INDEX IF EXISTS ix_profissional_estabelecimentos_estabelecimento_id RENAME TO ix_medico_estabelecimentos_estabelecimento_id')
    op.execute('ALTER TABLE profissional_estabelecimentos RENAME CONSTRAINT uq_profissional_estabelecimento TO uq_medico_estabelecimento')
    op.alter_column('profissional_estabelecimentos', 'profissional_id', new_column_name='medico_id')
    op.alter_column('profissional_estabelecimentos', 'duracao_atendimento_min', new_column_name='duracao_consulta_min')
    op.alter_column('profissionais', 'duracao_atendimento_min', new_column_name='duracao_consulta_min')
    op.alter_column('profissionais', 'registro_profissional', new_column_name='crm')
    op.rename_table('profissional_estabelecimentos', 'medico_estabelecimentos')
    op.rename_table('clientes', 'pacientes')
    op.rename_table('atendimentos', 'consultas')
    op.rename_table('profissionais', 'medicos')
