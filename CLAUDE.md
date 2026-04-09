# CLAUDE.md — MedBot Agendamentos Medicos
> Arquivo de configuracao do agente Claude Code.
> Versao: 3.0 | Atualizado: Abril 2026

---

## IDENTIDADE DO PROJETO

**Nome:** MedBot — Sistema de Agendamento Medico com IA
**Metodologia:** SDD (Spec-Driven Development) — padrao Automaxia v2.0

---

## ARTEFATOS SDD (ler antes de qualquer acao)

| Artefato | Arquivo | Conteudo |
|---|---|---|
| Constituicao | `CONSTITUTION.md` | Regras inviolaveis, stack fixada, glossario |
| Especificacao | `SPEC-MEDBOT.md` | Requisitos funcionais (GEARS) |
| Plano Tecnico | `PLAN.md` | Arquitetura, modelo de dados, contratos API |
| Tasks | `TASK.md` | Tarefas atomicas com progresso |
| ADRs | `docs/decisoes-tecnicas.md` | Decisoes tecnicas registradas |

---

## SKILLS OBRIGATORIAS

| Quando | Skill |
|---|---|
| **SEMPRE** | `padrao-sdd` |
| **Tasks backend (qualquer grupo)** | `skill-python-fastapi` |
| **Tasks frontend portal** | `automaxia-angular` |
| **Tasks frontend admin** | `automaxia-angular` |
| **Executar plano com subagentes** | `superpowers:subagent-driven-development` |
| **Executar plano inline** | `superpowers:executing-plans` |
| **QA e testes E2E** | `skill-qa-playwright` + `playwright-skill` |
| **Debugging** | `superpowers:systematic-debugging` |
| **Finalizar branch** | `superpowers:finishing-a-development-branch` |
| **Iniciar nova feature** | `superpowers:brainstorming` → `superpowers:writing-plans` |

```
ANTES DE QUALQUER ACAO:
1. Leia CONSTITUTION.md + PLAN.md + TASK.md
2. Leia ~/.claude/skills/padrao-sdd/SKILL.md

ANTES DE TASKS DE BACKEND:
3. Leia ~/.claude/skills/skill-python-fastapi/SKILL.md

ANTES DE TASKS DE FRONTEND:
4. Leia ~/.claude/skills/automaxia-angular/SKILL.md

ANTES DE EXECUTAR UM PLANO:
5. Use superpowers:subagent-driven-development (preferido) ou superpowers:executing-plans
```

---

## CONSTITUICAO — Ver `CONSTITUTION.md`

Resumo das regras criticas (detalhes completos no arquivo):

- **uv** como package manager — NUNCA pip
- **lifespan** — NUNCA @app.on_event
- **SQLAlchemy 2.0** Mapped[] — NUNCA sintaxe 1.x
- **asyncio_mode = "auto"** — NUNCA @pytest.mark.asyncio
- **structlog** — NUNCA print()
- **Toda chamada LLM** passa pelo billing_service
- **EMERGENCIA** → SAMU 192 → bloqueia agendamento
- **CPF mascarado** em logs e respostas
- **JWT + RBAC** em rotas protegidas

---

## DASHBOARD DE FEATURES — Ver `TASK.md`

**Progresso geral:** `[●●●●●●●●●●]` 95% — 124 de 129 tasks concluidas (G9 Deploy + T85 + T103-T104 + G16-G17 BACKLOG pendentes)

| Grupo | Status |
|---|---|
| G0 Setup | ✅ 100% |
| G1 Auth | ✅ 100% |
| G2 Agenda | ✅ 100% |
| G3 Chat IA | ✅ 100% |
| G4 RAG | ✅ 100% |
| G5 Billing | ✅ 100% |
| G6 Notificacoes | ✅ 100% |
| G7 Frontend Portal | ✅ 100% |
| G8 Frontend Admin | ✅ 100% (7/7) |
| G9 Deploy | ⬜ 0% — iniciar apos G22 ✅ |
| G10 Refinamento IA | ✅ 100% (5/5) |
| G11 Multi-tenancy | ✅ 100% (8/8) |
| G12 Licenciamento | ✅ 100% (11/11) |
| G13 Revisao Qualidade | ✅ 100% (3/3) |
| G14 Fluxo Guiado Agendamento | 🔄 87% (7/8) — pendente: T85 |
| G15 Diferenciais de Mercado | 🔄 89% (17/19) — pendente: T103, T104 |
| G16 N3 Enterprise | ⛔ BACKLOG (0/3) |
| G17 Plataforma BotFlow | ⛔ BACKLOG (0/4) |
| G18 Qualidade: Correcoes IA | ✅ 100% (3/3) |
| G19 Dashboard Gerencial v2 | ✅ 100% (5/5) |
| G20 Agenda Gerencial | ✅ 100% (4/4) |
| G21 Multi-tenancy UX Fixes | ✅ 100% (6/6) |
| G22 ADMIN_GLOBAL Platform | ✅ 100% (13/13) — concluido 2026-04-08 |
| G23 Painel RECEPCIONISTA | ⛔ BACKLOG (0/3) — iniciar apos G22 ✅ |
| G24 Painel MEDICO | ⛔ BACKLOG (0/3) — iniciar apos G23 |

