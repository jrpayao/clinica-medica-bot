"""add_multi_tenancy_estabelecimentos

Revision ID: ecb3f8465cc0
Revises: 89102304387e
Create Date: 2026-04-04 01:04:23.816361

Estratégia retrocompatível para tabelas com dados existentes:
  1. Criar tabelas novas (redes_estabelecimentos, estabelecimentos, medico_estabelecimentos)
  2. Inserir estabelecimento padrão (id=1)
  3. Adicionar colunas estabelecimento_id como NULLABLE com DEFAULT 1
  4. Backfill — todos os registros existentes recebem estabelecimento_id = 1
  5. Remover DEFAULT temporário e tornar NOT NULL
  6. Migrar enum usuario_role: remover ADMIN, adicionar ADMIN_GLOBAL e ADMIN_ESTABELECIMENTO
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ecb3f8465cc0"
down_revision: Union[str, None] = "89102304387e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tabelas de domínio que recebem estabelecimento_id (NOT NULL após backfill)
DOMAIN_TABLES = ["consultas", "especialidades", "pacientes", "sessoes_chat", "slots"]


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────
    # 0. Enum usuario_role: adicionar novos valores ANTES de qualquer DDL
    #    PostgreSQL exige COMMIT entre ADD VALUE e o uso do novo valor.
    #    Usamos AUTOCOMMIT para os ALTER TYPE, depois continuamos na transação.
    # ──────────────────────────────────────────────────────────
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TYPE usuario_role ADD VALUE IF NOT EXISTS 'ADMIN_GLOBAL'"))
    conn.execute(sa.text("ALTER TYPE usuario_role ADD VALUE IF NOT EXISTS 'ADMIN_ESTABELECIMENTO'"))
    # Forçar commit para tornar os novos valores visíveis ao UPDATE abaixo
    conn.execute(sa.text("COMMIT"))

    # ──────────────────────────────────────────────────────────
    # 1. Novas tabelas de tenancy
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "redes_estabelecimentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("cnpj_holding", sa.String(length=14), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cnpj_holding"),
    )

    op.create_table(
        "estabelecimentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "HOSPITAL",
                "CLINICA",
                "UBS",
                "LABORATORIO",
                "POSTO_SAUDE",
                "OUTRO",
                name="tipo_estabelecimento",
            ),
            nullable=False,
        ),
        sa.Column("plano", sa.String(length=20), server_default="basico", nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rede_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["rede_id"], ["redes_estabelecimentos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cnpj"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_estabelecimentos_rede_id", "estabelecimentos", ["rede_id"])
    op.create_index("ix_estabelecimentos_slug", "estabelecimentos", ["slug"], unique=True)

    op.create_table(
        "medico_estabelecimentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("medico_id", sa.Integer(), nullable=False),
        sa.Column("estabelecimento_id", sa.Integer(), nullable=False),
        sa.Column(
            "duracao_consulta_min",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
            comment="Pode variar por unidade (ex: 30min no hospital, 45min na clinica)",
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["estabelecimento_id"], ["estabelecimentos.id"]),
        sa.ForeignKeyConstraint(["medico_id"], ["medicos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("medico_id", "estabelecimento_id", name="uq_medico_estabelecimento"),
    )
    op.create_index(
        "ix_medico_estabelecimentos_estabelecimento_id",
        "medico_estabelecimentos",
        ["estabelecimento_id"],
    )
    op.create_index(
        "ix_medico_estabelecimentos_medico_id",
        "medico_estabelecimentos",
        ["medico_id"],
    )

    # ──────────────────────────────────────────────────────────
    # 2. Inserir estabelecimento padrão para backfill
    # ──────────────────────────────────────────────────────────
    op.execute(
        """
        INSERT INTO estabelecimentos (id, nome, cnpj, slug, tipo, plano, ativo)
        VALUES (1, 'Estabelecimento Padrão', '00000000000100', 'padrao',
                'HOSPITAL', 'basico', true)
        ON CONFLICT (id) DO NOTHING
        """
    )

    # ──────────────────────────────────────────────────────────
    # 3. Adicionar colunas NULLABLE com DEFAULT 1 (retrocompatível)
    # ──────────────────────────────────────────────────────────
    for table in DOMAIN_TABLES:
        op.add_column(
            table,
            sa.Column(
                "estabelecimento_id",
                sa.Integer(),
                nullable=True,
                server_default=sa.text("1"),
            ),
        )

    # usuarios: nullable permanente (ADMIN_GLOBAL não tem estabelecimento)
    op.add_column(
        "usuarios",
        sa.Column(
            "estabelecimento_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # ──────────────────────────────────────────────────────────
    # 4. Backfill — atribuir estabelecimento_id=1 nos registros existentes
    # ──────────────────────────────────────────────────────────
    for table in DOMAIN_TABLES:
        op.execute(f"UPDATE {table} SET estabelecimento_id = 1 WHERE estabelecimento_id IS NULL")  # noqa: S608

    # ──────────────────────────────────────────────────────────
    # 5. FK + índices nas tabelas de domínio
    # ──────────────────────────────────────────────────────────
    for table in DOMAIN_TABLES:
        op.alter_column(table, "estabelecimento_id", nullable=False, server_default=None)
        op.create_index(f"ix_{table}_estabelecimento_id", table, ["estabelecimento_id"])
        op.create_foreign_key(
            f"fk_{table}_estabelecimento_id",
            table,
            "estabelecimentos",
            ["estabelecimento_id"],
            ["id"],
        )

    op.create_index("ix_usuarios_estabelecimento_id", "usuarios", ["estabelecimento_id"])
    op.create_foreign_key(
        "fk_usuarios_estabelecimento_id",
        "usuarios",
        "estabelecimentos",
        ["estabelecimento_id"],
        ["id"],
    )

    # ──────────────────────────────────────────────────────────
    # 6. Migrar registros ADMIN → ADMIN_ESTABELECIMENTO
    #    (novos valores do enum já foram adicionados no passo 0)
    # ──────────────────────────────────────────────────────────
    op.execute(
        "UPDATE usuarios SET role = 'ADMIN_ESTABELECIMENTO' WHERE role = 'ADMIN'"
    )
    # Nota: o valor 'ADMIN' permanece no enum como legado sem uso.
    # Remover exigiria DROP+RECREATE do enum (risco desnecessário no MVP).

    # ──────────────────────────────────────────────────────────
    # 7. Ajuste medicos: adicionar comment na coluna
    # ──────────────────────────────────────────────────────────
    op.alter_column(
        "medicos",
        "duracao_consulta_min",
        existing_type=sa.INTEGER(),
        comment="Duração padrão global. Pode variar por unidade em MedicoEstabelecimento.",
        existing_nullable=False,
    )

    # especialidades: remover unique constraint global de nome
    # (mesmo nome pode existir em estabelecimentos diferentes)
    op.drop_constraint("especialidades_nome_key", "especialidades", type_="unique")


def downgrade() -> None:
    # Restaurar unique constraint de nome em especialidades
    op.create_unique_constraint("especialidades_nome_key", "especialidades", ["nome"])

    op.alter_column(
        "medicos",
        "duracao_consulta_min",
        existing_type=sa.INTEGER(),
        comment=None,
        existing_nullable=False,
    )

    # Remover FKs e colunas das tabelas de domínio
    for table in DOMAIN_TABLES:
        op.drop_constraint(f"fk_{table}_estabelecimento_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_estabelecimento_id", table_name=table)
        op.drop_column(table, "estabelecimento_id")

    op.drop_constraint("fk_usuarios_estabelecimento_id", "usuarios", type_="foreignkey")
    op.drop_index("ix_usuarios_estabelecimento_id", table_name="usuarios")
    op.drop_column("usuarios", "estabelecimento_id")

    # Remover tabelas junction e tenant (ordem inversa de criação)
    op.drop_index("ix_medico_estabelecimentos_medico_id", table_name="medico_estabelecimentos")
    op.drop_index(
        "ix_medico_estabelecimentos_estabelecimento_id",
        table_name="medico_estabelecimentos",
    )
    op.drop_table("medico_estabelecimentos")
    op.drop_index("ix_estabelecimentos_slug", table_name="estabelecimentos")
    op.drop_index("ix_estabelecimentos_rede_id", table_name="estabelecimentos")
    op.drop_table("estabelecimentos")
    op.drop_table("redes_estabelecimentos")

    sa.Enum(name="tipo_estabelecimento").drop(op.get_bind(), checkfirst=True)
