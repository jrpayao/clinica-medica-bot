# Design — Plataforma ADMIN_GLOBAL + Gestão de Usuários ADMIN_ESTABELECIMENTO

> Data: 2026-04-08
> Status: APROVADO
> Sessão de brainstorming: `.superpowers/brainstorm/79893-1775690185/`

---

## Contexto

O painel admin (`frontend-admin`) expõe o mesmo menu e dashboard para todos os roles. O ADMIN_GLOBAL — administrador da plataforma, não de uma clínica — não tem dashboard próprio, vê dados sensíveis de pacientes (PII) agregados de todas as clínicas, e enfrenta menus quebrados (Agenda/Consultas/Pacientes retornam HTTP 400 no modo global).

O ADMIN_ESTABELECIMENTO não consegue criar usuários internos (RECEPCIONISTA, MEDICO) — os roles existem no banco mas não há endpoint nem tela de gestão.

---

## Decisões de Design

### 1. Acesso de ADMIN_GLOBAL a clínicas — Opção B (header + auditoria)

ADMIN_GLOBAL **nunca troca o JWT** ao entrar em uma clínica. O frontend envia o header `X-Estabelecimento-ID` em todas as requisições quando o admin está operando dentro de uma clínica. O backend registra automaticamente um evento de auditoria `ACESSO_CLINICA`.

- **Motivo:** rastreabilidade total (LGPD/compliance). Os logs sempre mostram "ADMIN_GLOBAL Junior acessou Clínica X às 14h32", sem ambiguidade.
- O backend já suporta via `get_estabelecimento_id_opcional` que lê o header. Nenhuma mudança de autenticação necessária.

### 2. Dashboard de plataforma — 6 cards, sem PII

O ADMIN_GLOBAL em modo global vê métricas agregadas de plataforma, nunca nomes de pacientes ou médicos:

1. Estabelecimentos ativos / inativos
2. Licenças por status (TRIAL / ATIVA / EXPIRADA / SUSPENSA)
3. Billing global — ranking de custo por clínica
4. Volume de consultas agregado (contagens apenas, sem nomes)
5. Usuários por role
6. Alertas de plataforma (licenças expirando, clínicas inativas, custo alto)

### 3. Menu diferenciado por modo

| Modo Global | Modo Escopado (dentro de clínica) |
|---|---|
| Dashboard (plataforma) | Dashboard (clínica) |
| Estabelecimentos | Agenda |
| Licenças | Consultas |
| Usuários | Pacientes |
| Billing Global | Médicos |
| Auditoria | Especialidades |
| → Entrar como clínica | Billing IA |
| | Documentos RAG |
| | ↩ Voltar à plataforma |

### 4. Auditoria — modelo AuditoriaAcao, 5 tipos de evento

Registra: acesso de ADMIN_GLOBAL a clínica, alterações em licenças, alterações em estabelecimentos, alterações em usuários, login/logout de admins.

### 5. Gestão de usuários internos — ADMIN_ESTABELECIMENTO

ADMIN_ESTABELECIMENTO ganha tela e endpoints para criar/listar/desativar usuários do tipo RECEPCIONISTA e MEDICO vinculados ao seu estabelecimento.

---

## Escopo desta entrega

### Backend

| # | Tipo | Item |
|---|---|---|
| B1 | Fix | Remover `paciente_nome` / `medico_nome` de `proximas_consultas` quando `est_id=None` em `admin_dashboard.py` |
| B2 | Novo | Model `AuditoriaAcao` + migration Alembic |
| B3 | Novo | `AuditoriaService.registrar(acao, usuario_id, role, estab_id, entidade, detalhes, ip)` |
| B4 | Novo | Dependency `registrar_acesso_clinica` — captura header `X-Estabelecimento-ID` + chama `AuditoriaService` |
| B5 | Novo | `GET /v1/admin/plataforma/dashboard` — métricas agregadas (total estab., licenças por status, usuários por role, consultas hoje, custo total, alertas) |
| B6 | Novo | `GET /v1/admin/licencas` — lista todas as licenças com status, plano, vencimento, estabelecimento |
| B7 | Novo | `GET /v1/admin/usuarios/contagem` — contagem de usuários por role |
| B8 | Novo | `GET /v1/admin/auditoria` — histórico paginado com filtros (acao, estabelecimento_id, data_inicio, data_fim) |
| B9 | Novo | `POST /v1/admin/usuarios` — criar RECEPCIONISTA ou MEDICO (ADMIN_ESTABELECIMENTO, isolado por est_id do JWT) |
| B10 | Novo | `GET /v1/admin/usuarios` — listar usuários do estabelecimento (ADMIN_ESTABELECIMENTO) |
| B11 | Novo | `PATCH /v1/admin/usuarios/{id}` — atualizar dados / desativar usuário |

