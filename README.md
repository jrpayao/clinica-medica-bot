# MedBot — Sistema de Agendamento Médico com IA

Sistema completo de automação de clínicas médicas com IA, cobrindo agendamento via WhatsApp/portal, triagem clínica, fluxo de recepção, gestão de licenças e painel multi-tenant.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI 0.135 + SQLAlchemy 2.0 async + Alembic |
| Package Manager | uv |
| Banco de dados | PostgreSQL 16 |
| Cache / Fila | Redis 7 + Celery |
| Vector DB | Qdrant (RAG) |
| LLM | Ollama (dev) / OpenRouter (prod) |
| Frontend Portal | Angular 21 (standalone, signals, OnPush) |
| Frontend Admin | Angular 21 (standalone, signals, OnPush) |
| WhatsApp | Evolution API (self-hosted) |

## Ambiente Local

```bash
# Infra (PostgreSQL + Redis + Qdrant)
cd backend && docker compose up -d

# Backend
cd backend && uv run fastapi dev app/main.py --port 8100

# Testes
cd backend && uv run pytest tests/ -q

# Frontend portal (pacientes)
cd frontend-portal && ng serve --port 4200

# Frontend admin (clínica)
cd frontend-admin && ng serve --port 4201
```

## Links

| Serviço | URL |
|---|---|
| FastAPI docs | http://localhost:8100/docs |
| Frontend Portal | http://localhost:4200 |
| Frontend Admin | http://localhost:4201 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Ollama | http://localhost:11434 |

## Metodologia

Projeto desenvolvido com **SDD (Spec-Driven Development)** — padrão Automaxia v2.0.

| Artefato | Arquivo |
|---|---|
| Constituição | `CONSTITUTION.md` |
| Especificação | `SPEC-MEDBOT.md` |
| Plano Técnico | `PLAN.md` |
| Tasks | `TASK.md` |
| ADRs | `docs/decisoes-tecnicas.md` |

## Progresso

`[●●●●●●●●●●]` 95% — 124/129 tasks concluídas

| Grupo | Status |
|---|---|
| G0–G13 | ✅ 100% |
| G14 Fluxo Guiado | 🔄 87% |
| G15 Diferenciais | 🔄 89% |
| G22 ADMIN_GLOBAL | ✅ 100% |
| G23 Painel RECEPCIONISTA | 🔄 Em andamento |
| G24 Painel MÉDICO | ⛔ Backlog |
| G9 Deploy | ⛔ Backlog |

## Roles

| Role | Descrição |
|---|---|
| `ADMIN_GLOBAL` | Plataforma multi-tenant — gerencia todos os estabelecimentos |
| `ADMIN_ESTABELECIMENTO` | Administrador de uma clínica |
| `RECEPCIONISTA` | Operador de recepção — check-in e fluxo do paciente |
| `MEDICO` | Visualiza própria agenda e atendimentos |
| `PACIENTE` | Agenda via portal ou WhatsApp |
