# PLAN — MedBot Agendamentos Médicos
> Derivado de: SPEC-MEDBOT.md | Guiado por: CONSTITUTION.md
> Status: **APROVADO** — Executar somente após aprovação humana.
> Versão: 1.0 | Data: Abril 2026

---

## 1. Decisões de Stack

Stack fixada na CONSTITUTION.md. Justificativas das decisões-chave:

| Decisão | Escolha | Justificativa |
|---|---|---|
| Framework backend | FastAPI 0.135 | Performance async, WebSocket nativo, autodoc OpenAPI |
| ORM | SQLAlchemy 2.0 async | Único ORM Python com async completo e Mapped[] type-safe |
| Package manager | uv | 10-100x mais rápido que pip, lockfile determinístico |
| LLM Gateway | OpenRouter | Multi-modelo, roteamento por custo, sem lock-in |
| Vector DB | Qdrant | Performance superior ao pgvector para RAG em produção |
| Dois frontends | Angular 21 separados | Superfícies de ataque e ciclos de deploy independentes |
| Jobs | Celery + Redis | Lembretes e alertas não podem bloquear o request cycle |

---

## 2. Arquitetura de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENTES                             │
├──────────────┬──────────────────┬──────────────────────────┤
│ Portal Web   │  WhatsApp        │   Admin Web              │
│ (Angular 21) │  (Evolution API) │   (Angular 21)           │
│ localhost:4200│  Webhook         │   localhost:4201         │
└──────┬───────┴────────┬─────────┴──────────┬───────────────┘
       │                │                    │
       └────────────────┴────────────────────┘
                        │ HTTPS/WSS
                        ▼
         ┌──────────────────────────────┐
         │      FastAPI Backend         │
         │      localhost:8100          │
         │                              │
         │  /v1/auth    /v1/agenda      │
         │  /v1/chat/ws /v1/consultas   │
         │  /v1/billing /v1/rag         │
         └──────┬───────────────────────┘
                │
    ┌───────────┼───────────────────┐
    ▼           ▼                   ▼
PostgreSQL    Redis              Qdrant
(dados)     (sessões/cache)    (embeddings RAG)
                │
                ▼
            Celery Workers
         (lembretes + alertas)
                │
         ┌──────┴──────┐
         ▼             ▼
    Evolution API   SendGrid
    (WhatsApp)      (Email)
```

---

## 3. Modelo de Dados

### Entidades e Relacionamentos

```
Especialidade (1) ──────── (N) Medico
Medico (1) ─────────────── (N) Slot
Slot (1) ────────────────── (1) Consulta
Paciente (1) ──────────── (N) Consulta
Consulta (1) ──────────── (N) SessaoChat (indireta)
SessaoChat (1) ────────── (N) TokenUsage
```

### Schemas das Entidades Principais

```sql
-- Tabelas PostgreSQL 16

especialidades
  id SERIAL PK | nome VARCHAR(100) | cor_hex VARCHAR(7) | ativo BOOLEAN

medicos
  id SERIAL PK | crm VARCHAR(20) UNIQUE | nome VARCHAR(200)
  especialidade_id FK | email VARCHAR(254) | duracao_consulta_min INT DEFAULT 30 | ativo BOOLEAN

pacientes
  id SERIAL PK | cpf VARCHAR(11) UNIQUE INDEX | nome VARCHAR(200)
  data_nascimento DATE | telefone VARCHAR(20) | email VARCHAR(254)
  convenio VARCHAR(100) | numero_carteirinha VARCHAR(50) | ativo BOOLEAN

slots
  id SERIAL PK | medico_id FK | data DATE | hora_inicio TIME | hora_fim TIME
  status ENUM(DISPONIVEL, BLOQUEADO, AGENDADO, ENCAIXE) | motivo_bloqueio TEXT

consultas
  id SERIAL PK | slot_id FK UNIQUE | paciente_id FK | medico_id FK | especialidade_id FK
  tipo ENUM(EXTERNO, INTERNO, ENCAIXE, RETORNO)
  status ENUM(AGENDADA, CONFIRMADA, CANCELADA, REALIZADA, FALTA)
  triagem_resumo JSONB | urgencia ENUM(BAIXA, MEDIA, ALTA, EMERGENCIA)
  canal_origem ENUM(PORTAL, WHATSAPP, INTERNO) | observacoes TEXT

