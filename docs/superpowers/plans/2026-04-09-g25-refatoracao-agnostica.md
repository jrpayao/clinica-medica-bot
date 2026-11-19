# G25 — Refatoração Agnóstica: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Renomear todas as entidades médicas hardcoded (`medico`, `consulta`, `paciente`) para termos agnósticos (`profissional`, `atendimento`, `cliente`), adicionar o enum `AtendimentoStatus` com os novos status do fluxo de recepção e criar a tabela `atendimento_status_historico`.

**Architecture:** Uma migration Alembic única renomeia tabelas, FKs e enums no banco. Em seguida, todos os arquivos Python e TypeScript são renomeados e atualizados em ordem: models → schemas → services → endpoints → workers → IA services → tests → frontend. Nenhuma lógica de negócio muda — é pura renomeação.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Angular 21 standalone signals, uv

---

## Mapa de Renomeações

### Banco / Tabelas


| De                        | Para                            |
| ------------------------- | ------------------------------- |
| `medicos`                 | `profissionais`                 |
| `consultas`               | `atendimentos`                  |
| `pacientes`               | `clientes`                      |
| `medico_estabelecimentos` | `profissional_estabelecimentos` |


### Enums PostgreSQL


| De                                                   | Para                   |
| ---------------------------------------------------- | ---------------------- |
| `consulta_status`                                    | `atendimento_status`   |
| `consulta_tipo`                                      | `atendimento_tipo`     |
| `consulta_urgencia`                                  | `atendimento_urgencia` |
| `consulta_canal`                                     | `atendimento_canal`    |
| `tipo_atendimento` (CONVENIO/PARTICULAR em paciente) | `modalidade_pagamento` |


### Colunas (FKs)


| Tabela                          | De            | Para              |
| ------------------------------- | ------------- | ----------------- |
| `atendimentos`                  | `medico_id`   | `profissional_id` |
| `atendimentos`                  | `paciente_id` | `cliente_id`      |
| `slots`                         | `medico_id`   | `profissional_id` |
| `profissional_estabelecimentos` | `medico_id`   | `profissional_id` |


### Campos de model


| Model                         | De                     | Para                      |
| ----------------------------- | ---------------------- | ------------------------- |
| `Profissional` (ex-Medico)    | `crm`                  | `registro_profissional`   |
| `Profissional`                | `duracao_consulta_min` | `duracao_atendimento_min` |
| `ProfissionalEstabelecimento` | `duracao_consulta_min` | `duracao_atendimento_min` |


### Arquivos Backend


| De                                     | Para                                         |
| -------------------------------------- | -------------------------------------------- |
| `app/models/medico.py`                 | `app/models/profissional.py`                 |
| `app/models/consulta.py`               | `app/models/atendimento.py`                  |
| `app/models/paciente.py`               | `app/models/cliente.py`                      |
| `app/models/medico_estabelecimento.py` | `app/models/profissional_estabelecimento.py` |
| `app/schemas/medico.py`                | `app/schemas/profissional.py`                |
| `app/schemas/consulta.py`              | `app/schemas/atendimento.py`                 |
| `app/schemas/paciente.py`              | `app/schemas/cliente.py`                     |
| `app/services/medico_service.py`       | `app/services/profissional_service.py`       |
| `app/services/paciente_service.py`     | `app/services/cliente_service.py`            |
| `app/api/v1/endpoints/medicos.py`      | `app/api/v1/endpoints/profissionais.py`      |
| `app/api/v1/endpoints/pacientes.py`    | `app/api/v1/endpoints/clientes.py`           |


### Novos arquivos Backend