### Frontend (Angular 21)

| # | Tipo | Item |
|---|---|---|
| F1 | Fix | `admin_dashboard.py` já corrigido em B1; `dashboard.component.html` não renderiza `proximas_consultas` para ADMIN_GLOBAL global |
| F2 | Fix | `authGuard` — ADMIN_GLOBAL vai direto ao `/dashboard` de plataforma sem forçar seleção |
| F3 | Fix | `NAV_ITEMS` em `shell.component.ts` — menu diferenciado por modo (global vs escopado vs ADMIN_ESTABELECIMENTO) |
| F4 | Verificar | `tenant.interceptor.ts` já envia `X-Estabelecimento-ID` — validar que cobre o novo fluxo de "entrar como clínica" sem JWT escopado |
| F5 | Novo | `PlatformDashboardComponent` — rota `/dashboard` para ADMIN_GLOBAL modo global, 6 cards |
| F6 | Novo | `LicencasGlobalComponent` — rota `/licencas`, tabela com status, plano, vencimento, ações |
| F7 | Novo | `UsuariosGlobalComponent` — rota `/usuarios`, visão plataforma (ADMIN_GLOBAL) + gestão de staff (ADMIN_ESTABELECIMENTO) |
| F8 | Novo | `AuditoriaComponent` — rota `/auditoria`, tabela paginada com filtros de data/ação/clínica |
| F9 | Novo | `DashboardService.carregarPlataforma()` — consome `GET /admin/plataforma/dashboard` |
| F10 | Novo | `AuditoriaService` — consome endpoints de auditoria |
| F11 | Novo | `UsuariosService` — CRUD de usuários internos |

---

## Fora de escopo (backlog — tasks criadas)

- Painel do RECEPCIONISTA (menu operacional, sem billing/licença)
- Painel do MÉDICO (agenda própria, consultas próprias, filtro por medico_id)
- Vínculo entre `Medico` (model de agenda) e role `MEDICO` (usuário de login)

---

## Modelo de dados novo

```python
# AuditoriaAcao
id:                int          PK
usuario_id:        int          FK → usuarios.id
usuario_role:      str          ADMIN_GLOBAL | ADMIN_ESTABELECIMENTO
acao:              str          ACESSO_CLINICA | LICENCA_ALTERADA | ESTAB_ALTERADO | USUARIO_ALTERADO | LOGIN | LOGOUT
estabelecimento_id: int | None  FK → estabelecimentos.id
entidade:          str | None   "licenca" | "usuario" | "estabelecimento"
entidade_id:       int | None
detalhes:          JSONB | None  diff antes/depois, motivo
ip_origem:         str | None
created_at:        datetime     server_default=now()
```

---

## Requisitos não funcionais

- CPF mascarado em qualquer log ou response da auditoria (CONSTITUTION)
- `AuditoriaService.registrar()` não deve quebrar o fluxo principal em caso de erro — registrar com `try/except` e logar via structlog
- Endpoints de auditoria paginados (limit/offset, max 100/página)
- Testes unitários obrigatórios para cada endpoint novo (TDAD — testes RED primeiro)

---

## Arquivos críticos a alterar

| Arquivo | Motivo |
|---|---|
| `backend/app/api/v1/endpoints/admin_dashboard.py` | Fix PII em proximas_consultas |
| `backend/app/api/v1/dependencies.py` | Adicionar dependency registrar_acesso_clinica |
| `frontend-admin/src/app/shared/shell/shell.component.ts` | NAV_ITEMS por modo |
| `frontend-admin/src/app/core/guards/auth.guard.ts` | Fix redirect ADMIN_GLOBAL |
| `frontend-admin/src/app/app.routes.ts` | Rotas novas |
| `frontend-admin/src/app/core/services/dashboard.service.ts` | carregarPlataforma() |
