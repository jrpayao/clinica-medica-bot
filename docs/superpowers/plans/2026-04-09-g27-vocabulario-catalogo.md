# G27 — Vocabulário Configurável + Catálogo de Serviços: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que cada estabelecimento configure seus próprios rótulos de interface (ex: "Médico" → "Esteticista") e cadastre um catálogo de serviços (`TipoAtendimento`) com vínculo N:N com profissionais.

**Architecture:** 4 colunas de vocabulário adicionadas a `estabelecimentos`. Nova tabela `tipo_atendimentos` (catálogo por estabelecimento) + `profissional_tipo_atendimentos` (N:N). Migration Alembic única. CRUD via endpoints com RBAC. Frontend admin: painel de vocabulário + tela de catálogo. Portal: sem alteração nesta entrega (filtro por tipo será integrado no G23).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Angular 21 standalone signals, uv

**Pré-requisito:** G25 + G26 mergeados (usa nomenclatura agnóstica: `Profissional`, `Atendimento`)

---

## Mapa de Arquivos

### Backend — Criar
| Arquivo | Responsabilidade |
|---|---|
| `app/models/tipo_atendimento.py` | Model TipoAtendimento + ProfissionalTipoAtendimento |
| `app/schemas/tipo_atendimento.py` | Schemas de TipoAtendimento |
| `app/schemas/vocabulario.py` | Schemas de vocabulário do estabelecimento |
| `app/services/tipo_atendimento_service.py` | CRUD catálogo + vínculos com profissional |
| `app/api/v1/endpoints/tipo_atendimentos.py` | Endpoints /tipo-atendimentos |
| `alembic/versions/XXXX_g27_vocabulario_catalogo.py` | Migration |
| `tests/unit/test_tipo_atendimento_service.py` | Testes unitários |

### Backend — Modificar
| Arquivo | Mudança |
|---|---|
| `app/models/estabelecimento.py` | +4 campos de vocabulário |
| `app/models/__init__.py` | +TipoAtendimento, ProfissionalTipoAtendimento |
| `app/api/v1/endpoints/estabelecimentos.py` | +PATCH /vocabulario |
| `app/api/v1/router.py` | +tipo_atendimentos router |

### Frontend Admin — Criar
| Arquivo | Responsabilidade |
|---|---|
| `features/vocabulario/vocabulario.component.ts` | Configurar labels do estabelecimento |
| `features/vocabulario/vocabulario.component.html` | UI do painel de vocabulário |
| `features/catalogo/catalogo.component.ts` | Listar/criar/desativar TipoAtendimento |
| `features/catalogo/catalogo.component.html` | UI do catálogo |
| `features/catalogo/catalogo.service.ts` | HTTP /tipo-atendimentos |

### Frontend Admin — Modificar
| Arquivo | Mudança |
|---|---|
| `app.routes.ts` | +rotas /vocabulario, /catalogo |
| `shared/shell/shell.component.ts` | +NAV_ITEMS: Vocabulário, Catálogo |

---

## Task 1: Migration Alembic

**Files:**
- Create: `backend/alembic/versions/XXXX_g27_vocabulario_catalogo.py`
- Modify: `backend/app/models/estabelecimento.py`

- [ ] **Step 1: Verificar head atual**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run alembic current
```

Anotar o hash atual (ex: `e58f016718ba`).

- [ ] **Step 2: Gerar migration vazia**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run alembic revision -m "g27_vocabulario_catalogo"
```

Anotar o filename e hash gerado.

- [ ] **Step 3: Preencher migration**

Abrir o arquivo gerado e substituir `upgrade()` e `downgrade()`:

```python
"""G27 — Vocabulário configurável + catálogo TipoAtendimento

Revision ID: <new_hash>
Revises: <current_head>
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa

revision = '<new_hash>'
down_revision = '<current_head>'
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
    op.drop_table('tipo_atendimentos')
    op.drop_column('estabelecimentos', 'label_especialidade')
    op.drop_column('estabelecimentos', 'label_cliente')
    op.drop_column('estabelecimentos', 'label_atendimento')
    op.drop_column('estabelecimentos', 'label_profissional')
```

- [ ] **Step 4: Aplicar migration**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run alembic upgrade head
```

Expected: `Running upgrade <hash> -> <new_hash>, g27_vocabulario_catalogo`

- [ ] **Step 5: Verificar**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
docker compose exec -T postgres psql -U medbot -d medbot -c "\d estabelecimentos" | grep label
docker compose exec -T postgres psql -U medbot -d medbot -c "\dt" | grep tipo_atendimento
```

