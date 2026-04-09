# ADMIN_GLOBAL Platform Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar dashboard e menus específicos para ADMIN_GLOBAL (plataforma), corrigir exposição de PII, adicionar auditoria de ações administrativas e gestão de usuários internos para ADMIN_ESTABELECIMENTO.

**Architecture:** Backend-first — cada task de backend inclui testes unitários antes da implementação (TDAD). Frontend consome os novos endpoints. ADMIN_GLOBAL em modo global nunca troca JWT; usa header `X-Estabelecimento-ID` + evento de auditoria ao acessar clínica. Endpoints de plataforma ficam em `admin_plataforma.py`; CRUD de usuários em `admin_usuarios.py`.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic + structlog + pytest (asyncio_mode=auto) | Angular 21 + Signals + Angular Material + OnPush

**Spec:** `docs/superpowers/specs/2026-04-08-admin-global-platform-design.md`

---

## Mapa de arquivos

### Backend — criar
| Arquivo | Responsabilidade |
|---|---|
| `backend/app/models/auditoria.py` | Model AuditoriaAcao (SQLAlchemy 2.0) |
| `backend/app/services/auditoria_service.py` | Registrar e listar eventos de auditoria |
| `backend/app/api/v1/endpoints/admin_plataforma.py` | GET /admin/plataforma/dashboard, /admin/licencas, /admin/usuarios/contagem, /admin/auditoria |
| `backend/app/api/v1/endpoints/admin_usuarios.py` | POST/GET/PATCH /admin/usuarios |
| `backend/tests/unit/test_auditoria_service.py` | Testes do AuditoriaService |
| `backend/tests/unit/test_admin_plataforma.py` | Testes dos endpoints de plataforma |
| `backend/tests/unit/test_admin_usuarios.py` | Testes dos endpoints de usuários |

### Backend — modificar
| Arquivo | O que muda |
|---|---|
| `backend/app/api/v1/endpoints/admin_dashboard.py` | Fix: `obter_proximas_consultas` não retorna PII quando `est_id=None` |
| `backend/app/models/__init__.py` | Importar `AuditoriaAcao` |
| `backend/app/api/v1/dependencies.py` | Adicionar `registrar_acesso_clinica` |
| `backend/app/api/v1/router.py` | Registrar `admin_plataforma` e `admin_usuarios` |
| `backend/alembic/versions/` | Nova migration |

### Frontend — criar
| Arquivo | Responsabilidade |
|---|---|
| `frontend-admin/src/app/features/platform-dashboard/platform-dashboard.component.ts` | Dashboard de plataforma (6 cards) |
| `frontend-admin/src/app/features/platform-dashboard/platform-dashboard.component.html` | Template |
| `frontend-admin/src/app/features/licencas/licencas.component.ts` | Lista de licenças global |
| `frontend-admin/src/app/features/licencas/licencas.component.html` | Template |
| `frontend-admin/src/app/features/usuarios/usuarios.component.ts` | Gestão de usuários (ADMIN_GLOBAL view + ADMIN_ESTAB staff) |
| `frontend-admin/src/app/features/usuarios/usuarios.component.html` | Template |
| `frontend-admin/src/app/features/auditoria/auditoria.component.ts` | Log de auditoria paginado |
| `frontend-admin/src/app/features/auditoria/auditoria.component.html` | Template |
| `frontend-admin/src/app/core/services/plataforma.service.ts` | HTTP: dashboard plataforma + licenças + auditoria |
| `frontend-admin/src/app/core/services/usuarios-admin.service.ts` | HTTP: CRUD usuários internos |

### Frontend — modificar
| Arquivo | O que muda |
|---|---|
| `frontend-admin/src/app/core/guards/auth.guard.ts` | ADMIN_GLOBAL vai direto ao dashboard sem forçar seleção |
| `frontend-admin/src/app/shared/shell/shell.component.ts` | NAV_ITEMS separados por modo (global / escopado / ADMIN_ESTABELECIMENTO) |
| `frontend-admin/src/app/shared/shell/shell.component.html` | Badge "Plataforma MedBot" no modo global |
| `frontend-admin/src/app/app.routes.ts` | Rotas para platform-dashboard, licencas, usuarios, auditoria |
| `frontend-admin/src/app/features/dashboard/dashboard.component.html` | Ocultar `proximas_consultas` para ADMIN_GLOBAL global |

---

## Task 1: Fix PII — remover nomes de pacientes/médicos no modo global

**Arquivos:**
- Modify: `backend/app/api/v1/endpoints/admin_dashboard.py`
- Modify: `backend/tests/unit/test_admin_dashboard.py`

- [ ] **Escrever teste que falha: modo global não retorna PII**

Adicionar ao final de `backend/tests/unit/test_admin_dashboard.py`:

```python
async def test_proximas_consultas_modo_global_sem_pii(mock_db):
    """Segurança: est_id=None não expõe paciente_nome nem medico_nome."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (42, time(14, 30), "João Silva", "Dr. Carlos", "Cardiologia", "MEDIA", "AGENDADA"),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await obter_proximas_consultas(
        mock_db, data=date(2026, 4, 8), hora_atual=time(13, 0), estabelecimento_id=None
    )

    assert resultado == [], "modo global deve retornar lista vazia — sem PII"
```

- [ ] **Rodar e confirmar FAIL**

```bash
cd backend && uv run pytest tests/unit/test_admin_dashboard.py::test_proximas_consultas_modo_global_sem_pii -v
```
Esperado: `FAILED`

- [ ] **Implementar fix em `obter_proximas_consultas`**

Em `backend/app/api/v1/endpoints/admin_dashboard.py`, substituir o corpo da função `obter_proximas_consultas`:

```python
async def obter_proximas_consultas(
    db: AsyncSession,
    data: date,
    hora_atual: time,
    estabelecimento_id: int | None,
) -> list[dict]:
    """Retorna até 5 consultas AGENDADA com hora_inicio >= hora_atual.

    Quando estabelecimento_id=None (ADMIN_GLOBAL modo global) retorna []
    para não expor PII (nomes de pacientes e médicos) entre clínicas.
    """
    if estabelecimento_id is None:
        return []

    q = (
        select(
            Consulta.id,
            Slot.hora_inicio,
            Paciente.nome,
            Medico.nome,
            Especialidade.nome,
            Consulta.urgencia,
            Consulta.status,
        )
        .join(Slot,         Consulta.slot_id         == Slot.id)
        .join(Paciente,     Consulta.paciente_id     == Paciente.id)
        .join(Medico,       Consulta.medico_id       == Medico.id)
        .join(Especialidade, Consulta.especialidade_id == Especialidade.id)
        .where(
            Slot.data == data,
            Slot.hora_inicio >= hora_atual,
            Consulta.status == ConsultaStatus.AGENDADA,
            Slot.estabelecimento_id == estabelecimento_id,
        )
        .order_by(Slot.hora_inicio)
        .limit(5)
    )

    result = await db.execute(q)
    return [
        {
            "consulta_id":        row[0],
            "hora_inicio":        row[1].strftime("%H:%M"),
            "paciente_nome":      row[2],
            "medico_nome":        row[3],
            "especialidade_nome": row[4],
            "urgencia":           row[5].value if hasattr(row[5], "value") else row[5],
            "status":             row[6].value if hasattr(row[6], "value") else row[6],
        }
        for row in result.all()
    ]
```

- [ ] **Rodar todos os testes da task**

```bash
cd backend && uv run pytest tests/unit/test_admin_dashboard.py -v
```
Esperado: todos `PASSED`

- [ ] **Commit**

```bash
git add backend/app/api/v1/endpoints/admin_dashboard.py backend/tests/unit/test_admin_dashboard.py
git commit -m "fix(T130): remover PII de proximas_consultas no modo global ADMIN_GLOBAL"
```

---

## Task 2: Model AuditoriaAcao + migration Alembic

**Arquivos:**
- Create: `backend/app/models/auditoria.py`
- Modify: `backend/app/models/__init__.py`
- Create: migration via `alembic revision`

- [ ] **Criar `backend/app/models/auditoria.py`**