sessoes_chat
  id SERIAL PK | session_token VARCHAR(64) UNIQUE INDEX | paciente_id FK NULLABLE
  canal ENUM(PORTAL, WHATSAPP) | status ENUM(ATIVA, ENCERRADA, AGENDOU, ABANDONOU)
  modelo_ia_usado VARCHAR(100) | encerrada_at TIMESTAMPTZ

token_usage
  id SERIAL PK | session_id FK | modelo VARCHAR(100) | feature VARCHAR(50)
  prompt_tokens INT | completion_tokens INT | total_tokens INT
  cost_usd NUMERIC(10,6) | user_type VARCHAR(20)

usuarios  (acesso interno)
  id SERIAL PK | nome VARCHAR(200) | email VARCHAR(254) UNIQUE
  senha_hash VARCHAR(255) | role ENUM(RECEPCIONISTA, MEDICO, ADMIN)
  medico_id FK NULLABLE | ativo BOOLEAN
```

### Índices Necessários

```sql
CREATE INDEX idx_slots_medico_data ON slots (medico_id, data);
CREATE INDEX idx_slots_status ON slots (status) WHERE status = 'DISPONIVEL';
CREATE INDEX idx_consultas_paciente ON consultas (paciente_id);
CREATE INDEX idx_consultas_medico_data ON consultas (medico_id, created_at);
CREATE INDEX idx_token_usage_created ON token_usage (created_at);
CREATE INDEX idx_sessoes_token ON sessoes_chat (session_token);
```

---

## 4. Contratos de Interface (API)

### Autenticação
```
POST /v1/auth/sms/request    → { cpf } → { expires_in }
POST /v1/auth/sms/verify     → { cpf, code } → { access_token, refresh_token }
POST /v1/auth/login          → { email, password } → { access_token, refresh_token }
POST /v1/auth/refresh        → { refresh_token } → { access_token }
```

### Agenda
```
GET  /v1/agenda/disponivel   → ?especialidade_id&data_inicio&data_fim → Slot[]
GET  /v1/agenda/medico/{id}  → ?data → Slot[] (admin)
POST /v1/agenda/bloquear     → { medico_id, data, hora_inicio, hora_fim, motivo } (admin)
```

### Consultas
```
POST /v1/consultas           → { slot_id, paciente_id, tipo, canal } → Consulta
GET  /v1/consultas/{id}      → Consulta + triagem_resumo
PATCH /v1/consultas/{id}/status → { status, motivo? } → Consulta
GET  /v1/consultas/hoje      → Consulta[] (admin, filtro por médico)
GET  /v1/consultas/paciente/{cpf} → Consulta[] (portal)
```

### Chat / WebSocket
```
WS   /v1/chat/ws/{session_token}  → mensagens bidirecionais
POST /v1/chat/iniciar             → { canal, paciente_id? } → { session_token }
POST /v1/chat/whatsapp            → webhook Evolution API
```

### Billing
```
GET  /v1/billing/dashboard   → { hoje, semana, mes, por_modelo, por_feature }
GET  /v1/billing/sessoes     → TokenUsage[] paginado
GET  /v1/billing/export      → CSV download
PATCH /v1/billing/config     → { daily_limit_usd, monthly_limit_usd, alert_threshold_pct }
```

### RAG
```
POST /v1/rag/documentos      → multipart/form-data (PDF) → { doc_id, chunks }
GET  /v1/rag/documentos      → Documento[]
DELETE /v1/rag/documentos/{id}
```

---

## 5. Estrutura de Pastas

```
medbot/
├── CLAUDE.md            ← Config do agente Claude Code
├── CONSTITUTION.md      ← Leis imutáveis (este nível)
├── SPEC-MEDBOT.md       ← Especificação funcional (GEARS)
├── PLAN.md              ← ESTE ARQUIVO
├── TASKS.md             ← Tarefas atômicas (atualizado durante execução)
├── docs/
│   └── decisoes-tecnicas.md  ← ADRs gerados durante o desenvolvimento
│
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── router.py
│   │   │   └── endpoints/
│   │   │       ├── auth.py
│   │   │       ├── agenda.py
│   │   │       ├── consultas.py
│   │   │       ├── chat.py
│   │   │       ├── billing.py
│   │   │       ├── rag.py
│   │   │       ├── pacientes.py
│   │   │       ├── medicos.py
│   │   │       └── especialidades.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── redis.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── models/
│   │   │   ├── base.py
│   │   │   ├── especialidade.py
│   │   │   ├── medico.py
│   │   │   ├── paciente.py
│   │   │   ├── slot.py
│   │   │   ├── consulta.py
│   │   │   ├── sessao_chat.py
│   │   │   ├── token_usage.py
│   │   │   └── usuario.py
│   │   ├── schemas/
│   │   │   └── {entidade}.py  ← Create, Update, Response por entidade
│   │   ├── services/
│   │   │   ├── ia/
│   │   │   │   ├── chat_service.py
│   │   │   │   ├── triagem.py
│   │   │   │   ├── rag.py
│   │   │   │   ├── router.py
│   │   │   │   └── billing.py
│   │   │   ├── agenda_service.py
│   │   │   ├── notificacao_service.py
│   │   │   └── whatsapp_service.py
│   │   ├── workers/
│   │   │   ├── lembretes.py
│   │   │   ├── slot_cleanup.py
│   │   │   └── billing_alert.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   └── integration/
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend-portal/     ← Angular 21
│   └── src/app/
│       ├── core/
│       ├── shared/
│       └── features/
│           ├── auth/    ← CPF + SMS
│           ├── chat/    ← WebSocket UI
│           └── agendamentos/
│
├── frontend-admin/      ← Angular 21
│   └── src/app/
│       ├── core/
│       ├── shared/
│       └── features/
│           ├── dashboard/
│           ├── agenda/
│           ├── consultas/
│           ├── pacientes/
│           ├── medicos/
│           └── billing/
│
└── infra/
    ├── k8s/
    │   ├── backend-deployment.yaml
    │   ├── frontend-portal-deployment.yaml
    │   ├── frontend-admin-deployment.yaml
    │   └── ingress.yaml
    ├── docker-compose.yml
    └── nginx/
        └── default.conf