| Arquivo                                | Propósito                                                      |
| -------------------------------------- | -------------------------------------------------------------- |
| `app/models/atendimento_historico.py`  | Model AtendimentoStatusHistorico                               |
| `app/api/v1/endpoints/atendimentos.py` | Endpoints /v1/atendimentos/* (ex-consultas do admin_dashboard) |


### Arquivos Frontend Admin — Renomear pastas/arquivos


| De                                      | Para                                          |
| --------------------------------------- | --------------------------------------------- |
| `features/medicos/`                     | `features/profissionais/`                     |
| `features/pacientes/`                   | `features/clientes/`                          |
| `features/consultas/`                   | `features/atendimentos/`                      |
| `core/services/agenda-admin.service.ts` | atualizar internamente (não renomear arquivo) |


---

## Novos status AtendimentoStatus

```python
class AtendimentoStatus(str, enum.Enum):
    AGENDADA             = "AGENDADA"
    CONFIRMADA           = "CONFIRMADA"
    CANCELADA            = "CANCELADA"
    PRESENTE             = "PRESENTE"
    AGUARDANDO_ANAMNESE  = "AGUARDANDO_ANAMNESE"
    ANAMNESE_PREENCHIDA  = "ANAMNESE_PREENCHIDA"
    FICHA_CONCLUIDA      = "FICHA_CONCLUIDA"
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    PAGO                 = "PAGO"
    AGUARDANDO_PROFISSIONAL = "AGUARDANDO_PROFISSIONAL"
    EM_ATENDIMENTO       = "EM_ATENDIMENTO"
    REALIZADA            = "REALIZADA"
    FALTA                = "FALTA"
```

---

## Task 1: Alembic Migration

**Files:**

- Create: `backend/alembic/versions/XXXX_g25_refatoracao_agnostica.py`
- **Step 1: Gerar migration vazia**

```bash
cd backend
uv run alembic revision --autogenerate -m "g25_refatoracao_agnostica"
```

- **Step 2: Substituir o conteúdo gerado pelo migration manual**

Abrir o arquivo gerado em `alembic/versions/` e substituir `upgrade()` e `downgrade()` pelo conteúdo abaixo. Substituir `XXXX` pelo hash real gerado:

```python
"""G25 — Refatoração Agnóstica: renomear tabelas, colunas, enums + novos status + historico

Revision ID: XXXX
Revises: b7d6df81f0c1
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'XXXX'
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

    # 8. Renomear FK medico_id → profissional_id em slots
    op.alter_column('slots', 'medico_id',
                    new_column_name='profissional_id')

    # 9. Renomear unique constraint em profissional_estabelecimentos
    op.execute('ALTER TABLE profissional_estabelecimentos RENAME CONSTRAINT uq_medico_estabelecimento TO uq_profissional_estabelecimento')

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
    op.drop_table('atendimento_status_historico')
    op.execute("ALTER TYPE atendimento_status RENAME TO consulta_status")
    op.execute("ALTER TYPE atendimento_tipo RENAME TO consulta_tipo")
    op.execute("ALTER TYPE atendimento_urgencia RENAME TO consulta_urgencia")
    op.execute("ALTER TYPE atendimento_canal RENAME TO consulta_canal")
    op.execute("ALTER TYPE modalidade_pagamento RENAME TO tipo_atendimento")
    op.alter_column('slots', 'profissional_id', new_column_name='medico_id')
    op.alter_column('atendimentos', 'cliente_id', new_column_name='paciente_id')
    op.alter_column('atendimentos', 'profissional_id', new_column_name='medico_id')
    op.alter_column('profissional_estabelecimentos', 'profissional_id', new_column_name='medico_id')
    op.alter_column('profissional_estabelecimentos', 'duracao_atendimento_min', new_column_name='duracao_consulta_min')
    op.alter_column('profissionais', 'duracao_atendimento_min', new_column_name='duracao_consulta_min')
    op.alter_column('profissionais', 'registro_profissional', new_column_name='crm')
    op.rename_table('profissional_estabelecimentos', 'medico_estabelecimentos')
    op.rename_table('clientes', 'pacientes')
    op.rename_table('atendimentos', 'consultas')
    op.rename_table('profissionais', 'medicos')
```

- **Step 3: Aplicar migration**

```bash
cd backend
uv run alembic upgrade head
```

Expected: `Running upgrade b7d6df81f0c1 -> XXXX, g25_refatoracao_agnostica`

- **Step 4: Verificar tabelas no banco**

```bash
cd backend
docker compose exec -T postgres psql -U medbot -d medbot -c "\dt" | grep -E "profissional|atendimento|cliente"
```

Expected: linhas com `profissionais`, `atendimentos`, `clientes`, `profissional_estabelecimentos`, `atendimento_status_historico`

- **Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(g25): migration — renomear tabelas, enums, colunas + atendimento_status_historico"
```

---

## Task 2: Backend Models

**Files:**

- Create: `backend/app/models/profissional.py`
- Create: `backend/app/models/atendimento.py`
- Create: `backend/app/models/cliente.py`
- Create: `backend/app/models/profissional_estabelecimento.py`
- Create: `backend/app/models/atendimento_historico.py`
- Delete: `backend/app/models/medico.py`
- Delete: `backend/app/models/consulta.py`
- Delete: `backend/app/models/paciente.py`
- Delete: `backend/app/models/medico_estabelecimento.py`
- Modify: `backend/app/models/__init__.py`
- **Step 1: Criar `app/models/profissional.py`**

```python
"""Model SQLAlchemy 2.0 — Profissional.

Profissional (médico, esteticista, dentista, etc.) pertence a uma especialidade
e pode atender em múltiplos estabelecimentos via ProfissionalEstabelecimento (N:N).

`duracao_atendimento_min` é o padrão global do profissional.
Pode ser sobrescrito por unidade em ProfissionalEstabelecimento.duracao_atendimento_min.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Profissional(Base):
    __tablename__ = "profissionais"

    id: Mapped[int] = mapped_column(primary_key=True)
    registro_profissional: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    especialidade_id: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id"), nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duracao_atendimento_min: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        comment="Duração padrão global. Pode variar por unidade em ProfissionalEstabelecimento.",
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    especialidade: Mapped["Especialidade"] = relationship(back_populates="profissionais")  # noqa: F821
    slots: Mapped[list["Slot"]] = relationship(back_populates="profissional")  # noqa: F821
    estabelecimento_vinculos: Mapped[list["ProfissionalEstabelecimento"]] = relationship(  # noqa: F821
        back_populates="profissional"
    )
```

- **Step 2: Criar `app/models/atendimento.py`**

```python
import enum

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AtendimentoTipo(str, enum.Enum):
    EXTERNO  = "EXTERNO"
    INTERNO  = "INTERNO"
    ENCAIXE  = "ENCAIXE"
    RETORNO  = "RETORNO"


class AtendimentoStatus(str, enum.Enum):
    AGENDADA              = "AGENDADA"
    CONFIRMADA            = "CONFIRMADA"
    CANCELADA             = "CANCELADA"
    PRESENTE              = "PRESENTE"
    AGUARDANDO_ANAMNESE   = "AGUARDANDO_ANAMNESE"
    ANAMNESE_PREENCHIDA   = "ANAMNESE_PREENCHIDA"
    FICHA_CONCLUIDA       = "FICHA_CONCLUIDA"
    AGUARDANDO_PAGAMENTO  = "AGUARDANDO_PAGAMENTO"
    PAGO                  = "PAGO"
    AGUARDANDO_PROFISSIONAL = "AGUARDANDO_PROFISSIONAL"
    EM_ATENDIMENTO        = "EM_ATENDIMENTO"
    REALIZADA             = "REALIZADA"
    FALTA                 = "FALTA"


class AtendimentoUrgencia(str, enum.Enum):
    BAIXA      = "BAIXA"
    MEDIA      = "MEDIA"
    ALTA       = "ALTA"
    EMERGENCIA = "EMERGENCIA"


class AtendimentoCanal(str, enum.Enum):
    PORTAL    = "PORTAL"
    WHATSAPP  = "WHATSAPP"
    INTERNO   = "INTERNO"


class Atendimento(Base, TimestampMixin):
    __tablename__ = "atendimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), nullable=False)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False)
    profissional_id: Mapped[int] = mapped_column(ForeignKey("profissionais.id"), nullable=False)
    especialidade_id: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id"), nullable=False
    )
    tipo: Mapped[AtendimentoTipo] = mapped_column(
        Enum(AtendimentoTipo, name="atendimento_tipo"),
        nullable=False,
    )
    status: Mapped[AtendimentoStatus] = mapped_column(
        Enum(AtendimentoStatus, name="atendimento_status"),
        default=AtendimentoStatus.AGENDADA,
        nullable=False,
    )
    triagem_resumo: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    urgencia: Mapped[AtendimentoUrgencia] = mapped_column(
        Enum(AtendimentoUrgencia, name="atendimento_urgencia"),
        default=AtendimentoUrgencia.BAIXA,
        nullable=False,
    )
    canal_origem: Mapped[AtendimentoCanal] = mapped_column(
        Enum(AtendimentoCanal, name="atendimento_canal"),
        nullable=False,
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )

    slot: Mapped["Slot"] = relationship()  # noqa: F821
    cliente: Mapped["Cliente"] = relationship()  # noqa: F821
    profissional: Mapped["Profissional"] = relationship()  # noqa: F821
    especialidade: Mapped["Especialidade"] = relationship()  # noqa: F821
    historico: Mapped[list["AtendimentoStatusHistorico"]] = relationship(  # noqa: F821
        back_populates="atendimento", order_by="AtendimentoStatusHistorico.created_at"
    )
```

- **Step 3: Criar `app/models/cliente.py`**

```python
import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ModalidadePagamento(str, enum.Enum):
    CONVENIO    = "CONVENIO"
    PARTICULAR  = "PARTICULAR"


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    cpf: Mapped[str] = mapped_column(String(11), index=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    convenio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    numero_carteirinha: Mapped[str | None] = mapped_column(String(50), nullable=True)
    modalidade_pagamento: Mapped[ModalidadePagamento | None] = mapped_column(
        Enum(ModalidadePagamento, name="modalidade_pagamento"), nullable=True
    )
    convenio_id: Mapped[int | None] = mapped_column(
        ForeignKey("convenios.id"), nullable=True, index=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
```

- **Step 4: Criar `app/models/profissional_estabelecimento.py`**

```python
"""Model SQLAlchemy 2.0 — ProfissionalEstabelecimento (junction N:N).

Resolve o relacionamento muitos-para-muitos entre Profissional e EstabelecimentoSaude.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProfissionalEstabelecimento(Base):
    __tablename__ = "profissional_estabelecimentos"
    __table_args__ = (
        UniqueConstraint(
            "profissional_id",
            "estabelecimento_id",
            name="uq_profissional_estabelecimento",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profissional_id: Mapped[int] = mapped_column(
        ForeignKey("profissionais.id"), nullable=False, index=True
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    duracao_atendimento_min: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30,
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    profissional: Mapped["Profissional"] = relationship(back_populates="estabelecimento_vinculos")  # noqa: F821
    estabelecimento: Mapped["EstabelecimentoSaude"] = relationship(  # noqa: F821
        back_populates="profissional_vinculos"
    )
```

- **Step 5: Criar `app/models/atendimento_historico.py`**

```python
"""Model SQLAlchemy 2.0 — AtendimentoStatusHistorico.

Registra cada transição de status de um atendimento.
O campo `atendimentos.status` é sempre o espelho do último registro desta tabela.
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.atendimento import AtendimentoStatus


class AtendimentoStatusHistorico(Base):
    __tablename__ = "atendimento_status_historico"

    id: Mapped[int] = mapped_column(primary_key=True)
    atendimento_id: Mapped[int] = mapped_column(
        ForeignKey("atendimentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status_anterior: Mapped[AtendimentoStatus | None] = mapped_column(
        Enum(AtendimentoStatus, name="atendimento_status", create_type=False),
        nullable=True,
    )
    status_novo: Mapped[AtendimentoStatus] = mapped_column(
        Enum(AtendimentoStatus, name="atendimento_status", create_type=False),
        nullable=False,
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    atendimento: Mapped["Atendimento"] = relationship(back_populates="historico")  # noqa: F821
```

- **Step 6: Atualizar `app/models/__init__.py`**

```python
from app.models.atendimento import (
    Atendimento,
    AtendimentoCanal,
    AtendimentoStatus,
    AtendimentoTipo,
    AtendimentoUrgencia,
)
from app.models.atendimento_historico import AtendimentoStatusHistorico
from app.models.auditoria import AuditoriaAcao, TipoAuditoria
from app.models.base import Base
from app.models.cliente import Cliente, ModalidadePagamento
from app.models.convenio import Convenio
from app.models.especialidade import Especialidade
from app.models.estabelecimento import EstabelecimentoSaude, TipoEstabelecimento
from app.models.fila_espera import FilaEspera
from app.models.licenca import Licenca, LicencaPlano, LicencaStatus
from app.models.profissional import Profissional
from app.models.profissional_estabelecimento import ProfissionalEstabelecimento
from app.models.rede_estabelecimento import RedeEstabelecimentos
from app.models.sessao_chat import SessaoChat
from app.models.sessao_historico import SessaoHistorico
from app.models.slot import Slot, SlotStatus
from app.models.token_usage import TokenUsage
from app.models.usuario import Usuario, UsuarioRole

__all__ = [
    "Atendimento", "AtendimentoCanal", "AtendimentoStatus",
    "AtendimentoTipo", "AtendimentoUrgencia",
    "AtendimentoStatusHistorico",
    "AuditoriaAcao", "TipoAuditoria",
    "Base",
    "Cliente", "ModalidadePagamento",
    "Convenio",
    "Especialidade",
    "EstabelecimentoSaude", "TipoEstabelecimento",
    "FilaEspera",
    "Licenca", "LicencaPlano", "LicencaStatus",
    "Profissional",
    "ProfissionalEstabelecimento",
    "RedeEstabelecimentos",
    "SessaoChat",
    "SessaoHistorico",
    "Slot", "SlotStatus",
    "TokenUsage",
    "Usuario", "UsuarioRole",
]
```

- **Step 7: Atualizar `app/models/slot.py`** — renomear `medico_id` → `profissional_id` e relationship

Localizar e substituir em `slot.py`:

```python
# DE:
medico_id: Mapped[int] = mapped_column(ForeignKey("medicos.id"), nullable=False)
# ...
medico: Mapped["Medico"] = relationship(back_populates="slots")

# PARA:
profissional_id: Mapped[int] = mapped_column(ForeignKey("profissionais.id"), nullable=False)
# ...
profissional: Mapped["Profissional"] = relationship(back_populates="slots")
```

- **Step 8: Atualizar `app/models/especialidade.py`** — renomear back_populates

```python
# DE:
medicos: Mapped[list["Medico"]] = relationship(back_populates="especialidade")
# PARA:
profissionais: Mapped[list["Profissional"]] = relationship(back_populates="especialidade")
```

- **Step 9: Atualizar `app/models/estabelecimento.py`** — renomear back_populates

```python
# DE:
medico_vinculos: Mapped[list["MedicoEstabelecimento"]] = relationship(...)
# PARA:
profissional_vinculos: Mapped[list["ProfissionalEstabelecimento"]] = relationship(...)
```

- **Step 10: Deletar arquivos antigos**

```bash
rm backend/app/models/medico.py
rm backend/app/models/consulta.py
rm backend/app/models/paciente.py
rm backend/app/models/medico_estabelecimento.py
```

- **Step 11: Rodar testes de models**

```bash
cd backend
uv run pytest tests/unit/test_usuario_roles.py tests/unit/test_estabelecimento.py -q
```

Expected: todos passam (esses testes não dependem dos models renomeados).

- **Step 12: Commit**

```bash
git add backend/app/models/
git commit -m "feat(g25): renomear models — profissional, atendimento, cliente, historico"
```

---

## Task 3: Backend Schemas

**Files:**

- Create: `backend/app/schemas/profissional.py`
- Create: `backend/app/schemas/atendimento.py`
- Create: `backend/app/schemas/cliente.py`
- Delete: `backend/app/schemas/medico.py`
- Delete: `backend/app/schemas/consulta.py`
- Delete: `backend/app/schemas/paciente.py`
- Modify: `backend/app/schemas/__init__.py`
- **Step 1: Criar `app/schemas/profissional.py`**

```python
from pydantic import BaseModel, Field


class ProfissionalBase(BaseModel):
    registro_profissional: str = Field(..., max_length=20)
    nome: str = Field(..., max_length=200)
    especialidade_id: int
    email: str | None = None
    telefone: str | None = None
    duracao_atendimento_min: int = 30
    ativo: bool = True


class ProfissionalCreate(ProfissionalBase):
    pass


class ProfissionalUpdate(BaseModel):
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    duracao_atendimento_min: int | None = None
    ativo: bool | None = None


class ProfissionalOut(ProfissionalBase):
    id: int
    model_config = {"from_attributes": True}


class ProfissionalResumo(BaseModel):
    id: int
    nome: str
    registro_profissional: str
    especialidade_id: int
    duracao_atendimento_min: int
    model_config = {"from_attributes": True}
```

- **Step 2: Criar `app/schemas/atendimento.py`**

```python
from datetime import datetime

from pydantic import BaseModel

from app.models.atendimento import AtendimentoCanal, AtendimentoStatus, AtendimentoTipo, AtendimentoUrgencia


class AtendimentoCreate(BaseModel):
    slot_id: int
    cliente_id: int
    profissional_id: int
    especialidade_id: int
    tipo: AtendimentoTipo = AtendimentoTipo.EXTERNO
    urgencia: AtendimentoUrgencia = AtendimentoUrgencia.BAIXA
    canal_origem: AtendimentoCanal = AtendimentoCanal.PORTAL
    observacoes: str | None = None
    estabelecimento_id: int


class AtendimentoOut(BaseModel):
    id: int
    slot_id: int
    cliente_id: int
    profissional_id: int
    especialidade_id: int
    tipo: AtendimentoTipo
    status: AtendimentoStatus
    urgencia: AtendimentoUrgencia
    canal_origem: AtendimentoCanal
    observacoes: str | None
    estabelecimento_id: int
    created_at: datetime
    model_config = {"from_attributes": True}


class AtendimentoResumo(BaseModel):
    id: int
    cliente_id: int
    profissional_id: int
    status: AtendimentoStatus
    urgencia: AtendimentoUrgencia
    model_config = {"from_attributes": True}


class AtendimentoFiltros(BaseModel):
    profissional_id: int | None = None
    status: AtendimentoStatus | None = None
    data: str | None = None


class TransicaoStatusRequest(BaseModel):
    status_novo: AtendimentoStatus
    observacao: str | None = None
```

- **Step 3: Criar `app/schemas/cliente.py`**

```python
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.cliente import ModalidadePagamento


class ClienteBase(BaseModel):
    cpf: str = Field(..., min_length=11, max_length=11)
    nome: str = Field(..., max_length=200)
    data_nascimento: date | None = None
    telefone: str | None = None
    email: str | None = None
    convenio: str | None = None
    numero_carteirinha: str | None = None
    modalidade_pagamento: ModalidadePagamento | None = None
    convenio_id: int | None = None


class ClienteCreate(ClienteBase):
    estabelecimento_id: int


class ClienteUpdate(BaseModel):
    nome: str | None = None
    telefone: str | None = None
    email: str | None = None
    convenio: str | None = None
    numero_carteirinha: str | None = None
    modalidade_pagamento: ModalidadePagamento | None = None
    convenio_id: int | None = None
    ativo: bool | None = None


class ClienteOut(ClienteBase):
    id: int
    ativo: bool
    created_at: datetime
    estabelecimento_id: int
    model_config = {"from_attributes": True}
```

- **Step 4: Deletar schemas antigos e atualizar `__init__.py`**

```bash
rm backend/app/schemas/medico.py backend/app/schemas/consulta.py backend/app/schemas/paciente.py
```

Em `app/schemas/__init__.py`, garantir que não importa mais os arquivos deletados (se houver imports).

- **Step 5: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat(g25): renomear schemas — profissional, atendimento, cliente"
```

---

## Task 4: Backend Services

**Files:**

- Create: `backend/app/services/profissional_service.py`
- Create: `backend/app/services/cliente_service.py`
- Modify: `backend/app/services/agenda_service.py`
- Modify: `backend/app/services/historico_service.py`
- Modify: `backend/app/services/ia/chat_service.py`
- Modify: `backend/app/services/ia/state_machine.py`
- Modify: `backend/app/services/ia/confirmacao.py`
- Modify: `backend/app/services/ia/sugestao.py`
- Modify: `backend/app/services/ia/triagem.py`
- Modify: `backend/app/services/notificacao_service.py`
- Modify: `backend/app/workers/lembretes.py`
- Delete: `backend/app/services/medico_service.py`
- Delete: `backend/app/services/paciente_service.py`
- **Step 1: Criar `app/services/profissional_service.py`** (copiar de `medico_service.py` e renomear)

```bash
cp backend/app/services/medico_service.py backend/app/services/profissional_service.py
```

Em `profissional_service.py`, substituir **todas** as ocorrências:

- `from app.models.medico import Medico` → `from app.models.profissional import Profissional`
- `Medico` → `Profissional`
- `medico` → `profissional` (variáveis e parâmetros)
- `medicos` → `profissionais` (listas)
- `"medicos"` → `"profissionais"` (strings de tabela se houver)
- `crm` → `registro_profissional`
- `duracao_consulta_min` → `duracao_atendimento_min`
- **Step 2: Criar `app/services/cliente_service.py`** (copiar de `paciente_service.py` e renomear)

```bash
cp backend/app/services/paciente_service.py backend/app/services/cliente_service.py
```

Em `cliente_service.py`, substituir **todas** as ocorrências:

- `from app.models.paciente import Paciente` → `from app.models.cliente import Cliente`
- `Paciente` → `Cliente`
- `paciente` → `cliente`
- `pacientes` → `clientes`
- `TipoAtendimento` → `ModalidadePagamento`
- `tipo_atendimento` → `modalidade_pagamento`
- **Step 3: Atualizar `app/services/agenda_service.py`**

Substituir em todo o arquivo:

- `from app.models.consulta import Consulta, ConsultaStatus` → `from app.models.atendimento import Atendimento, AtendimentoStatus`
- `from app.models.medico import Medico` → `from app.models.profissional import Profissional`
- `from app.models.paciente import Paciente` → `from app.models.cliente import Cliente`
- `from app.schemas.consulta import ConsultaCreate` → `from app.schemas.atendimento import AtendimentoCreate`
- `Consulta` → `Atendimento`, `ConsultaStatus` → `AtendimentoStatus`
- `Medico` → `Profissional`, `medico` → `profissional`, `medico_id` → `profissional_id`
- `Paciente` → `Cliente`, `paciente` → `cliente`, `paciente_id` → `cliente_id`
- `consulta` → `atendimento`, `consultas` → `atendimentos`
- **Step 4: Atualizar todos os services IA e workers**

Para cada arquivo abaixo, substituir as mesmas referências acima:

- `app/services/ia/chat_service.py`
- `app/services/ia/state_machine.py`
- `app/services/ia/confirmacao.py`
- `app/services/ia/sugestao.py`
- `app/services/ia/triagem.py`
- `app/services/historico_service.py`
- `app/services/notificacao_service.py`
- `app/workers/lembretes.py`
- `app/workers/billing_alert.py`
- `app/workers/slot_cleanup.py`

Padrão de substituição em cada arquivo:

```
medico/Medico       → profissional/Profissional
consulta/Consulta   → atendimento/Atendimento
paciente/Paciente   → cliente/Cliente
medico_id           → profissional_id
paciente_id         → cliente_id
ConsultaStatus      → AtendimentoStatus
crm                 → registro_profissional
duracao_consulta_min → duracao_atendimento_min
```

- **Step 5: Deletar services antigos**

```bash
rm backend/app/services/medico_service.py backend/app/services/paciente_service.py
```

- **Step 6: Rodar testes de services**

```bash
cd backend
uv run pytest tests/unit/test_agenda_service.py tests/unit/test_agenda_slots_dia.py -q
```

Anotar falhas para corrigir nas tasks de testes (Task 6).

- **Step 7: Commit**

```bash
git add backend/app/services/ backend/app/workers/
git commit -m "feat(g25): renomear services — profissional_service, cliente_service + atualizar agenda e IA"
```

---

## Task 5: Backend Endpoints e Router

**Files:**

- Create: `backend/app/api/v1/endpoints/profissionais.py`
- Create: `backend/app/api/v1/endpoints/clientes.py`
- Modify: `backend/app/api/v1/endpoints/agenda.py`
- Modify: `backend/app/api/v1/endpoints/admin_dashboard.py`
- Modify: `backend/app/api/v1/endpoints/chat.py`
- Modify: `backend/app/api/v1/router.py`
- Delete: `backend/app/api/v1/endpoints/medicos.py`
- Delete: `backend/app/api/v1/endpoints/pacientes.py`
- **Step 1: Criar `endpoints/profissionais.py`** (copiar de `medicos.py` e renomear)

```bash
cp backend/app/api/v1/endpoints/medicos.py backend/app/api/v1/endpoints/profissionais.py
```

Em `profissionais.py`:

- Substituir `prefix="/medicos"` → `prefix="/profissionais"`
- Substituir `tags=["Médicos"]` → `tags=["Profissionais"]`
- Substituir todas as referências: `Medico/medico/medicos` → `Profissional/profissional/profissionais`
- Substituir import: `from app.services.medico_service` → `from app.services.profissional_service`
- Substituir import schema: `from app.schemas.medico` → `from app.schemas.profissional`
- **Step 2: Criar `endpoints/clientes.py`** (copiar de `pacientes.py` e renomear)

```bash
cp backend/app/api/v1/endpoints/pacientes.py backend/app/api/v1/endpoints/clientes.py
```

Em `clientes.py`:

- Substituir `prefix="/pacientes"` → `prefix="/clientes"`
- Substituir `tags=["Pacientes"]` → `tags=["Clientes"]`
- Substituir todas as referências: `Paciente/paciente/pacientes` → `Cliente/cliente/clientes`
- Substituir import: `from app.services.paciente_service` → `from app.services.cliente_service`
- Substituir import schema: `from app.schemas.paciente` → `from app.schemas.cliente`
- **Step 3: Atualizar `endpoints/agenda.py`**

Substituir todas as referências de model/service no arquivo:

- `medico_id` → `profissional_id` (parâmetros de query e corpo)
- `paciente_id` → `cliente_id`
- `Consulta/ConsultaStatus` → `Atendimento/AtendimentoStatus`
- Imports correspondentes
- **Step 4: Atualizar `endpoints/admin_dashboard.py` e `chat.py`**

Mesmas substituições de import e referências de model.

- **Step 5: Atualizar `app/api/v1/router.py`**

```python
# DE:
from app.api.v1.endpoints import medicos, pacientes
# ...
api_router.include_router(medicos.router,   dependencies=_LICENCA_DEP)
api_router.include_router(pacientes.router, dependencies=_LICENCA_DEP)

# PARA:
from app.api.v1.endpoints import profissionais, clientes
# ...
api_router.include_router(profissionais.router, dependencies=_LICENCA_DEP)
api_router.include_router(clientes.router,      dependencies=_LICENCA_DEP)
```

- **Step 6: Deletar endpoints antigos**

```bash
rm backend/app/api/v1/endpoints/medicos.py backend/app/api/v1/endpoints/pacientes.py
```

- **Step 7: Testar que o app sobe**

```bash
cd backend
uv run fastapi dev app/main.py --port 8100 &
sleep 3
curl -s http://localhost:8100/docs -o /dev/null -w "%{http_code}"
kill %1
```

Expected: `200`

- **Step 8: Commit**

```bash
git add backend/app/api/
git commit -m "feat(g25): renomear endpoints — /profissionais, /clientes + atualizar router"
```

---

## Task 6: Atualizar Testes Backend

**Files:**

- Modify: todos os arquivos em `backend/tests/`
- **Step 1: Substituição global nos testes**

```bash
cd backend
# Substituir em todos os arquivos de teste
find tests/ -name "*.py" | xargs sed -i 's/from app\.models\.medico import/from app.models.profissional import/g'
find tests/ -name "*.py" | xargs sed -i 's/from app\.models\.consulta import/from app.models.atendimento import/g'
find tests/ -name "*.py" | xargs sed -i 's/from app\.models\.paciente import/from app.models.cliente import/g'
find tests/ -name "*.py" | xargs sed -i 's/from app\.models\.medico_estabelecimento import/from app.models.profissional_estabelecimento import/g'
find tests/ -name "*.py" | xargs sed -i 's/from app\.schemas\.medico import/from app.schemas.profissional import/g'
find tests/ -name "*.py" | xargs sed -i 's/from app\.schemas\.consulta import/from app.schemas.atendimento import/g'
find tests/ -name "*.py" | xargs sed -i 's/from app\.schemas\.paciente import/from app.schemas.cliente import/g'
find tests/ -name "*.py" | xargs sed -i 's/from app\.services\.medico_service import/from app.services.profissional_service import/g'
find tests/ -name "*.py" | xargs sed -i 's/from app\.services\.paciente_service import/from app.services.cliente_service import/g'
find tests/ -name "*.py" | xargs sed -i 's/ConsultaStatus/AtendimentoStatus/g'
find tests/ -name "*.py" | xargs sed -i 's/ConsultaTipo/AtendimentoTipo/g'
find tests/ -name "*.py" | xargs sed -i 's/\bConsulta\b/Atendimento/g'
find tests/ -name "*.py" | xargs sed -i 's/\bMedico\b/Profissional/g'
find tests/ -name "*.py" | xargs sed -i 's/\bPaciente\b/Cliente/g'
find tests/ -name "*.py" | xargs sed -i 's/medico_id/profissional_id/g'
find tests/ -name "*.py" | xargs sed -i 's/paciente_id/cliente_id/g'
find tests/ -name "*.py" | xargs sed -i 's/MedicoEstabelecimento/ProfissionalEstabelecimento/g'
find tests/ -name "*.py" | xargs sed -i 's/medico_estabelecimento/profissional_estabelecimento/g'
find tests/ -name "*.py" | xargs sed -i 's/\bcrm\b/registro_profissional/g'
find tests/ -name "*.py" | xargs sed -i 's/duracao_consulta_min/duracao_atendimento_min/g'
find tests/ -name "*.py" | xargs sed -i 's|/v1/medicos|/v1/profissionais|g'
find tests/ -name "*.py" | xargs sed -i 's|/v1/pacientes|/v1/clientes|g'
find tests/ -name "*.py" | xargs sed -i 's|/v1/consultas|/v1/atendimentos|g'
```

- **Step 2: Renomear arquivos de teste**

```bash
cd backend
mv tests/unit/test_medico_service.py tests/unit/test_profissional_service.py 2>/dev/null || true
mv tests/unit/test_paciente_service.py tests/unit/test_cliente_service.py 2>/dev/null || true
mv tests/unit/test_paciente_convenio.py tests/unit/test_cliente_convenio.py 2>/dev/null || true
```

- **Step 3: Rodar suite completa**

```bash
cd backend
uv run pytest tests/ -q 2>&1 | tail -20
```

- **Step 4: Corrigir falhas restantes**

Para cada falha, localizar o arquivo e corrigir manualmente o que o sed não pegou (nomes compostos, strings de URL, etc.).

- **Step 5: Rodar novamente até 0 falhas**

```bash
cd backend
uv run pytest tests/ -q
```

Expected: `X passed, 0 failed`

- **Step 6: Commit**

```bash
git add backend/tests/
git commit -m "feat(g25): atualizar testes — substituição global de nomenclatura"
```

---

## Task 7: Frontend Admin

**Files:**

- Rename: `features/medicos/` → `features/profissionais/`
- Rename: `features/pacientes/` → `features/clientes/`
- Rename: `features/consultas/` → `features/atendimentos/`
- Modify: `core/services/agenda-admin.service.ts`
- Modify: `app.routes.ts`
- Modify: `shared/shell/shell.component.ts`
- **Step 1: Renomear pastas de features**

```bash
cd frontend-admin/src/app/features
mv medicos profissionais
mv pacientes clientes
mv consultas atendimentos
```

- **Step 2: Renomear arquivos internos**

```bash
cd frontend-admin/src/app/features/profissionais
mv medicos.component.ts profissionais.component.ts
mv medicos.component.html profissionais.component.html
mv medicos.component.scss profissionais.component.scss
mv medico-dialog.component.ts profissional-dialog.component.ts
mv medicos.service.ts profissionais.service.ts

cd ../clientes
mv pacientes.component.ts clientes.component.ts
mv pacientes.component.html clientes.component.html
mv pacientes.component.scss clientes.component.scss
mv paciente-edit-dialog.component.ts cliente-edit-dialog.component.ts

cd ../atendimentos
mv consultas.component.ts atendimentos.component.ts
mv consultas.component.html atendimentos.component.html
mv consultas.component.scss atendimentos.component.scss
```

- **Step 3: Substituição global no frontend-admin**

```bash
cd frontend-admin/src
find . -name "*.ts" -o -name "*.html" | xargs sed -i \
  -e 's|/v1/medicos|/v1/profissionais|g' \
  -e 's|/v1/pacientes|/v1/clientes|g' \
  -e 's|/v1/consultas|/v1/atendimentos|g' \
  -e 's/MedicosComponent/ProfissionaisComponent/g' \
  -e 's/PacientesComponent/ClientesComponent/g' \
  -e 's/ConsultasComponent/AtendimentosComponent/g' \
  -e 's/MedicosService/ProfissionaisService/g' \
  -e 's/medicos\.service/profissionais.service/g' \
  -e 's/medico-dialog/profissional-dialog/g' \
  -e 's/paciente-edit-dialog/cliente-edit-dialog/g' \
  -e "s|features/medicos/medicos|features/profissionais/profissionais|g" \
  -e "s|features/pacientes/pacientes|features/clientes/clientes|g" \
  -e "s|features/consultas/consultas|features/atendimentos/atendimentos|g" \
  -e 's/crm/registro_profissional/g' \
  -e 's/duracao_consulta_min/duracao_atendimento_min/g' \
  -e 's/medico_id/profissional_id/g' \
  -e 's/paciente_id/cliente_id/g'
```

- **Step 4: Atualizar `app.routes.ts`**

Substituir as rotas `/medicos`, `/pacientes`, `/consultas` para `/profissionais`, `/clientes`, `/atendimentos`, e os imports dos components.

- **Step 5: Atualizar NAV_ITEMS no `shell.component.ts`**

Substituir os paths e labels:

- `{ path: '/medicos', label: 'Médicos' }` → `{ path: '/profissionais', label: 'Profissionais' }`
- `{ path: '/pacientes', label: 'Pacientes' }` → `{ path: '/clientes', label: 'Clientes' }`
- `{ path: '/consultas', label: 'Consultas' }` → `{ path: '/atendimentos', label: 'Atendimentos' }`
- **Step 6: Build do frontend-admin**

```bash
cd frontend-admin
node_modules/.bin/ng build 2>&1 | tail -20
```

Expected: `Build at: ... - Hash: ... - Time: ...ms` sem erros.

- **Step 7: Corrigir erros de build**

Para cada erro TypeScript, corrigir o import ou referência indicada.

- **Step 8: Commit**

```bash
git add frontend-admin/src/
git commit -m "feat(g25): frontend-admin — renomear features profissionais, clientes, atendimentos"
```

---

## Task 8: Frontend Portal

**Files:**

- Modify: `frontend-portal/src/app/core/services/agendamento.service.ts`
- Modify: `frontend-portal/src/app/core/services/chat.service.ts`
- Modify: `frontend-portal/src/app/features/agendamentos/agendamentos.component.ts`
- **Step 1: Substituição global no frontend-portal**

```bash
cd frontend-portal/src
find . -name "*.ts" -o -name "*.html" | xargs sed -i \
  -e 's|/v1/medicos|/v1/profissionais|g' \
  -e 's|/v1/pacientes|/v1/clientes|g' \
  -e 's|/v1/consultas|/v1/atendimentos|g' \
  -e 's/medico_id/profissional_id/g' \
  -e 's/paciente_id/cliente_id/g'
```

- **Step 2: Build do frontend-portal**

```bash
cd frontend-portal
node_modules/.bin/ng build 2>&1 | tail -20
```

Expected: sem erros.

- **Step 3: Commit**

```bash
git add frontend-portal/src/
git commit -m "feat(g25): frontend-portal — atualizar URLs e referências para nomenclatura agnóstica"
```

---

## Task 9: Verificação Final

- **Step 1: Suite completa de testes backend**

```bash
cd backend
uv run pytest tests/ -q
```

Expected: `X passed, 0 failed`

- **Step 2: Build frontend-admin**

```bash
cd frontend-admin && node_modules/.bin/ng build 2>&1 | grep -E "ERROR|Warning|successfully"
```

Expected: `Build successfully`

- **Step 3: Build frontend-portal**

```bash
cd frontend-portal && node_modules/.bin/ng build 2>&1 | grep -E "ERROR|Warning|successfully"
```

Expected: `Build successfully`

- **Step 4: Smoke test com servidor rodando**

```bash
cd backend && uv run fastapi dev app/main.py --port 8100 &
sleep 3
curl -s http://localhost:8100/v1/profissionais -H "Authorization: Bearer INVALID" -o /dev/null -w "%{http_code}"
curl -s http://localhost:8100/v1/clientes -H "Authorization: Bearer INVALID" -o /dev/null -w "%{http_code}"
kill %1
```

Expected: `401 401` (endpoint existe, rejeita token inválido corretamente)

- **Step 5: Commit final + push**

```bash
git add -A
git commit -m "feat(g25): verificação final — testes passando, builds limpos"
git push origin feature/g25-refatoracao-agnostica
```

---

## Critérios de Aceite

- `uv run pytest tests/ -q` — 0 falhas
- `ng build` frontend-admin sem erros
- `ng build` frontend-portal sem erros
- `uv run alembic upgrade head` em banco limpo sem erros
- Endpoints `/v1/profissionais`, `/v1/clientes` respondem 401 sem token
- Tabela `atendimento_status_historico` existe no banco
- Enum `atendimento_status` contém `PRESENTE`, `AGUARDANDO_ANAMNESE`, `AGUARDANDO_PROFISSIONAL`