```python
"""Model SQLAlchemy 2.0 — AuditoriaAcao (log de ações administrativas)."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TipoAuditoria(str, enum.Enum):
    ACESSO_CLINICA  = "ACESSO_CLINICA"
    LICENCA_ALTERADA = "LICENCA_ALTERADA"
    ESTAB_ALTERADO  = "ESTAB_ALTERADO"
    USUARIO_ALTERADO = "USUARIO_ALTERADO"
    LOGIN           = "LOGIN"
    LOGOUT          = "LOGOUT"


class AuditoriaAcao(Base):
    __tablename__ = "auditoria_acoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False, index=True
    )
    usuario_role: Mapped[str] = mapped_column(String(50), nullable=False)
    acao: Mapped[TipoAuditoria] = mapped_column(
        Enum(TipoAuditoria, name="tipo_auditoria", create_constraint=True),
        nullable=False,
        index=True,
    )
    estabelecimento_id: Mapped[int | None] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=True, index=True
    )
    entidade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entidade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalhes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
```

- [ ] **Adicionar import em `backend/app/models/__init__.py`**

Inserir após a linha `from app.models.sessao_historico import SessaoHistorico`:

```python
from app.models.auditoria import AuditoriaAcao, TipoAuditoria
```

Adicionar `"AuditoriaAcao"` e `"TipoAuditoria"` na lista `__all__`.

- [ ] **Gerar migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_auditoria_acoes"
```

Abrir o arquivo gerado em `backend/alembic/versions/` e confirmar que contém:
- `CREATE TABLE auditoria_acoes`
- `CREATE TYPE tipo_auditoria`
- Índices em `usuario_id`, `acao`, `estabelecimento_id`, `created_at`

- [ ] **Aplicar migration**

```bash
cd backend && uv run alembic upgrade head
```
Esperado: `Running upgrade ... -> ...`

- [ ] **Commit**

```bash
git add backend/app/models/auditoria.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat(T131): model AuditoriaAcao + migration Alembic"
```

---

## Task 3: AuditoriaService — registrar e listar eventos

**Arquivos:**
- Create: `backend/app/services/auditoria_service.py`
- Create: `backend/tests/unit/test_auditoria_service.py`

- [ ] **Criar testes que falham**

Criar `backend/tests/unit/test_auditoria_service.py`:

```python
"""Testes unitários — AuditoriaService (T132)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.auditoria import TipoAuditoria
from app.services.auditoria_service import AuditoriaService


@pytest.fixture
def mock_db():
    return AsyncMock()


async def test_registrar_salva_evento(mock_db):
    """registrar() deve chamar db.add() e db.flush() com os dados corretos."""
    service = AuditoriaService(mock_db)

    await service.registrar(
        acao=TipoAuditoria.LOGIN,
        usuario_id=1,
        usuario_role="ADMIN_GLOBAL",
        estabelecimento_id=None,
        entidade=None,
        entidade_id=None,
        detalhes=None,
        ip_origem="127.0.0.1",
    )

    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()
    evento = mock_db.add.call_args[0][0]
    assert evento.acao == TipoAuditoria.LOGIN
    assert evento.usuario_id == 1
    assert evento.usuario_role == "ADMIN_GLOBAL"
    assert evento.ip_origem == "127.0.0.1"


async def test_registrar_nao_propaga_excecao(mock_db):
    """registrar() deve absorver exceções — nunca quebrar o fluxo principal."""
    mock_db.add.side_effect = Exception("db error")
    service = AuditoriaService(mock_db)

    # Não deve levantar exceção
    await service.registrar(
        acao=TipoAuditoria.ACESSO_CLINICA,
        usuario_id=1,
        usuario_role="ADMIN_GLOBAL",
        estabelecimento_id=5,
        entidade=None,
        entidade_id=None,
        detalhes=None,
        ip_origem=None,
    )


async def test_listar_retorna_eventos(mock_db):
    """listar() deve executar query e retornar lista de AuditoriaAcao."""
    from app.models.auditoria import AuditoriaAcao

    evento = MagicMock(spec=AuditoriaAcao)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [evento]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = AuditoriaService(mock_db)
    resultado = await service.listar(limit=10, offset=0)

    assert len(resultado) == 1
    assert resultado[0] is evento
```

- [ ] **Rodar e confirmar FAIL**

```bash
cd backend && uv run pytest tests/unit/test_auditoria_service.py -v
```
Esperado: `ImportError` ou `ModuleNotFoundError`

- [ ] **Criar `backend/app/services/auditoria_service.py`**

```python
"""Service de auditoria de ações administrativas (T132)."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auditoria import AuditoriaAcao, TipoAuditoria

log = structlog.get_logger(__name__)


class AuditoriaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def registrar(
        self,
        acao: TipoAuditoria,
        usuario_id: int,
        usuario_role: str,
        estabelecimento_id: int | None = None,
        entidade: str | None = None,
        entidade_id: int | None = None,
        detalhes: dict | None = None,
        ip_origem: str | None = None,
    ) -> None:
        """Persiste evento de auditoria. Nunca propaga exceção."""
        try:
            evento = AuditoriaAcao(
                usuario_id=usuario_id,
                usuario_role=usuario_role,
                acao=acao,
                estabelecimento_id=estabelecimento_id,
                entidade=entidade,
                entidade_id=entidade_id,
                detalhes=detalhes,
                ip_origem=ip_origem,
            )
            self.db.add(evento)
            await self.db.flush()
            log.info(
                "auditoria_registrada",
                acao=acao,
                usuario_id=usuario_id,
                estabelecimento_id=estabelecimento_id,
            )
        except Exception as exc:
            log.error("auditoria_falhou", acao=acao, erro=str(exc))

    async def listar(
        self,
        limit: int = 50,
        offset: int = 0,
        estabelecimento_id: int | None = None,
        acao: TipoAuditoria | None = None,
    ) -> list[AuditoriaAcao]:
        """Retorna eventos de auditoria paginados, mais recentes primeiro."""
        q = (
            select(AuditoriaAcao)
            .order_by(AuditoriaAcao.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if estabelecimento_id is not None:
            q = q.where(AuditoriaAcao.estabelecimento_id == estabelecimento_id)
        if acao is not None:
            q = q.where(AuditoriaAcao.acao == acao)

        result = await self.db.execute(q)
        return list(result.scalars().all())
```

- [ ] **Rodar testes**

```bash
cd backend && uv run pytest tests/unit/test_auditoria_service.py -v
```
Esperado: `3 passed`

- [ ] **Commit**

```bash
git add backend/app/services/auditoria_service.py backend/tests/unit/test_auditoria_service.py
git commit -m "feat(T132): AuditoriaService — registrar e listar eventos"
```

---

## Task 4: Dependency registrar_acesso_clinica

**Arquivos:**
- Modify: `backend/app/api/v1/dependencies.py`

- [ ] **Adicionar ao final de `backend/app/api/v1/dependencies.py`**

```python
async def registrar_acesso_clinica(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Registra evento de auditoria quando ADMIN_GLOBAL acessa uma clínica via header.

    Deve ser adicionado como dependency em endpoints de plataforma que aceitam
    X-Estabelecimento-ID de ADMIN_GLOBAL.
    """
    from app.services.auditoria_service import AuditoriaService
    from app.models.auditoria import TipoAuditoria

    role = current_user.get("role", "")
    if role != "ADMIN_GLOBAL":
        return

    header_id = request.headers.get("X-Estabelecimento-ID")
    if not header_id:
        return

    try:
        est_id = int(header_id)
    except ValueError:
        return

    ip = request.client.host if request.client else None
    service = AuditoriaService(db)
    await service.registrar(
        acao=TipoAuditoria.ACESSO_CLINICA,
        usuario_id=int(current_user.get("sub", 0)),
        usuario_role=role,
        estabelecimento_id=est_id,
        detalhes={"path": str(request.url.path), "method": request.method},
        ip_origem=ip,
    )
```

- [ ] **Rodar testes existentes para garantir nenhuma regressão**

```bash
cd backend && uv run pytest tests/ -q
```
Esperado: todos passando

- [ ] **Commit**

```bash
git add backend/app/api/v1/dependencies.py
git commit -m "feat(T133): dependency registrar_acesso_clinica para auditoria ADMIN_GLOBAL"
```

---

## Task 5: Endpoints de plataforma — dashboard, licenças, contagem de usuários, auditoria

**Arquivos:**
- Create: `backend/app/api/v1/endpoints/admin_plataforma.py`
- Create: `backend/tests/unit/test_admin_plataforma.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Criar testes que falham**

Criar `backend/tests/unit/test_admin_plataforma.py`:

```python
"""Testes unitários — endpoints admin_plataforma (T134, T135, T137)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.admin_plataforma import (
    _contagem_licencas_por_status,
    _contagem_usuarios_por_role,
    _total_consultas_hoje,
)


@pytest.fixture
def mock_db():
    return AsyncMock()


async def test_contagem_licencas_por_status(mock_db):
    """Deve retornar dict com contagens por status."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("TRIAL", 3),
        ("ATIVA", 10),
        ("EXPIRADA", 2),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await _contagem_licencas_por_status(mock_db)

    assert resultado["TRIAL"] == 3
    assert resultado["ATIVA"] == 10
    assert resultado["EXPIRADA"] == 2
    assert resultado.get("SUSPENSA", 0) == 0


async def test_contagem_usuarios_por_role(mock_db):
    """Deve retornar dict com contagem por role."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("ADMIN_ESTABELECIMENTO", 5),
        ("RECEPCIONISTA", 8),
        ("MEDICO", 12),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await _contagem_usuarios_por_role(mock_db)

    assert resultado["ADMIN_ESTABELECIMENTO"] == 5
    assert resultado["RECEPCIONISTA"] == 8
    assert resultado["MEDICO"] == 12


async def test_total_consultas_hoje_sem_pii(mock_db):
    """Retorna contagens agregadas — sem campos de nome."""
    from datetime import date

    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("AGENDADA", 15),
        ("REALIZADA", 7),
        ("CANCELADA", 3),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await _total_consultas_hoje(mock_db, date.today())

    assert resultado["agendadas"] == 15
    assert resultado["realizadas"] == 7
    assert resultado["canceladas"] == 3
    assert "paciente_nome" not in resultado
    assert "medico_nome" not in resultado
```

- [ ] **Rodar e confirmar FAIL**

```bash
cd backend && uv run pytest tests/unit/test_admin_plataforma.py -v
```
Esperado: `ImportError`

- [ ] **Criar `backend/app/api/v1/endpoints/admin_plataforma.py`**

```python
"""Endpoints exclusivos para ADMIN_GLOBAL — visão de plataforma.

GET /v1/admin/plataforma/dashboard  — métricas agregadas (sem PII)
GET /v1/admin/licencas              — lista todas as licenças
GET /v1/admin/usuarios/contagem     — contagem de usuários por role
GET /v1/admin/auditoria             — log de ações paginado
"""

from datetime import date, datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_role
from app.core.database import get_db
from app.models.auditoria import AuditoriaAcao, TipoAuditoria
from app.models.consulta import Consulta, ConsultaStatus
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.licenca import Licenca, LicencaStatus
from app.models.usuario import Usuario, UsuarioRole
from app.services.auditoria_service import AuditoriaService
from app.services.ia.billing import obter_custo_diario_total, obter_ranking_por_estabelecimento
from app.services.licenca_service import LicencaService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Plataforma"])

_ROLE_GLOBAL = "ADMIN_GLOBAL"


# ── Queries extraídas (testáveis) ─────────────────────────────────────────────

async def _contagem_licencas_por_status(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(Licenca.status, func.count(Licenca.id)).group_by(Licenca.status)
    )
    return {row[0] if isinstance(row[0], str) else row[0].value: row[1] for row in result.all()}


async def _contagem_usuarios_por_role(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(Usuario.role, func.count(Usuario.id))
        .where(Usuario.ativo == True)  # noqa: E712
        .group_by(Usuario.role)
    )
    return {row[0] if isinstance(row[0], str) else row[0].value: row[1] for row in result.all()}


async def _total_consultas_hoje(db: AsyncSession, data: date) -> dict[str, int]:
    result = await db.execute(
        select(Consulta.status, func.count(Consulta.id))
        .where(cast(Consulta.created_at, Date) == data)
        .group_by(Consulta.status)
    )
    contagens = {row[0] if isinstance(row[0], str) else row[0].value: row[1] for row in result.all()}
    return {
        "agendadas":  contagens.get(ConsultaStatus.AGENDADA,  0),
        "realizadas": contagens.get(ConsultaStatus.REALIZADA, 0),
        "canceladas": contagens.get(ConsultaStatus.CANCELADA, 0),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/plataforma/dashboard",
    summary="KPIs de plataforma para ADMIN_GLOBAL",
    dependencies=[Depends(require_role(_ROLE_GLOBAL))],
)
async def dashboard_plataforma(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Métricas agregadas de toda a plataforma — sem PII."""
    hoje = date.today()

    # Estabelecimentos
    total_estab = (await db.execute(select(func.count(EstabelecimentoSaude.id)))).scalar() or 0
    ativos = (await db.execute(
        select(func.count(EstabelecimentoSaude.id)).where(EstabelecimentoSaude.ativo == True)  # noqa: E712
    )).scalar() or 0

    licencas      = await _contagem_licencas_por_status(db)
    usuarios      = await _contagem_usuarios_por_role(db)
    consultas     = await _total_consultas_hoje(db, hoje)
    custo_total   = float(await obter_custo_diario_total(db, data=hoje, estabelecimento_id=None))
    billing_rank  = await obter_ranking_por_estabelecimento(db, data=hoje)

    # Alertas de plataforma
    alertas: list[dict] = []
    expirando = licencas.get("TRIAL", 0) + licencas.get("EXPIRADA", 0)
    if expirando > 0:
        alertas.append({
            "tipo":     "licencas_expirando",
            "mensagem": f"{expirando} licença(s) em TRIAL ou EXPIRADA",
            "contagem": expirando,
            "link":     "/licencas",
        })
    suspensas = licencas.get("SUSPENSA", 0)
    if suspensas > 0:
        alertas.append({
            "tipo":     "licencas_suspensas",
            "mensagem": f"{suspensas} clínica(s) com licença SUSPENSA",
            "contagem": suspensas,
            "link":     "/licencas",
        })

    log.info("dashboard_plataforma_carregado", total_estab=total_estab, alertas=len(alertas))

    return {
        "data": str(hoje),
        "estabelecimentos": {"total": total_estab, "ativos": ativos, "inativos": total_estab - ativos},
        "licencas_por_status": licencas,
        "usuarios_por_role": usuarios,
        "consultas_hoje": consultas,
        "custo_plataforma_usd": custo_total,
        "billing_top_clinicas": billing_rank[:5],
        "alertas": alertas,
    }


@router.get(
    "/licencas",
    summary="Lista todas as licenças da plataforma",
    dependencies=[Depends(require_role(_ROLE_GLOBAL))],
)
async def listar_licencas(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Retorna todas as licenças com status, plano, datas e nome do estabelecimento."""
    result = await db.execute(
        select(
            Licenca.id,
            Licenca.estabelecimento_id,
            EstabelecimentoSaude.nome,
            Licenca.plano,
            Licenca.status,
            Licenca.licenca_expira_em,
            Licenca.created_at,
        )
        .join(EstabelecimentoSaude, Licenca.estabelecimento_id == EstabelecimentoSaude.id)
        .order_by(Licenca.status, EstabelecimentoSaude.nome)
    )
    service = LicencaService(db)
    rows = result.all()
    return [
        {
            "id":                  row[0],
            "estabelecimento_id":  row[1],
            "estabelecimento_nome": row[2],
            "plano":               row[3],
            "status":              row[4].value if hasattr(row[4], "value") else row[4],
            "expira_em":           row[5].isoformat() if row[5] else None,
            "criada_em":           row[6].isoformat() if row[6] else None,
        }
        for row in rows
    ]


@router.get(
    "/usuarios/contagem",
    summary="Contagem de usuários por role",
    dependencies=[Depends(require_role(_ROLE_GLOBAL))],
)
async def contagem_usuarios(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retorna contagem de usuários ativos agrupada por role."""
    return await _contagem_usuarios_por_role(db)


@router.get(
    "/auditoria",
    summary="Log de auditoria de ações administrativas",
    dependencies=[Depends(require_role(_ROLE_GLOBAL))],
)
async def listar_auditoria(
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: int | None = Query(None),
    acao: TipoAuditoria | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Log paginado de ações administrativas. Somente ADMIN_GLOBAL."""
    service = AuditoriaService(db)
    eventos = await service.listar(
        limit=limit,
        offset=offset,
        estabelecimento_id=estabelecimento_id,
        acao=acao,
    )
    return [
        {
            "id":                evento.id,
            "usuario_id":        evento.usuario_id,
            "usuario_role":      evento.usuario_role,
            "acao":              evento.acao.value if hasattr(evento.acao, "value") else evento.acao,
            "estabelecimento_id": evento.estabelecimento_id,
            "entidade":          evento.entidade,
            "entidade_id":       evento.entidade_id,
            "detalhes":          evento.detalhes,
            "ip_origem":         evento.ip_origem,
            "created_at":        evento.created_at.isoformat() if evento.created_at else None,
        }
        for evento in eventos
    ]
```

- [ ] **Registrar router em `backend/app/api/v1/router.py`**

Adicionar o import:
```python
from app.api.v1.endpoints import (
    ...
    admin_plataforma,
    ...
)
```

Adicionar após `api_router.include_router(admin_dashboard.router)`:
```python
api_router.include_router(admin_plataforma.router)
```

- [ ] **Rodar testes**

```bash
cd backend && uv run pytest tests/unit/test_admin_plataforma.py -v
```
Esperado: `3 passed`

- [ ] **Smoke test nos endpoints**

```bash
cd backend && uv run fastapi dev app/main.py &
# aguardar start, depois:
curl -s http://localhost:8000/v1/admin/plataforma/dashboard | python3 -m json.tool | head -20
```

- [ ] **Commit**

```bash
git add backend/app/api/v1/endpoints/admin_plataforma.py backend/tests/unit/test_admin_plataforma.py backend/app/api/v1/router.py
git commit -m "feat(T134-T135-T137): endpoints de plataforma — dashboard, licenças, auditoria"
```

---

## Task 6: CRUD de usuários internos (ADMIN_ESTABELECIMENTO)

**Arquivos:**
- Create: `backend/app/api/v1/endpoints/admin_usuarios.py`
- Create: `backend/tests/unit/test_admin_usuarios.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Criar testes que falham**

Criar `backend/tests/unit/test_admin_usuarios.py`:

```python
"""Testes unitários — admin_usuarios endpoints (T136)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.admin_usuarios import _validar_role_permitido


def test_validar_role_permitido_aceita_recepcionista():
    assert _validar_role_permitido("RECEPCIONISTA") is True


def test_validar_role_permitido_aceita_medico():
    assert _validar_role_permitido("MEDICO") is True


def test_validar_role_permitido_rejeita_admin_global():
    assert _validar_role_permitido("ADMIN_GLOBAL") is False


def test_validar_role_permitido_rejeita_admin_estabelecimento():
    assert _validar_role_permitido("ADMIN_ESTABELECIMENTO") is False
```

- [ ] **Rodar e confirmar FAIL**

```bash
cd backend && uv run pytest tests/unit/test_admin_usuarios.py -v
```
Esperado: `ImportError`

- [ ] **Criar `backend/app/api/v1/endpoints/admin_usuarios.py`**

```python
"""Endpoints de gestão de usuários internos por estabelecimento (T136).

POST  /v1/admin/usuarios      — criar RECEPCIONISTA ou MEDICO
GET   /v1/admin/usuarios      — listar usuários do estabelecimento
PATCH /v1/admin/usuarios/{id} — atualizar dados / desativar
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_estabelecimento, require_role
from app.core.database import get_db
from app.core.security import hash_password
from app.models.usuario import Usuario, UsuarioRole

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/usuarios", tags=["Admin Usuários"])

_ROLES_PERMITIDOS_CRIAR = {"RECEPCIONISTA", "MEDICO"}


def _validar_role_permitido(role: str) -> bool:
    """ADMIN_ESTABELECIMENTO só pode criar RECEPCIONISTA ou MEDICO."""
    return role in _ROLES_PERMITIDOS_CRIAR


class UsuarioCreateSchema(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    email: EmailStr
    senha: str = Field(min_length=8)
    role: str = Field(pattern="^(RECEPCIONISTA|MEDICO)$")


class UsuarioUpdateSchema(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=200)
    ativo: bool | None = None


@router.post(
    "",
    summary="Criar usuário interno (RECEPCIONISTA ou MEDICO)",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN_ESTABELECIMENTO", "ADMIN_GLOBAL"))],
)
async def criar_usuario(
    dados: UsuarioCreateSchema,
    estabelecimento_id: int = Depends(require_estabelecimento),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cria RECEPCIONISTA ou MEDICO vinculado ao estabelecimento do JWT."""
    if not _validar_role_permitido(dados.role):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Role '{dados.role}' não pode ser criado por este endpoint.",
        )

    existente = await db.execute(select(Usuario).where(Usuario.email == dados.email))
    if existente.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado.",
        )

    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_password(dados.senha),
        role=UsuarioRole(dados.role),
        estabelecimento_id=estabelecimento_id,
        ativo=True,
    )
    db.add(usuario)
    await db.flush()
    await db.commit()

    log.info("usuario_criado", usuario_id=usuario.id, role=dados.role, est_id=estabelecimento_id)
    return {"id": usuario.id, "nome": usuario.nome, "email": usuario.email, "role": dados.role}


@router.get(
    "",
    summary="Listar usuários do estabelecimento",
    dependencies=[Depends(require_role("ADMIN_ESTABELECIMENTO", "ADMIN_GLOBAL"))],
)
async def listar_usuarios(
    estabelecimento_id: int = Depends(require_estabelecimento),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Lista usuários ativos e inativos do estabelecimento do JWT."""
    result = await db.execute(
        select(Usuario)
        .where(Usuario.estabelecimento_id == estabelecimento_id)
        .order_by(Usuario.role, Usuario.nome)
    )
    return [
        {
            "id":    u.id,
            "nome":  u.nome,
            "email": u.email,
            "role":  u.role.value if hasattr(u.role, "value") else u.role,
            "ativo": u.ativo,
        }
        for u in result.scalars().all()
    ]


@router.patch(
    "/{usuario_id}",
    summary="Atualizar ou desativar usuário interno",
    dependencies=[Depends(require_role("ADMIN_ESTABELECIMENTO", "ADMIN_GLOBAL"))],
)
async def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioUpdateSchema,
    estabelecimento_id: int = Depends(require_estabelecimento),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Atualiza nome ou status ativo. Isolado ao estabelecimento do JWT."""
    result = await db.execute(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.estabelecimento_id == estabelecimento_id,
        )
    )
    usuario = result.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    if dados.nome is not None:
        usuario.nome = dados.nome
    if dados.ativo is not None:
        usuario.ativo = dados.ativo

    await db.commit()
    log.info("usuario_atualizado", usuario_id=usuario_id, est_id=estabelecimento_id)
    return {
        "id":    usuario.id,
        "nome":  usuario.nome,
        "email": usuario.email,
        "role":  usuario.role.value if hasattr(usuario.role, "value") else usuario.role,
        "ativo": usuario.ativo,
    }
```

- [ ] **Verificar se `hash_password` existe em `app.core.security`**

```bash
grep -n "hash_password\|def hash" /home/payao/projetos/chatbot-ai-medical/backend/app/core/security.py
```

Se não existir, adicionar em `security.py`:
```python
def hash_password(senha: str) -> str:
    import bcrypt
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
```

- [ ] **Registrar router em `router.py`**

Adicionar import de `admin_usuarios` e:
```python
api_router.include_router(admin_usuarios.router)
```

- [ ] **Rodar testes**

```bash
cd backend && uv run pytest tests/unit/test_admin_usuarios.py -v
```
Esperado: `4 passed`

- [ ] **Rodar suite completa**

```bash
cd backend && uv run pytest tests/ -q
```
Esperado: todos passando

- [ ] **Commit**

```bash
git add backend/app/api/v1/endpoints/admin_usuarios.py backend/tests/unit/test_admin_usuarios.py backend/app/api/v1/router.py backend/app/core/security.py
git commit -m "feat(T136): CRUD /admin/usuarios para ADMIN_ESTABELECIMENTO"
```

---

## Task 7: Frontend — Fix authGuard + NAV_ITEMS por modo

**Arquivos:**
- Modify: `frontend-admin/src/app/core/guards/auth.guard.ts`
- Modify: `frontend-admin/src/app/shared/shell/shell.component.ts`
- Modify: `frontend-admin/src/app/shared/shell/shell.component.html`
- Modify: `frontend-admin/src/app/app.routes.ts`

- [ ] **Corrigir `auth.guard.ts`**

Substituir o conteúdo completo:

```typescript
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthAdminService } from '../services/auth-admin.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthAdminService);
  const router = inject(Router);

  if (!auth.estaAutenticado()) {
    return router.createUrlTree(['/login']);
  }

  // ADMIN_GLOBAL vai direto para o dashboard — sem forçar seleção de clínica
  return true;
};
```

- [ ] **Atualizar `NAV_ITEMS` em `shell.component.ts`**

Substituir o bloco `const NAV_ITEMS` e `navItemsFiltrados`:

```typescript
interface NavItem {
  path: string;
  label: string;
  icon: string;
  modos: Array<'global' | 'escopado' | 'estabelecimento' | '*'>;
}

const NAV_ITEMS: NavItem[] = [
  // ── Modo global (ADMIN_GLOBAL sem clínica) ──────────────────────
  { path: '/dashboard',        label: 'Dashboard',        icon: 'dashboard',        modos: ['*'] },
  { path: '/estabelecimentos', label: 'Estabelecimentos', icon: 'business',         modos: ['global'] },
  { path: '/licencas',         label: 'Licenças',         icon: 'verified',         modos: ['global'] },
  { path: '/usuarios',         label: 'Usuários',         icon: 'manage_accounts',  modos: ['global', 'estabelecimento'] },
  { path: '/billing',          label: 'Billing Global',   icon: 'payments',         modos: ['global'] },
  { path: '/auditoria',        label: 'Auditoria',        icon: 'history',          modos: ['global'] },

  // ── Modo escopado (ADMIN_GLOBAL dentro de uma clínica) ──────────
  { path: '/agenda',           label: 'Agenda',           icon: 'calendar_month',   modos: ['escopado', 'estabelecimento'] },
  { path: '/consultas',        label: 'Consultas',        icon: 'event_note',       modos: ['escopado', 'estabelecimento'] },
  { path: '/pacientes',        label: 'Pacientes',        icon: 'group',            modos: ['escopado', 'estabelecimento'] },
  { path: '/medicos',          label: 'Médicos',          icon: 'medical_services', modos: ['escopado', 'estabelecimento'] },
  { path: '/especialidades',   label: 'Especialidades',   icon: 'category',         modos: ['escopado', 'estabelecimento'] },
  { path: '/billing',          label: 'Billing IA',       icon: 'payments',         modos: ['escopado'] },
  { path: '/documentos',       label: 'Documentos RAG',   icon: 'description',      modos: ['escopado', 'estabelecimento'] },

  // ── Apenas ADMIN_ESTABELECIMENTO ────────────────────────────────
  { path: '/minha-licenca',    label: 'Minha Licença',    icon: 'verified',         modos: ['estabelecimento'] },
];
```

Substituir o computed `navItemsFiltrados`:

```typescript
readonly navItemsFiltrados = computed(() => {
  const role = this.auth.usuario()?.role ?? '';
  const modoGlobal = this.isModoGlobal();
  const modoEscopado = this.isModoEscopado();

  return NAV_ITEMS.filter((item) => {
    if (item.modos.includes('*')) return true;
    if (role === 'ADMIN_GLOBAL' && modoGlobal)   return item.modos.includes('global');
    if (role === 'ADMIN_GLOBAL' && modoEscopado) return item.modos.includes('escopado');
    if (role === 'ADMIN_ESTABELECIMENTO')        return item.modos.includes('estabelecimento');
    return false;
  });
});
```

- [ ] **Atualizar brand no `shell.component.html`**

Substituir o bloco `<!-- Brand -->`:

```html
<!-- Brand -->
<div class="sidebar__brand">
  <mat-icon class="sidebar__brand-icon">local_hospital</mat-icon>
  <div class="sidebar__brand-text">
    @if (isModoGlobal()) {
      <span class="sidebar__brand-name">MedBot</span>
      <span class="sidebar__brand-sub" style="color:#93c5fd">⚡ Plataforma</span>
    } @else if (isModoEscopado()) {
      <span class="sidebar__brand-name">MedBot Admin</span>
      <span class="sidebar__brand-sub">{{ nomeEstabelecimentoAtivo() ?? 'Clínica' }}</span>
    } @else {
      <span class="sidebar__brand-name">MedBot Admin</span>
      <span class="sidebar__brand-sub">Painel de Gestão</span>
    }
  </div>
</div>
```

Adicionar botão "Entrar como clínica" no rodapé do sidebar, após `<mat-divider />`:

```html
@if (isModoGlobal()) {
  <div style="padding:12px 16px">
    <button mat-stroked-button style="width:100%;font-size:12px" (click)="irParaSelecao()">
      <mat-icon>login</mat-icon> Entrar como clínica
    </button>
  </div>
}
@if (isModoEscopado()) {
  <div style="padding:12px 16px">
    <button mat-stroked-button style="width:100%;font-size:12px" (click)="trocarEstabelecimento()">
      <mat-icon>arrow_back</mat-icon> Voltar à plataforma
    </button>
  </div>
}
```

- [ ] **Adicionar rotas em `app.routes.ts`**

Dentro do array `children`, adicionar após `billing/config`:

```typescript
{
  path: 'licencas',
  loadComponent: () =>
    import('./features/licencas/licencas.component').then((m) => m.LicencasComponent),
},
{
  path: 'usuarios',
  loadComponent: () =>
    import('./features/usuarios/usuarios.component').then((m) => m.UsuariosComponent),
},
{
  path: 'auditoria',
  loadComponent: () =>
    import('./features/auditoria/auditoria.component').then((m) => m.AuditoriaComponent),
},
```

- [ ] **Verificar build**

```bash
cd frontend-admin && ng build --configuration=development 2>&1 | tail -20
```
Esperado: sem erros de compilação (warnings de lazy-load são ok)

- [ ] **Commit**

```bash
git add frontend-admin/src/app/core/guards/auth.guard.ts \
        frontend-admin/src/app/shared/shell/shell.component.ts \
        frontend-admin/src/app/shared/shell/shell.component.html \
        frontend-admin/src/app/app.routes.ts
git commit -m "feat(T138): authGuard sem forçar seleção + NAV_ITEMS por modo"
```

---

## Task 8: PlatformDashboardComponent

**Arquivos:**
- Create: `frontend-admin/src/app/features/platform-dashboard/platform-dashboard.component.ts`
- Create: `frontend-admin/src/app/features/platform-dashboard/platform-dashboard.component.html`
- Create: `frontend-admin/src/app/core/services/plataforma.service.ts`
- Modify: `frontend-admin/src/app/features/dashboard/dashboard.component.html`

- [ ] **Criar `plataforma.service.ts`**

```typescript
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';

export interface PlataformaDashboard {
  data: string;
  estabelecimentos: { total: number; ativos: number; inativos: number };
  licencas_por_status: Record<string, number>;
  usuarios_por_role: Record<string, number>;
  consultas_hoje: { agendadas: number; realizadas: number; canceladas: number };
  custo_plataforma_usd: number;
  billing_top_clinicas: Array<{ estabelecimento_id: number; nome: string; custo_total: number }>;
  alertas: Array<{ tipo: string; mensagem: string; contagem: number; link: string }>;
}

@Injectable({ providedIn: 'root' })
export class PlataformaService {
  private readonly api = inject(ApiService);

  readonly kpi    = signal<PlataformaDashboard | null>(null);
  readonly loading = signal(false);
  readonly erro    = signal<string | null>(null);

  async carregar(): Promise<void> {
    this.loading.set(true);
    this.erro.set(null);
    try {
      const data = await firstValueFrom(
        this.api.get<PlataformaDashboard>('/admin/plataforma/dashboard')
      );
      this.kpi.set(data);
    } catch (e: unknown) {
      this.erro.set('Erro ao carregar dashboard');
    } finally {
      this.loading.set(false);
    }
  }
}
```

- [ ] **Criar `platform-dashboard.component.ts`**

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { PlataformaService } from '../../core/services/plataforma.service';

@Component({
  selector: 'app-platform-dashboard',
  standalone: true,
  imports: [DecimalPipe, RouterModule, MatCardModule, MatIconModule, MatProgressSpinnerModule, MatChipsModule],
  templateUrl: './platform-dashboard.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlatformDashboardComponent implements OnInit {
  readonly ps = inject(PlataformaService);

  async ngOnInit(): Promise<void> {
    await this.ps.carregar();
  }

  statusColor(status: string): string {
    const map: Record<string, string> = {
      ATIVA: 'primary', TRIAL: 'accent', EXPIRADA: 'warn', SUSPENSA: 'warn',
    };
    return map[status] ?? 'default';
  }
}
```

- [ ] **Criar `platform-dashboard.component.html`**

```html
@if (ps.loading()) {
  <div style="display:flex;justify-content:center;padding:48px">
    <mat-spinner diameter="40" />
  </div>
}

@if (ps.kpi(); as kpi) {
  <div style="padding:24px;display:flex;flex-direction:column;gap:20px">

    <!-- Linha 1: estabelecimentos + licenças -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px">

      <mat-card>
        <mat-card-header>
          <mat-icon mat-card-avatar>business</mat-icon>
          <mat-card-title>Estabelecimentos</mat-card-title>
        </mat-card-header>
        <mat-card-content style="padding-top:12px">
          <div style="font-size:2rem;font-weight:700">{{ kpi.estabelecimentos.total }}</div>
          <div style="font-size:13px;color:#64748b">{{ kpi.estabelecimentos.ativos }} ativos · {{ kpi.estabelecimentos.inativos }} inativos</div>
        </mat-card-content>
      </mat-card>

      @for (entry of objectEntries(kpi.licencas_por_status); track entry[0]) {
        <mat-card>
          <mat-card-header>
            <mat-icon mat-card-avatar>verified</mat-icon>
            <mat-card-title>{{ entry[0] }}</mat-card-title>
          </mat-card-header>
          <mat-card-content style="padding-top:12px">
            <div style="font-size:2rem;font-weight:700">{{ entry[1] }}</div>
            <div style="font-size:13px;color:#64748b">licenças</div>
          </mat-card-content>
        </mat-card>
      }
    </div>

    <!-- Linha 2: usuários + consultas + custo IA -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px">

      <mat-card>
        <mat-card-header>
          <mat-icon mat-card-avatar>manage_accounts</mat-icon>
          <mat-card-title>Usuários por perfil</mat-card-title>
        </mat-card-header>
        <mat-card-content style="padding-top:12px;display:flex;flex-direction:column;gap:6px">
          @for (entry of objectEntries(kpi.usuarios_por_role); track entry[0]) {
            <div style="display:flex;justify-content:space-between;font-size:13px">
              <span>{{ entry[0] }}</span><strong>{{ entry[1] }}</strong>
            </div>
          }
        </mat-card-content>
      </mat-card>

      <mat-card>
        <mat-card-header>
          <mat-icon mat-card-avatar>event_note</mat-icon>
          <mat-card-title>Consultas hoje</mat-card-title>
        </mat-card-header>
        <mat-card-content style="padding-top:12px;display:flex;flex-direction:column;gap:6px">
          <div style="display:flex;justify-content:space-between;font-size:13px"><span>Agendadas</span><strong>{{ kpi.consultas_hoje.agendadas }}</strong></div>
          <div style="display:flex;justify-content:space-between;font-size:13px"><span>Realizadas</span><strong>{{ kpi.consultas_hoje.realizadas }}</strong></div>
          <div style="display:flex;justify-content:space-between;font-size:13px"><span>Canceladas</span><strong>{{ kpi.consultas_hoje.canceladas }}</strong></div>
        </mat-card-content>
      </mat-card>

      <mat-card>
        <mat-card-header>
          <mat-icon mat-card-avatar>payments</mat-icon>
          <mat-card-title>Custo IA hoje</mat-card-title>
        </mat-card-header>
        <mat-card-content style="padding-top:12px">
          <div style="font-size:2rem;font-weight:700">$ {{ kpi.custo_plataforma_usd | number:'1.4-4' }}</div>
          <div style="font-size:13px;color:#64748b">total da plataforma</div>
        </mat-card-content>
      </mat-card>

    </div>

    <!-- Top clínicas por custo -->
    @if (kpi.billing_top_clinicas.length > 0) {
      <mat-card>
        <mat-card-header><mat-card-title>Top clínicas por custo IA</mat-card-title></mat-card-header>
        <mat-card-content style="padding-top:12px">
          @for (c of kpi.billing_top_clinicas; track c.estabelecimento_id) {
            <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--mat-divider-color);font-size:13px">
              <span>{{ c.nome ?? 'Clínica #' + c.estabelecimento_id }}</span>
              <strong>$ {{ c.custo_total | number:'1.4-4' }}</strong>
            </div>
          }
        </mat-card-content>
      </mat-card>
    }

    <!-- Alertas -->
    @if (kpi.alertas.length > 0) {
      <mat-card>
        <mat-card-header><mat-card-title>Alertas de plataforma</mat-card-title></mat-card-header>
        <mat-card-content style="padding-top:12px;display:flex;flex-direction:column;gap:8px">
          @for (a of kpi.alertas; track a.tipo) {
            <div style="padding:10px;background:rgba(234,179,8,.1);border-radius:6px;border-left:3px solid #ca8a04;font-size:13px">
              {{ a.mensagem }}
            </div>
          }
        </mat-card-content>
      </mat-card>
    }

  </div>
}
```

Adicionar método `objectEntries` no componente `.ts`:
```typescript
readonly objectEntries = Object.entries;
```

- [ ] **Atualizar rota `/dashboard` em `app.routes.ts`**

Tornar o dashboard condicional por role — a rota `/dashboard` carrega `PlatformDashboardComponent` para ADMIN_GLOBAL global ou `DashboardComponent` para os demais. A forma mais simples é: o `DashboardComponent` detecta o role e redireciona:

Em `dashboard.component.ts`, adicionar no `constructor`:
```typescript
constructor() {
  const role = this.auth.usuario()?.role;
  if (role === 'ADMIN_GLOBAL' && !this.auth.usuario()?.estabelecimentoId) {
    inject(Router).navigate(['/platform-dashboard'], { replaceUrl: true });
  }
  // ... effect existente ...
}
```

Adicionar rota `/platform-dashboard` em `app.routes.ts`:
```typescript
{
  path: 'platform-dashboard',
  loadComponent: () =>
    import('./features/platform-dashboard/platform-dashboard.component')
      .then((m) => m.PlatformDashboardComponent),
},
```

Atualizar `NAV_ITEMS` em `shell.component.ts` — mudar o path do dashboard global:
```typescript
{ path: '/platform-dashboard', label: 'Dashboard', icon: 'dashboard', modos: ['global'] },
{ path: '/dashboard',          label: 'Dashboard', icon: 'dashboard', modos: ['escopado', 'estabelecimento'] },
```

- [ ] **Build e verificação**

```bash
cd frontend-admin && ng build --configuration=development 2>&1 | grep -E "error|Error" | head -20
```
Esperado: nenhum erro

- [ ] **Commit**

```bash
git add frontend-admin/src/app/features/platform-dashboard/ \
        frontend-admin/src/app/core/services/plataforma.service.ts \
        frontend-admin/src/app/app.routes.ts \
        frontend-admin/src/app/shared/shell/shell.component.ts \
        frontend-admin/src/app/features/dashboard/dashboard.component.ts
git commit -m "feat(T139): PlatformDashboardComponent + PlataformaService"
```

---

## Task 9: LicencasComponent

**Arquivos:**
- Create: `frontend-admin/src/app/features/licencas/licencas.component.ts`
- Create: `frontend-admin/src/app/features/licencas/licencas.component.html`

- [ ] **Criar `licencas.component.ts`**

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/services/api.service';

interface Licenca {
  id: number;
  estabelecimento_id: number;
  estabelecimento_nome: string;
  plano: string;
  status: string;
  expira_em: string | null;
  criada_em: string | null;
}

@Component({
  selector: 'app-licencas',
  standalone: true,
  imports: [DatePipe, MatTableModule, MatChipsModule, MatIconModule, MatProgressSpinnerModule, MatSelectModule, MatFormFieldModule, FormsModule],
  templateUrl: './licencas.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LicencasComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly licencas  = signal<Licenca[]>([]);
  readonly loading   = signal(false);
  readonly filtroStatus = signal<string>('');

  readonly colunas = ['estabelecimento_nome', 'plano', 'status', 'expira_em', 'criada_em'];

  async ngOnInit(): Promise<void> {
    this.loading.set(true);
    try {
      const data = await firstValueFrom(this.api.get<Licenca[]>('/admin/licencas'));
      this.licencas.set(data);
    } finally {
      this.loading.set(false);
    }
  }

  get licencasFiltradas(): Licenca[] {
    const f = this.filtroStatus();
    return f ? this.licencas().filter((l) => l.status === f) : this.licencas();
  }

  corStatus(status: string): string {
    const map: Record<string, string> = { ATIVA: 'primary', TRIAL: 'accent', EXPIRADA: 'warn', SUSPENSA: 'warn' };
    return map[status] ?? 'default';
  }
}
```

- [ ] **Criar `licencas.component.html`**

```html
<div style="padding:24px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
    <h2 style="margin:0">Licenças da Plataforma</h2>
    <mat-form-field appearance="outline" style="width:180px">
      <mat-label>Filtrar status</mat-label>
      <mat-select [ngModel]="filtroStatus()" (ngModelChange)="filtroStatus.set($event)">
        <mat-option value="">Todos</mat-option>
        <mat-option value="ATIVA">Ativa</mat-option>
        <mat-option value="TRIAL">Trial</mat-option>
        <mat-option value="EXPIRADA">Expirada</mat-option>
        <mat-option value="SUSPENSA">Suspensa</mat-option>
      </mat-select>
    </mat-form-field>
  </div>

  @if (loading()) {
    <div style="display:flex;justify-content:center;padding:48px">
      <mat-spinner diameter="40" />
    </div>
  } @else {
    <table mat-table [dataSource]="licencasFiltradas" style="width:100%">

      <ng-container matColumnDef="estabelecimento_nome">
        <th mat-header-cell *matHeaderCellDef>Estabelecimento</th>
        <td mat-cell *matCellDef="let l">{{ l.estabelecimento_nome }}</td>
      </ng-container>

      <ng-container matColumnDef="plano">
        <th mat-header-cell *matHeaderCellDef>Plano</th>
        <td mat-cell *matCellDef="let l">{{ l.plano }}</td>
      </ng-container>

      <ng-container matColumnDef="status">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let l">
          <mat-chip [color]="corStatus(l.status)" highlighted>{{ l.status }}</mat-chip>
        </td>
      </ng-container>

      <ng-container matColumnDef="expira_em">
        <th mat-header-cell *matHeaderCellDef>Expira em</th>
        <td mat-cell *matCellDef="let l">{{ l.expira_em ? (l.expira_em | date:'dd/MM/yyyy') : '—' }}</td>
      </ng-container>

      <ng-container matColumnDef="criada_em">
        <th mat-header-cell *matHeaderCellDef>Criada em</th>
        <td mat-cell *matCellDef="let l">{{ l.criada_em | date:'dd/MM/yyyy' }}</td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="colunas"></tr>
      <tr mat-row *matRowDef="let row; columns: colunas;"></tr>
    </table>
  }
</div>
```

- [ ] **Build**

```bash
cd frontend-admin && ng build --configuration=development 2>&1 | grep -E "^.*error" | head -10
```

- [ ] **Commit**

```bash
git add frontend-admin/src/app/features/licencas/
git commit -m "feat(T140): LicencasComponent — lista global de licenças"
```

---

## Task 10: UsuariosComponent

**Arquivos:**
- Create: `frontend-admin/src/app/features/usuarios/usuarios.component.ts`
- Create: `frontend-admin/src/app/features/usuarios/usuarios.component.html`

- [ ] **Criar `usuarios.component.ts`**

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { AuthAdminService } from '../../core/services/auth-admin.service';

interface UsuarioInterno {
  id: number; nome: string; email: string; role: string; ativo: boolean;
}

@Component({
  selector: 'app-usuarios',
  standalone: true,
  imports: [FormsModule, MatTableModule, MatButtonModule, MatIconModule, MatDialogModule, MatChipsModule, MatProgressSpinnerModule, MatFormFieldModule, MatInputModule, MatSelectModule],
  templateUrl: './usuarios.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UsuariosComponent implements OnInit {
  private readonly api  = inject(ApiService);
  readonly auth = inject(AuthAdminService);

  readonly usuarios  = signal<UsuarioInterno[]>([]);
  readonly loading   = signal(false);
  readonly isGlobal  = computed(() => this.auth.usuario()?.role === 'ADMIN_GLOBAL' && !this.auth.usuario()?.estabelecimentoId);

  readonly novoNome  = signal('');
  readonly novoEmail = signal('');
  readonly novaSenha = signal('');
  readonly novoRole  = signal('RECEPCIONISTA');
  readonly criando   = signal(false);
  readonly erroForm  = signal<string | null>(null);

  readonly colunas = ['nome', 'email', 'role', 'ativo', 'acoes'];

  async ngOnInit(): Promise<void> {
    await this._carregar();
  }

  private async _carregar(): Promise<void> {
    this.loading.set(true);
    try {
      const data = await firstValueFrom(this.api.get<UsuarioInterno[]>('/admin/usuarios'));
      this.usuarios.set(data);
    } finally {
      this.loading.set(false);
    }
  }

  async criarUsuario(): Promise<void> {
    this.erroForm.set(null);
    this.criando.set(true);
    try {
      await firstValueFrom(this.api.post('/admin/usuarios', {
        nome: this.novoNome(), email: this.novoEmail(),
        senha: this.novaSenha(), role: this.novoRole(),
      }));
      this.novoNome.set(''); this.novoEmail.set('');
      this.novaSenha.set(''); this.novoRole.set('RECEPCIONISTA');
      await this._carregar();
    } catch (e: unknown) {
      this.erroForm.set('Erro ao criar usuário. Verifique os dados.');
    } finally {
      this.criando.set(false);
    }
  }

  async desativar(id: number): Promise<void> {
    await firstValueFrom(this.api.patch(`/admin/usuarios/${id}`, { ativo: false }));
    await this._carregar();
  }

  async reativar(id: number): Promise<void> {
    await firstValueFrom(this.api.patch(`/admin/usuarios/${id}`, { ativo: true }));
    await this._carregar();
  }
}
```

- [ ] **Verificar se `ApiService` tem método `patch`**

```bash
grep -n "patch\|put" /home/payao/projetos/chatbot-ai-medical/frontend-admin/src/app/core/services/api.service.ts
```

Se não tiver, adicionar:
```typescript
patch<T>(path: string, body: unknown): Observable<T> {
  return this.http.patch<T>(`${this.base}${path}`, body);
}
```

- [ ] **Criar `usuarios.component.html`**

```html
<div style="padding:24px">
  <h2>Usuários Internos</h2>

  @if (!isGlobal()) {
    <!-- Formulário de criação — só para ADMIN_ESTABELECIMENTO -->
    <mat-card style="margin-bottom:24px">
      <mat-card-header><mat-card-title>Novo usuário</mat-card-title></mat-card-header>
      <mat-card-content style="padding-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;align-items:end">
        <mat-form-field appearance="outline">
          <mat-label>Nome</mat-label>
          <input matInput [ngModel]="novoNome()" (ngModelChange)="novoNome.set($event)">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>E-mail</mat-label>
          <input matInput type="email" [ngModel]="novoEmail()" (ngModelChange)="novoEmail.set($event)">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Senha</mat-label>
          <input matInput type="password" [ngModel]="novaSenha()" (ngModelChange)="novaSenha.set($event)">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Perfil</mat-label>
          <mat-select [ngModel]="novoRole()" (ngModelChange)="novoRole.set($event)">
            <mat-option value="RECEPCIONISTA">Recepcionista</mat-option>
            <mat-option value="MEDICO">Médico</mat-option>
          </mat-select>
        </mat-form-field>
        <button mat-raised-button color="primary" (click)="criarUsuario()" [disabled]="criando()">
          <mat-icon>person_add</mat-icon> Criar
        </button>
      </mat-card-content>
      @if (erroForm()) {
        <mat-card-footer style="padding:0 16px 12px;color:#ef4444;font-size:12px">{{ erroForm() }}</mat-card-footer>
      }
    </mat-card>
  }

  @if (loading()) {
    <div style="display:flex;justify-content:center;padding:48px"><mat-spinner diameter="40"/></div>
  } @else {
    <table mat-table [dataSource]="usuarios()" style="width:100%">
      <ng-container matColumnDef="nome">
        <th mat-header-cell *matHeaderCellDef>Nome</th>
        <td mat-cell *matCellDef="let u">{{ u.nome }}</td>
      </ng-container>
      <ng-container matColumnDef="email">
        <th mat-header-cell *matHeaderCellDef>E-mail</th>
        <td mat-cell *matCellDef="let u">{{ u.email }}</td>
      </ng-container>
      <ng-container matColumnDef="role">
        <th mat-header-cell *matHeaderCellDef>Perfil</th>
        <td mat-cell *matCellDef="let u"><mat-chip>{{ u.role }}</mat-chip></td>
      </ng-container>
      <ng-container matColumnDef="ativo">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let u">
          <mat-chip [color]="u.ativo ? 'primary' : 'warn'" highlighted>{{ u.ativo ? 'Ativo' : 'Inativo' }}</mat-chip>
        </td>
      </ng-container>
      <ng-container matColumnDef="acoes">
        <th mat-header-cell *matHeaderCellDef></th>
        <td mat-cell *matCellDef="let u">
          @if (!isGlobal()) {
            @if (u.ativo) {
              <button mat-icon-button color="warn" (click)="desativar(u.id)" matTooltip="Desativar">
                <mat-icon>person_off</mat-icon>
              </button>
            } @else {
              <button mat-icon-button color="primary" (click)="reativar(u.id)" matTooltip="Reativar">
                <mat-icon>person</mat-icon>
              </button>
            }
          }
        </td>
      </ng-container>
      <tr mat-header-row *matHeaderRowDef="colunas"></tr>
      <tr mat-row *matRowDef="let row; columns: colunas;"></tr>
    </table>
  }
</div>
```

- [ ] **Build**

```bash
cd frontend-admin && ng build --configuration=development 2>&1 | grep -E "^.*error" | head -10
```

- [ ] **Commit**

```bash
git add frontend-admin/src/app/features/usuarios/ frontend-admin/src/app/core/services/api.service.ts
git commit -m "feat(T141): UsuariosComponent — gestão de staff por ADMIN_ESTABELECIMENTO"
```

---

## Task 11: AuditoriaComponent

**Arquivos:**
- Create: `frontend-admin/src/app/features/auditoria/auditoria.component.ts`
- Create: `frontend-admin/src/app/features/auditoria/auditoria.component.html`

- [ ] **Criar `auditoria.component.ts`**

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/services/api.service';

interface EventoAuditoria {
  id: number;
  usuario_id: number;
  usuario_role: string;
  acao: string;
  estabelecimento_id: number | null;
  entidade: string | null;
  entidade_id: number | null;
  ip_origem: string | null;
  created_at: string;
}

@Component({
  selector: 'app-auditoria',
  standalone: true,
  imports: [DatePipe, FormsModule, MatTableModule, MatIconModule, MatButtonModule, MatProgressSpinnerModule, MatFormFieldModule, MatSelectModule, MatInputModule],
  templateUrl: './auditoria.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuditoriaComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly eventos  = signal<EventoAuditoria[]>([]);
  readonly loading  = signal(false);
  readonly offset   = signal(0);
  readonly limit    = 50;
  readonly filtroAcao = signal('');

  readonly colunas = ['created_at', 'usuario_role', 'acao', 'estabelecimento_id', 'ip_origem'];

  async ngOnInit(): Promise<void> {
    await this._carregar();
  }

  private async _carregar(): Promise<void> {
    this.loading.set(true);
    const params = new URLSearchParams({ limit: String(this.limit), offset: String(this.offset()) });
    if (this.filtroAcao()) params.set('acao', this.filtroAcao());
    try {
      const data = await firstValueFrom(
        this.api.get<EventoAuditoria[]>(`/admin/auditoria?${params}`)
      );
      this.eventos.set(data);
    } finally {
      this.loading.set(false);
    }
  }

  async aplicarFiltro(): Promise<void> {
    this.offset.set(0);
    await this._carregar();
  }

  async proxima(): Promise<void> {
    this.offset.update((v) => v + this.limit);
    await this._carregar();
  }

  async anterior(): Promise<void> {
    this.offset.update((v) => Math.max(0, v - this.limit));
    await this._carregar();
  }
}
```

- [ ] **Criar `auditoria.component.html`**

```html
<div style="padding:24px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
    <h2 style="margin:0">Auditoria de Ações</h2>
    <div style="display:flex;gap:12px;align-items:center">
      <mat-form-field appearance="outline" style="width:200px;margin-bottom:-20px">
        <mat-label>Tipo de ação</mat-label>
        <mat-select [ngModel]="filtroAcao()" (ngModelChange)="filtroAcao.set($event)">
          <mat-option value="">Todas</mat-option>
          <mat-option value="ACESSO_CLINICA">Acesso à clínica</mat-option>
          <mat-option value="LICENCA_ALTERADA">Licença alterada</mat-option>
          <mat-option value="ESTAB_ALTERADO">Estabelecimento</mat-option>
          <mat-option value="USUARIO_ALTERADO">Usuário</mat-option>
          <mat-option value="LOGIN">Login</mat-option>
          <mat-option value="LOGOUT">Logout</mat-option>
        </mat-select>
      </mat-form-field>
      <button mat-raised-button (click)="aplicarFiltro()">Filtrar</button>
    </div>
  </div>

  @if (loading()) {
    <div style="display:flex;justify-content:center;padding:48px"><mat-spinner diameter="40"/></div>
  } @else {
    <table mat-table [dataSource]="eventos()" style="width:100%">
      <ng-container matColumnDef="created_at">
        <th mat-header-cell *matHeaderCellDef>Data/Hora</th>
        <td mat-cell *matCellDef="let e" style="font-size:12px">{{ e.created_at | date:'dd/MM/yy HH:mm:ss' }}</td>
      </ng-container>
      <ng-container matColumnDef="usuario_role">
        <th mat-header-cell *matHeaderCellDef>Role</th>
        <td mat-cell *matCellDef="let e" style="font-size:12px">{{ e.usuario_role }} #{{ e.usuario_id }}</td>
      </ng-container>
      <ng-container matColumnDef="acao">
        <th mat-header-cell *matHeaderCellDef>Ação</th>
        <td mat-cell *matCellDef="let e"><strong style="font-size:12px">{{ e.acao }}</strong></td>
      </ng-container>
      <ng-container matColumnDef="estabelecimento_id">
        <th mat-header-cell *matHeaderCellDef>Clínica</th>
        <td mat-cell *matCellDef="let e" style="font-size:12px">{{ e.estabelecimento_id ?? '—' }}</td>
      </ng-container>
      <ng-container matColumnDef="ip_origem">
        <th mat-header-cell *matHeaderCellDef>IP</th>
        <td mat-cell *matCellDef="let e" style="font-size:12px">{{ e.ip_origem ?? '—' }}</td>
      </ng-container>
      <tr mat-header-row *matHeaderRowDef="colunas"></tr>
      <tr mat-row *matRowDef="let row; columns: colunas;"></tr>
    </table>

    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px">
      <button mat-button [disabled]="offset() === 0" (click)="anterior()">
        <mat-icon>arrow_back</mat-icon> Anterior
      </button>
      <button mat-button [disabled]="eventos().length < 50" (click)="proxima()">
        Próxima <mat-icon>arrow_forward</mat-icon>
      </button>
    </div>
  }
</div>
```

- [ ] **Build final completo**

```bash
cd frontend-admin && ng build --configuration=development 2>&1 | tail -5
```
Esperado: `Build at: ... - Hash: ... - Time: ...ms`

- [ ] **Rodar suite de testes backend**

```bash
cd backend && uv run pytest tests/ -q
```
Esperado: todos passando

- [ ] **Commit final**

```bash
git add frontend-admin/src/app/features/auditoria/
git commit -m "feat(T142): AuditoriaComponent — log paginado de ações administrativas"
```

---

## Self-Review

### Cobertura da spec

| Requisito | Task |
|---|---|
| B1 Fix PII proximas_consultas | Task 1 |
| B2 Model AuditoriaAcao | Task 2 |
| B3 AuditoriaService | Task 3 |
| B4 Dependency registrar_acesso_clinica | Task 4 |
| B5 GET /admin/plataforma/dashboard | Task 5 |
| B6 GET /admin/licencas | Task 5 |
| B7 GET /admin/usuarios/contagem | Task 5 |
| B8 GET /admin/auditoria | Task 5 |
| B9-B11 CRUD /admin/usuarios | Task 6 |
| F1 Fix PII no template | Task 1 + Task 8 |
| F2 Fix authGuard | Task 7 |
| F3 NAV_ITEMS por modo | Task 7 |
| F4 Verificar tenant.interceptor | Task 7 (já existia) |
| F5 PlatformDashboardComponent | Task 8 |
| F6 LicencasGlobalComponent | Task 9 |
| F7 UsuariosComponent | Task 10 |
| F8 AuditoriaComponent | Task 11 |
| F9 DashboardService.carregarPlataforma | Task 8 (PlataformaService) |
| F10 AuditoriaService | Task 11 (embutido no componente) |
| F11 UsuariosService | Task 10 (embutido no componente) |

Todos os requisitos cobertos.