**Tasks pendentes em aberto:**
- G14: T85 (frontend fluxo guiado — renderizacao chat)
- G15: T103 (abstracao WhatsApp provider) + T104 (E2E diferenciais)
- G9: T47–T50 (Deploy Hostinger + CapRover)
- G23: T143–T145 (Painel RECEPCIONISTA) — **PROXIMA ENTREGA**

---

## WORKFLOW DO AGENTE

1. Ler CLAUDE.md + CONSTITUTION.md + PLAN.md
2. Consultar TASK.md para proxima task pendente
3. Ler secao do SPEC-MEDBOT.md correspondente
4. **TDAD:** testes RED antes da implementacao
5. Implementar codigo minimo para GREEN
6. Builder-Verifier (ver CONSTITUTION.md)
7. Marcar task ✅ no TASK.md e CLAUDE.md
8. Resumo Pos-Task

### Ambiguidade:
- SPEC-MEDBOT.md primeiro → se nao resolver → perguntar → ADR em `docs/decisoes-tecnicas.md`

### Nunca:
- Pular tasks | Alterar CONSTITUTION sem aprovacao | print() | pip | @app.on_event | LLM sem billing

---

## AMBIENTE LOCAL

```bash
# Infra
cd backend && docker compose up -d
# postgres:5432 | redis:6379 | qdrant:6333

# Backend
cd backend && uv run fastapi dev app/main.py

# Testes
cd backend && uv run pytest tests/ -q

# Frontend portal
cd frontend-portal && ng serve --port 4200

# Frontend admin
cd frontend-admin && ng serve --port 4201
```

## LLM LOCAL — Ollama (ADR-009/010)

**Hardware dev:** Alienware Area 51 + RTX 5090 (maquina local do dev)
**Modelos instalados:**
- `llama3.1:8b` → saudacao, coleta de dados, agendamento (economico)
- `cniongolo/biomistral:latest` → triagem clinica (especializado medico)
- `nomic-embed-text` → embeddings para RAG no Qdrant

```bash
ollama serve
# Dev local: substitui OpenRouter — zero custo de tokens
# Producao (VPS): OpenRouter via LangChain (OPENROUTER_API_KEY no .env)
# Startup: valida automaticamente modelos disponiveis ao iniciar
```

---

## DEPLOY — Hostinger KVM 4 (ADR-007)

**VPS contratado:** Hostinger KVM 4
4 vCPU | 16GB RAM | 200GB NVMe | Brasil — Campinas (28ms)
Ubuntu 24.04 LTS | R$62,99/mes (12 meses) | BRL sem cambio

**Stack no VPS (todos via CapRover + Docker):**
- FastAPI + Celery Worker + Celery Beat
- PostgreSQL 16 + Redis 7 + Qdrant
- Evolution API (WhatsApp — free, Apache 2.0)
- frontend-portal + frontend-admin (Nginx via CapRover)

**Estrategia por fase (ADR-007):**
- Fase 1 — Demo: Railway Free Trial (gratis, 30 dias, zero config)
- Fase 2 — MVP: Hostinger KVM 4 + CapRover (VPS ja contratado)
- Fase 3 — Plataforma: mesmo KVM 4, multiplos bots via CapRover (R$0 extra)

**URLs producao (preencher apos T47-T50):**
- Portal:   https://portal.medbot.[dominio]
- Admin:    https://admin.medbot.[dominio]
- API:      https://api.medbot.[dominio]
- Qdrant:   https://qdrant.medbot.[dominio]

---

## WHATSAPP — Evolution API (ADR-027)

**Provedor atual:** Evolution API (self-hosted no VPS)
**Custo:** R$0 — open source, Apache 2.0
**Config .env:** `WHATSAPP_PROVIDER=evolution`
**Provedores suportados (T103):** `evolution` | `uazapi` | `zapi` | `meta`
**Trocar provedor:** apenas mudar WHATSAPP_PROVIDER no .env
**Setup no VPS:** CapRover → novo app → docker-compose → scan QR Code

---

## LINKS UTEIS

```
Ollama:       http://localhost:11434
Qdrant:       http://localhost:6333/dashboard
FastAPI docs: http://localhost:8100/docs
Portal:       http://localhost:4200
Admin:        http://localhost:4201
Postman:      postman/MedBot-API.postman_collection.json
```