```

---

## 6. Dependências Externas

| Serviço | Propósito | Configuração |
|---|---|---|
| OpenRouter | Gateway LLM | `OPENROUTER_API_KEY` |
| Qdrant | Vector store para RAG | `QDRANT_URL` |
| Evolution API | WhatsApp Business | `EVOLUTION_API_URL` + `EVOLUTION_API_KEY` |
| SendGrid | E-mail transacional | `SENDGRID_API_KEY` |
| Twilio/Zenvia | SMS (código de verificação) | `SMS_PROVIDER` + `SMS_API_KEY` |

---

## 7. ADRs — Architecture Decision Records

### ADR-001: FastAPI em vez de Django REST
- **Contexto:** Escolha do framework Python para API
- **Decisão:** FastAPI
- **Justificativa:** WebSocket nativo, async-first, Pydantic integrado, performance superior
- **Trade-offs:** Menor ecossistema de plugins vs Django, sem admin nativo

### ADR-002: Dois frontends Angular separados
- **Contexto:** Portal público vs painel interno poderiam ser um só app
- **Decisão:** Aplicações Angular separadas
- **Justificativa:** Superfícies de ataque independentes, ciclos de release diferentes, bundle menor por app
- **Trade-offs:** Código compartilhado precisa de biblioteca comum ou repetição

### ADR-003: OpenRouter em vez de SDK direto
- **Contexto:** Escolha de como acessar os modelos LLM
- **Decisão:** OpenRouter via LangChain
- **Justificativa:** Troca de modelo sem mudar código, roteamento por custo, fallback automático
- **Trade-offs:** Latência adicional (~50ms), dependência de terceiro

### ADR-004: Qdrant em vez de pgvector
- **Contexto:** Escolha do vector store para RAG
- **Decisão:** Qdrant standalone
- **Justificativa:** Performance superior para coleções > 100k vetores, filtros híbridos, sem extensão no Postgres
- **Trade-offs:** Mais um serviço a operar, não colocado na mesma instância do Postgres

### ADR-025: Dashboard agregado em endpoint único /admin/dashboard
- **Contexto:** Frontend precisava de KPIs + próximas consultas + alertas + custo IA — originalmente distribuídos em 3 endpoints distintos
- **Decisão:** Criar `GET /admin/dashboard` que agrega todos os dados em uma única resposta
- **Justificativa:** Reduz de 3-4 requests para 1 por carregamento; simplifica tratamento de loading; evita race condition entre chamadas paralelas
- **Trade-offs:** Payload maior; se um dado falhar todos falham — aceitável dado que são todos críticos para o dashboard

### ADR-026: Dashboard ADMIN_GLOBAL usa query param, não JWT scoped
- **Contexto:** ADMIN_GLOBAL precisa filtrar dashboard por estabelecimento
- **Decisão:** `GET /admin/dashboard?estabelecimento_id=N` sem trocar o JWT
- **Justificativa:** Dashboard é read-only e transversal; trocar JWT a cada filtro seria UX ruim e geraria refresh de sessão
- **Trade-offs:** Backend precisa de `_resolver_est_id()` para diferenciar ADMIN_GLOBAL (query param) de ADMIN_ESTABELECIMENTO (JWT)

### ADR-027: Agenda usa JWT scoped (troca de token) para ADMIN_GLOBAL
- **Contexto:** `GET /agenda/slots/dia/{data}` usa `require_estabelecimento` que lê apenas do JWT
- **Decisão:** ADMIN_GLOBAL seleciona estabelecimento na Agenda via `POST /admin/selecionar-estabelecimento` obtendo JWT com est_id
- **Justificativa:** Endpoint de agenda é compartilhado com ADMIN_ESTABELECIMENTO; não há query param de est_id neste endpoint; consistência com o fluxo de seleção de estabelecimento já existente
- **Trade-offs:** UX levemente diferente do Dashboard (troca de token vs query param); ao navegar de volta, est_id persiste no JWT

### ADR-028: Temperatura llama3.1:8b aumentada para 0.6
- **Contexto:** Temperatura 0.3 gerava respostas mecânicas e repetitivas no fluxo de saudação
- **Decisão:** `"llama3.1:8b": {"temperature": 0.6}`
- **Justificativa:** Fluxos de saudação e coleta de dados beneficiam de respostas mais variadas e naturais; triagem clínica usa biomistral (não afetado)
- **Trade-offs:** Ligeiro aumento de variação nas respostas — aceitável para saudação, irrelevante para dados estruturados (nome, CPF)

### ADR-029: Filtro especialidade na Agenda é client-side
- **Contexto:** Backend de agenda suporta apenas `?medico_id=N`, sem filtro por especialidade_id
- **Decisão:** Filtro de especialidade filtra client-side (slots na memória + dropdown de médicos)
- **Justificativa:** Evita nova chamada ao backend; dados já carregados; especialidade é derivada de médico (MedicosService já carrega ambos)
- **Trade-offs:** Ao selecionar especialidade sem selecionar médico, todos os slots de médicos da especialidade são mostrados — comportamento esperado e correto

---

## 8. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Custo LLM excede orçamento | Média | Alto | Billing com alertas em 80% e 100%; bloquear modelo premium |
| Falha do OpenRouter | Baixa | Alto | Fallback para modelo local (Ollama) ou modelo alternativo |
| Latência do chat > 3s | Média | Alto | Streaming de resposta, indicador de digitando no frontend |
| Evolution API instável | Média | Médio | Fila de retry no Celery, notificação alternativa por e-mail |
| Violação de dados de pacientes | Baixa | Crítico | CPF mascarado, JWT curto (15min), auditoria de acesso |

---

> **Aprovado por:** Junior Payão — Abril 2026
> Próximo artefato: `TASKS.md`