Expected: 4 colunas label_* em estabelecimentos; tabelas `tipo_atendimentos` e `profissional_tipo_atendimentos`.

- [ ] **Step 6: Commit**

```bash
cd /home/payao/projetos/chatbot-ai-medical
git add backend/alembic/versions/
git commit -m "feat(g27): migration — vocabulário nos estabelecimentos + tipo_atendimentos + profissional_tipo_atendimentos"
```

---

## Task 2: Backend Models

**Files:**
- Create: `backend/app/models/tipo_atendimento.py`
- Modify: `backend/app/models/estabelecimento.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Criar `app/models/tipo_atendimento.py`**

```python
"""Models SQLAlchemy 2.0 — TipoAtendimento e ProfissionalTipoAtendimento.

TipoAtendimento: catálogo de serviços por estabelecimento.
  Ex: "Botox", "Limpeza de Pele", "Consulta de Retorno"

ProfissionalTipoAtendimento: junction N:N — quais serviços um profissional oferece.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# Tabela de associação N:N (sem model próprio — apenas chaves)
profissional_tipo_atendimentos = Table(
    "profissional_tipo_atendimentos",
    Base.metadata,
    Column("profissional_id", Integer, ForeignKey("profissionais.id", ondelete="CASCADE"), primary_key=True),
    Column("tipo_atendimento_id", Integer, ForeignKey("tipo_atendimentos.id", ondelete="CASCADE"), primary_key=True),
)


class TipoAtendimento(Base):
    __tablename__ = "tipo_atendimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    duracao_min: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    preco: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profissionais: Mapped[list["Profissional"]] = relationship(  # noqa: F821
        secondary=profissional_tipo_atendimentos,
        back_populates="tipos_atendimento",
    )
```

- [ ] **Step 2: Atualizar `app/models/estabelecimento.py`**

Ler o arquivo. Adicionar os 4 campos de vocabulário na classe `EstabelecimentoSaude` (após o campo `rede_id`):

```python
    # Vocabulário configurável por tipo de estabelecimento
    label_profissional: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Médico", server_default="Médico"
    )
    label_atendimento: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Consulta", server_default="Consulta"
    )
    label_cliente: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Paciente", server_default="Paciente"
    )
    label_especialidade: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Especialidade", server_default="Especialidade"
    )
```

- [ ] **Step 3: Adicionar relationship em `app/models/profissional.py`**

Ler o arquivo. Adicionar ao final da classe `Profissional`:

```python
    tipos_atendimento: Mapped[list["TipoAtendimento"]] = relationship(  # noqa: F821
        secondary="profissional_tipo_atendimentos",
        back_populates="profissionais",
    )
```

- [ ] **Step 4: Atualizar `app/models/__init__.py`**

Ler o arquivo. Adicionar:

```python
from app.models.tipo_atendimento import TipoAtendimento, profissional_tipo_atendimentos
```

E no `__all__`: `"TipoAtendimento"`.

- [ ] **Step 5: Verificar importação**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run python -c "from app.models import *; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
cd /home/payao/projetos/chatbot-ai-medical
git add backend/app/models/
git commit -m "feat(g27): models TipoAtendimento + vocabulário em EstabelecimentoSaude"
```

---

## Task 3: Schemas

**Files:**
- Create: `backend/app/schemas/tipo_atendimento.py`
- Create: `backend/app/schemas/vocabulario.py`

- [ ] **Step 1: Criar `app/schemas/tipo_atendimento.py`**

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TipoAtendimentoCreate(BaseModel):
    nome: str = Field(..., max_length=100)
    descricao: str | None = None
    duracao_min: int = 30
    preco: Decimal | None = None


class TipoAtendimentoUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    duracao_min: int | None = None
    preco: Decimal | None = None
    ativo: bool | None = None


class TipoAtendimentoOut(BaseModel):
    id: int
    estabelecimento_id: int
    nome: str
    descricao: str | None
    duracao_min: int
    preco: Decimal | None
    ativo: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class TipoAtendimentoResumo(BaseModel):
    id: int
    nome: str
    duracao_min: int
    ativo: bool
    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Criar `app/schemas/vocabulario.py`**

```python
from pydantic import BaseModel, Field


class VocabularioUpdate(BaseModel):
    label_profissional: str | None = Field(None, max_length=50)
    label_atendimento: str | None = Field(None, max_length=50)
    label_cliente: str | None = Field(None, max_length=50)
    label_especialidade: str | None = Field(None, max_length=50)


class VocabularioOut(BaseModel):
    label_profissional: str
    label_atendimento: str
    label_cliente: str
    label_especialidade: str
    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Verificar importação**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run python -c "
from app.schemas.tipo_atendimento import TipoAtendimentoCreate, TipoAtendimentoOut
from app.schemas.vocabulario import VocabularioUpdate, VocabularioOut
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
cd /home/payao/projetos/chatbot-ai-medical
git add backend/app/schemas/tipo_atendimento.py backend/app/schemas/vocabulario.py
git commit -m "feat(g27): schemas TipoAtendimento e Vocabulario"
```

---

## Task 4: Service (TDD)

**Files:**
- Create: `backend/app/services/tipo_atendimento_service.py`
- Create: `backend/tests/unit/test_tipo_atendimento_service.py`

- [ ] **Step 1: Escrever testes RED**

Criar `backend/tests/unit/test_tipo_atendimento_service.py`:

```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tipo_atendimento import TipoAtendimento
from app.services.tipo_atendimento_service import TipoAtendimentoService
from app.schemas.tipo_atendimento import TipoAtendimentoCreate, TipoAtendimentoUpdate


@pytest.fixture
def db():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def svc(db):
    return TipoAtendimentoService(db)


async def test_listar_ativos(svc, db):
    tipo = MagicMock(spec=TipoAtendimento)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [tipo]
    db.execute.return_value = result

    lista = await svc.listar_ativos(estabelecimento_id=1)

    assert len(lista) == 1
    assert lista[0] is tipo


async def test_criar_tipo(svc, db):
    dados = TipoAtendimentoCreate(
        nome="Botox",
        duracao_min=45,
        preco=Decimal("350.00"),
    )
    tipo = await svc.criar(dados, estabelecimento_id=1)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert tipo.nome == "Botox"
    assert tipo.estabelecimento_id == 1
    assert tipo.duracao_min == 45


async def test_atualizar_tipo(svc, db):
    tipo_existente = MagicMock(spec=TipoAtendimento)
    db.get.return_value = tipo_existente

    dados = TipoAtendimentoUpdate(ativo=False)
    resultado = await svc.atualizar(tipo_id=1, dados=dados)

    db.commit.assert_called_once()
    assert resultado is tipo_existente


async def test_atualizar_tipo_nao_encontrado(svc, db):
    db.get.return_value = None

    dados = TipoAtendimentoUpdate(nome="Novo Nome")
    resultado = await svc.atualizar(tipo_id=999, dados=dados)

    assert resultado is None


async def test_vincular_profissional(svc, db):
    profissional = MagicMock()
    profissional.tipos_atendimento = []
    tipo = MagicMock(spec=TipoAtendimento)
    db.get.side_effect = [profissional, tipo]

    result = await svc.vincular_profissional(profissional_id=1, tipo_id=2)

    assert result is True
    assert tipo in profissional.tipos_atendimento
    db.commit.assert_called_once()
```

- [ ] **Step 2: Rodar — verificar FAIL**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run pytest tests/unit/test_tipo_atendimento_service.py -v 2>&1 | tail -10
```

Expected: `ImportError` ou `ModuleNotFoundError` (service não existe ainda).

- [ ] **Step 3: Criar `app/services/tipo_atendimento_service.py`**

```python
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.estabelecimento import EstabelecimentoSaude
from app.models.profissional import Profissional
from app.models.tipo_atendimento import TipoAtendimento
from app.schemas.tipo_atendimento import TipoAtendimentoCreate, TipoAtendimentoUpdate
from app.schemas.vocabulario import VocabularioUpdate

log = structlog.get_logger(__name__)


class TipoAtendimentoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Catálogo de serviços ─────────────────────────────────────

    async def listar_ativos(self, estabelecimento_id: int) -> list[TipoAtendimento]:
        result = await self.db.execute(
            select(TipoAtendimento)
            .where(
                TipoAtendimento.estabelecimento_id == estabelecimento_id,
                TipoAtendimento.ativo == True,  # noqa: E712
            )
            .order_by(TipoAtendimento.nome)
        )
        return result.scalars().all()

    async def listar_todos(self, estabelecimento_id: int) -> list[TipoAtendimento]:
        result = await self.db.execute(
            select(TipoAtendimento)
            .where(TipoAtendimento.estabelecimento_id == estabelecimento_id)
            .order_by(TipoAtendimento.nome)
        )
        return result.scalars().all()

    async def criar(self, dados: TipoAtendimentoCreate, estabelecimento_id: int) -> TipoAtendimento:
        tipo = TipoAtendimento(**dados.model_dump(), estabelecimento_id=estabelecimento_id)
        self.db.add(tipo)
        await self.db.commit()
        await self.db.refresh(tipo)
        log.info("tipo_atendimento_criado", nome=tipo.nome, estabelecimento_id=estabelecimento_id)
        return tipo

    async def atualizar(self, tipo_id: int, dados: TipoAtendimentoUpdate) -> TipoAtendimento | None:
        tipo = await self.db.get(TipoAtendimento, tipo_id)
        if not tipo:
            return None
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(tipo, campo, valor)
        await self.db.commit()
        await self.db.refresh(tipo)
        return tipo

    # ── Vínculo profissional ↔ tipo ──────────────────────────────

    async def vincular_profissional(self, profissional_id: int, tipo_id: int) -> bool:
        profissional = await self.db.get(Profissional, profissional_id)
        tipo = await self.db.get(TipoAtendimento, tipo_id)
        if not profissional or not tipo:
            return False
        if tipo not in profissional.tipos_atendimento:
            profissional.tipos_atendimento.append(tipo)
            await self.db.commit()
        return True

    async def desvincular_profissional(self, profissional_id: int, tipo_id: int) -> bool:
        profissional = await self.db.get(Profissional, profissional_id)
        tipo = await self.db.get(TipoAtendimento, tipo_id)
        if not profissional or not tipo:
            return False
        if tipo in profissional.tipos_atendimento:
            profissional.tipos_atendimento.remove(tipo)
            await self.db.commit()
        return True

    async def listar_tipos_do_profissional(self, profissional_id: int) -> list[TipoAtendimento]:
        profissional = await self.db.get(Profissional, profissional_id)
        if not profissional:
            return []
        return profissional.tipos_atendimento

    # ── Vocabulário do estabelecimento ───────────────────────────

    async def atualizar_vocabulario(
        self, estabelecimento_id: int, dados: VocabularioUpdate
    ) -> EstabelecimentoSaude | None:
        est = await self.db.get(EstabelecimentoSaude, estabelecimento_id)
        if not est:
            return None
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(est, campo, valor)
        await self.db.commit()
        await self.db.refresh(est)
        return est
```

- [ ] **Step 4: Rodar — verificar PASS**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run pytest tests/unit/test_tipo_atendimento_service.py -v 2>&1 | tail -10
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
cd /home/payao/projetos/chatbot-ai-medical
git add backend/app/services/tipo_atendimento_service.py backend/tests/unit/test_tipo_atendimento_service.py
git commit -m "feat(g27): TipoAtendimentoService — CRUD catálogo, vínculos profissional, vocabulário (TDD)"
```

---

## Task 5: Endpoints

**Files:**
- Create: `backend/app/api/v1/endpoints/tipo_atendimentos.py`
- Modify: `backend/app/api/v1/endpoints/estabelecimentos.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: Criar `app/api/v1/endpoints/tipo_atendimentos.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core.database import get_db
from app.schemas.tipo_atendimento import TipoAtendimentoCreate, TipoAtendimentoOut, TipoAtendimentoUpdate
from app.services.tipo_atendimento_service import TipoAtendimentoService

router = APIRouter(prefix="/tipo-atendimentos", tags=["Catálogo de Serviços"])

_ADMIN = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")


@router.get("", response_model=list[TipoAtendimentoOut])
async def listar_tipos(
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    return await TipoAtendimentoService(db).listar_todos(estabelecimento_id)


@router.post("", response_model=TipoAtendimentoOut, status_code=status.HTTP_201_CREATED)
async def criar_tipo(
    dados: TipoAtendimentoCreate,
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role(*_ADMIN))],
):
    return await TipoAtendimentoService(db).criar(dados, estabelecimento_id)


@router.patch("/{tipo_id}", response_model=TipoAtendimentoOut)
async def atualizar_tipo(
    tipo_id: int,
    dados: TipoAtendimentoUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role(*_ADMIN))],
):
    tipo = await TipoAtendimentoService(db).atualizar(tipo_id, dados)
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de atendimento não encontrado")
    return tipo


@router.get("/{tipo_id}/profissionais", response_model=list[int])
async def listar_profissionais_do_tipo(
    tipo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    """Retorna IDs dos profissionais vinculados a este tipo de atendimento."""
    from sqlalchemy import select
    from app.models.tipo_atendimento import profissional_tipo_atendimentos
    result = await db.execute(
        select(profissional_tipo_atendimentos.c.profissional_id)
        .where(profissional_tipo_atendimentos.c.tipo_atendimento_id == tipo_id)
    )
    return [row[0] for row in result.fetchall()]
```

- [ ] **Step 2: Criar endpoints N:N em `router.py` (vínculos profissional ↔ tipo)**

Ler `backend/app/api/v1/router.py`. Após os includes existentes, adicionar inline router:

```python
# Tipos de atendimento por profissional — /v1/profissionais/{id}/tipo-atendimentos
from app.services.tipo_atendimento_service import TipoAtendimentoService as _TASvc
from app.schemas.tipo_atendimento import TipoAtendimentoOut as _TAOut

_prof_ta_router = APIRouter(prefix="/profissionais/{profissional_id}/tipo-atendimentos",
                             tags=["Vínculos Profissional↔Catálogo"])


@_prof_ta_router.get("", response_model=list[_TAOut])
async def listar_tipos_profissional(
    profissional_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    return await _TASvc(db).listar_tipos_do_profissional(profissional_id)


@_prof_ta_router.post("/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def vincular_tipo_profissional(
    profissional_id: int,
    tipo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO"))],
):
    ok = await _TASvc(db).vincular_profissional(profissional_id, tipo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profissional ou tipo não encontrado")


@_prof_ta_router.delete("/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desvincular_tipo_profissional(
    profissional_id: int,
    tipo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO"))],
):
    ok = await _TASvc(db).desvincular_profissional(profissional_id, tipo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profissional ou tipo não encontrado")


api_router.include_router(_prof_ta_router, dependencies=_LICENCA_DEP)
```

E incluir o router principal:

```python
from app.api.v1.endpoints import tipo_atendimentos
# ...
api_router.include_router(tipo_atendimentos.router, dependencies=_LICENCA_DEP)
```

- [ ] **Step 3: Adicionar endpoint de vocabulário em `estabelecimentos.py`**

Ler o arquivo. Adicionar ao final:

```python
from app.schemas.vocabulario import VocabularioOut, VocabularioUpdate
from app.services.tipo_atendimento_service import TipoAtendimentoService


@router.patch("/meu/vocabulario", response_model=VocabularioOut)
async def atualizar_vocabulario(
    dados: VocabularioUpdate,
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO"))],
):
    est = await TipoAtendimentoService(db).atualizar_vocabulario(estabelecimento_id, dados)
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado")
    return est


@router.get("/meu/vocabulario", response_model=VocabularioOut)
async def obter_vocabulario(
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_user)],
):
    from app.models.estabelecimento import EstabelecimentoSaude
    est = await db.get(EstabelecimentoSaude, estabelecimento_id)
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado")
    return est
```

**IMPORTANTE**: Verificar quais imports já existem em `estabelecimentos.py` antes de adicionar — não duplicar `require_role`, `get_db`, etc.

- [ ] **Step 4: Verificar app sobe**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run python -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Rodar suite completa**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run pytest tests/ -q 2>&1 | tail -5
```

Expected: 0 falhas.

- [ ] **Step 6: Commit**

```bash
cd /home/payao/projetos/chatbot-ai-medical
git add backend/app/api/ backend/app/services/
git commit -m "feat(g27): endpoints /tipo-atendimentos, /profissionais/{id}/tipo-atendimentos, /estabelecimentos/meu/vocabulario"
```

---

## Task 6: Frontend Admin — Vocabulário e Catálogo

**Files:**
- Create: `frontend-admin/src/app/features/vocabulario/vocabulario.component.ts`
- Create: `frontend-admin/src/app/features/vocabulario/vocabulario.component.html`
- Create: `frontend-admin/src/app/features/catalogo/catalogo.component.ts`
- Create: `frontend-admin/src/app/features/catalogo/catalogo.component.html`
- Create: `frontend-admin/src/app/features/catalogo/catalogo.service.ts`
- Modify: `frontend-admin/src/app/app.routes.ts`
- Modify: `frontend-admin/src/app/shared/shell/shell.component.ts`

- [ ] **Step 1: Criar `features/catalogo/catalogo.service.ts`**

```typescript
import { Injectable, inject } from '@angular/core';
import { ApiService } from '../../core/services/api.service';

export interface TipoAtendimento {
  id: number;
  nome: string;
  descricao: string | null;
  duracao_min: number;
  preco: number | null;
  ativo: boolean;
}

@Injectable({ providedIn: 'root' })
export class CatalogoService {
  private api = inject(ApiService);

  listar() {
    return this.api.get<TipoAtendimento[]>('/tipo-atendimentos');
  }

  criar(dados: Partial<TipoAtendimento>) {
    return this.api.post<TipoAtendimento>('/tipo-atendimentos', dados);
  }

  atualizar(id: number, dados: Partial<TipoAtendimento>) {
    return this.api.patch<TipoAtendimento>(`/tipo-atendimentos/${id}`, dados);
  }
}
```

- [ ] **Step 2: Criar `features/catalogo/catalogo.component.ts`**

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormControl, FormGroup, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { firstValueFrom } from 'rxjs';

import { CatalogoService, TipoAtendimento } from './catalogo.service';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ToastService } from '../../core/services/toast.service';

@Component({
  selector: 'app-catalogo',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatIconModule, MatTableModule,
    MatFormFieldModule, MatInputModule, MatProgressSpinnerModule,
    PageHeaderComponent, EmptyStateComponent,
  ],
  templateUrl: './catalogo.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogoComponent implements OnInit {
  private svc   = inject(CatalogoService);
  private toast = inject(ToastService);

  readonly tipos   = signal<TipoAtendimento[]>([]);
  readonly loading = signal(false);
  readonly colunas = ['nome', 'duracao_min', 'preco', 'ativo', 'acoes'];

  readonly form = new FormGroup({
    nome:        new FormControl('', [Validators.required]),
    descricao:   new FormControl(''),
    duracao_min: new FormControl(30, [Validators.required, Validators.min(5)]),
    preco:       new FormControl<number | null>(null),
  });

  ngOnInit(): void {
    this.carregar();
  }

  async carregar(): Promise<void> {
    this.loading.set(true);
    try {
      const lista = await firstValueFrom(this.svc.listar());
      this.tipos.set(lista ?? []);
    } finally {
      this.loading.set(false);
    }
  }

  async salvar(): Promise<void> {
    if (this.form.invalid) return;
    try {
      await firstValueFrom(this.svc.criar(this.form.value as Partial<TipoAtendimento>));
      this.toast.sucesso('Serviço criado');
      this.form.reset({ duracao_min: 30 });
      await this.carregar();
    } catch {
      this.toast.erro('Erro ao criar serviço');
    }
  }

  async toggle(tipo: TipoAtendimento): Promise<void> {
    try {
      await firstValueFrom(this.svc.atualizar(tipo.id, { ativo: !tipo.ativo }));
      await this.carregar();
    } catch {
      this.toast.erro('Erro ao atualizar');
    }
  }
}
```

- [ ] **Step 3: Criar `features/catalogo/catalogo.component.html`**

```html
<app-page-header titulo="Catálogo de Serviços" subtitulo="Tipos de atendimento oferecidos pela clínica" />

@if (loading()) {
  <mat-spinner diameter="40" />
} @else {
  <mat-card class="mb-4">
    <mat-card-header><mat-card-title>Novo Serviço</mat-card-title></mat-card-header>
    <mat-card-content>
      <form [formGroup]="form" (ngSubmit)="salvar()" class="grid grid-cols-2 gap-3 mt-3">
        <mat-form-field class="col-span-2">
          <mat-label>Nome *</mat-label>
          <input matInput formControlName="nome" placeholder="Ex: Botox, Limpeza de Pele" />
        </mat-form-field>
        <mat-form-field class="col-span-2">
          <mat-label>Descrição</mat-label>
          <textarea matInput formControlName="descricao" rows="2"></textarea>
        </mat-form-field>
        <mat-form-field>
          <mat-label>Duração (min) *</mat-label>
          <input matInput type="number" formControlName="duracao_min" />
        </mat-form-field>
        <mat-form-field>
          <mat-label>Preço (R$)</mat-label>
          <input matInput type="number" step="0.01" formControlName="preco" />
        </mat-form-field>
        <div class="col-span-2">
          <button mat-raised-button color="primary" type="submit" [disabled]="form.invalid">
            Adicionar Serviço
          </button>
        </div>
      </form>
    </mat-card-content>
  </mat-card>

  @if (tipos().length === 0) {
    <app-empty-state title="Nenhum serviço cadastrado" />
  } @else {
    <mat-card>
      <mat-card-content>
        <table mat-table [dataSource]="tipos()" class="w-full">
          <ng-container matColumnDef="nome">
            <th mat-header-cell *matHeaderCellDef>Nome</th>
            <td mat-cell *matCellDef="let t">{{ t.nome }}</td>
          </ng-container>
          <ng-container matColumnDef="duracao_min">
            <th mat-header-cell *matHeaderCellDef>Duração</th>
            <td mat-cell *matCellDef="let t">{{ t.duracao_min }} min</td>
          </ng-container>
          <ng-container matColumnDef="preco">
            <th mat-header-cell *matHeaderCellDef>Preço</th>
            <td mat-cell *matCellDef="let t">{{ t.preco ? ('R$ ' + t.preco) : '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="ativo">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let t">{{ t.ativo ? 'Ativo' : 'Inativo' }}</td>
          </ng-container>
          <ng-container matColumnDef="acoes">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let t">
              <button mat-icon-button (click)="toggle(t)" [title]="t.ativo ? 'Desativar' : 'Reativar'">
                <mat-icon>{{ t.ativo ? 'block' : 'check_circle' }}</mat-icon>
              </button>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="colunas"></tr>
          <tr mat-row *matRowDef="let row; columns: colunas;"></tr>
        </table>
      </mat-card-content>
    </mat-card>
  }
}
```

- [ ] **Step 4: Criar `features/vocabulario/vocabulario.component.ts`**

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormControl, FormGroup } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/services/api.service';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';

interface Vocabulario {
  label_profissional: string;
  label_atendimento: string;
  label_cliente: string;
  label_especialidade: string;
}

@Component({
  selector: 'app-vocabulario',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatProgressSpinnerModule,
    PageHeaderComponent,
  ],
  templateUrl: './vocabulario.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VocabularioComponent implements OnInit {
  private api   = inject(ApiService);
  private toast = inject(ToastService);

  readonly loading = signal(false);
  readonly salvando = signal(false);

  readonly form = new FormGroup({
    label_profissional:  new FormControl(''),
    label_atendimento:   new FormControl(''),
    label_cliente:       new FormControl(''),
    label_especialidade: new FormControl(''),
  });

  ngOnInit(): void {
    this.carregar();
  }

  async carregar(): Promise<void> {
    this.loading.set(true);
    try {
      const vocab = await firstValueFrom(this.api.get<Vocabulario>('/estabelecimentos/meu/vocabulario'));
      this.form.patchValue(vocab);
    } finally {
      this.loading.set(false);
    }
  }

  async salvar(): Promise<void> {
    this.salvando.set(true);
    try {
      await firstValueFrom(this.api.patch('/estabelecimentos/meu/vocabulario', this.form.value));
      this.toast.sucesso('Vocabulário atualizado');
    } catch {
      this.toast.erro('Erro ao salvar');
    } finally {
      this.salvando.set(false);
    }
  }
}
```

- [ ] **Step 5: Criar `features/vocabulario/vocabulario.component.html`**

```html
<app-page-header titulo="Vocabulário" subtitulo="Personalize os termos exibidos na interface" />

@if (loading()) {
  <mat-spinner diameter="40" />
} @else {
  <mat-card class="max-w-xl">
    <mat-card-header>
      <mat-card-title>Rótulos da interface</mat-card-title>
      <mat-card-subtitle>
        Ex: "Médico" → "Esteticista" para uma clínica de estética
      </mat-card-subtitle>
    </mat-card-header>
    <mat-card-content>
      <form [formGroup]="form" (ngSubmit)="salvar()" class="grid gap-4 mt-4">
        <mat-form-field>
          <mat-label>Profissional</mat-label>
          <input matInput formControlName="label_profissional" placeholder="Médico" />
          <mat-hint>Ex: Esteticista, Dentista, Biomédico</mat-hint>
        </mat-form-field>
        <mat-form-field>
          <mat-label>Atendimento</mat-label>
          <input matInput formControlName="label_atendimento" placeholder="Consulta" />
          <mat-hint>Ex: Sessão, Procedimento, Consulta</mat-hint>
        </mat-form-field>
        <mat-form-field>
          <mat-label>Cliente</mat-label>
          <input matInput formControlName="label_cliente" placeholder="Paciente" />
          <mat-hint>Ex: Cliente, Aluno, Paciente</mat-hint>
        </mat-form-field>
        <mat-form-field>
          <mat-label>Especialidade</mat-label>
          <input matInput formControlName="label_especialidade" placeholder="Especialidade" />
          <mat-hint>Ex: Área, Serviço, Especialidade</mat-hint>
        </mat-form-field>
        <div>
          <button mat-raised-button color="primary" type="submit" [disabled]="salvando()">
            {{ salvando() ? 'Salvando...' : 'Salvar vocabulário' }}
          </button>
        </div>
      </form>
    </mat-card-content>
  </mat-card>
}
```

- [ ] **Step 6: Adicionar rotas em `app.routes.ts`**

Ler o arquivo. Adicionar antes do fechamento `]`:

```typescript
{
  path: 'catalogo',
  loadComponent: () =>
    import('./features/catalogo/catalogo.component').then(m => m.CatalogoComponent),
  canActivate: [authGuard],
},
{
  path: 'vocabulario',
  loadComponent: () =>
    import('./features/vocabulario/vocabulario.component').then(m => m.VocabularioComponent),
  canActivate: [authGuard],
},
```

- [ ] **Step 7: Adicionar NAV_ITEMS no `shell.component.ts`**

Ler o arquivo. No array `NAV_ITEMS`, após `/convenios`, adicionar:

```typescript
{ path: '/catalogo', label: 'Catálogo', icon: 'medical_services', modos: ['escopado', 'estabelecimento'] },
{ path: '/vocabulario', label: 'Vocabulário', icon: 'translate', modos: ['escopado', 'estabelecimento'] },
```

**IMPORTANTE**: Adaptar o shape exato ao padrão existente (verificar se tem campo `modos` ou usa outro filtro).

- [ ] **Step 8: Build**

```bash
cd /home/payao/projetos/chatbot-ai-medical/frontend-admin
node_modules/.bin/ng build 2>&1 | grep -E "^ERROR|Application bundle"
```

Expected: sem ERRORs. Corrigir se necessário.

- [ ] **Step 9: Commit**

```bash
cd /home/payao/projetos/chatbot-ai-medical
git add frontend-admin/src/
git commit -m "feat(g27): frontend-admin — catálogo de serviços e painel de vocabulário"
```

---

## Task 7: Verificação Final

- [ ] **Step 1: Suite de testes backend**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
uv run pytest tests/ -q 2>&1 | tail -5
```

Expected: 0 falhas.

- [ ] **Step 2: Builds**

```bash
cd /home/payao/projetos/chatbot-ai-medical/frontend-admin
node_modules/.bin/ng build 2>&1 | grep -E "^ERROR|Application bundle"
cd /home/payao/projetos/chatbot-ai-medical/frontend-portal
node_modules/.bin/ng build 2>&1 | grep -E "^ERROR|Application bundle"
```

Expected: ambos sem ERRORs.

- [ ] **Step 3: Smoke test endpoints**

```bash
curl -s http://localhost:8100/v1/tipo-atendimentos -o /dev/null -w "/v1/tipo-atendimentos: %{http_code}\n"
curl -s http://localhost:8100/v1/estabelecimentos/meu/vocabulario -o /dev/null -w "/v1/estabelecimentos/meu/vocabulario: %{http_code}\n"
curl -s "http://localhost:8100/v1/profissionais/1/tipo-atendimentos" -o /dev/null -w "/v1/profissionais/1/tipo-atendimentos: %{http_code}\n"
```

Expected: todos `401` (endpoint existe, protegido por JWT).

- [ ] **Step 4: Verificar DB**

```bash
cd /home/payao/projetos/chatbot-ai-medical/backend
docker compose exec -T postgres psql -U medbot -d medbot -c "\d estabelecimentos" | grep label
docker compose exec -T postgres psql -U medbot -d medbot -c "\dt" | grep tipo_atendimento
```

- [ ] **Step 5: Commit final + push**

```bash
cd /home/payao/projetos/chatbot-ai-medical
git add -A
git diff --staged --quiet || git commit -m "feat(g27): verificação final — testes passando, builds limpos"
git push origin feature/g27-vocabulario
```

---

## Critérios de Aceite

- [ ] Colunas `label_profissional/atendimento/cliente/especialidade` em `estabelecimentos`
- [ ] Tabelas `tipo_atendimentos` e `profissional_tipo_atendimentos` no banco
- [ ] `GET /v1/tipo-atendimentos` responde 401 sem token
- [ ] `GET /v1/estabelecimentos/meu/vocabulario` responde 401 sem token
- [ ] `GET /v1/profissionais/1/tipo-atendimentos` responde 401 sem token
- [ ] `uv run pytest tests/ -q` — 0 falhas (inclui 5 testes TipoAtendimentoService)
- [ ] `ng build` frontend-admin sem erros
- [ ] Telas `/catalogo` e `/vocabulario` acessíveis no admin
