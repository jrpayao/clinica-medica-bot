# CONSTITUTION — MedBot Agendamentos Médicos
> Status: **CONGELADO** — Mudanças exigem aprovação explícita do responsável técnico.
> Versão: 1.0 | Data: Abril 2026

---

## Stack Fixada (resultado da entrevista)

| Camada | Tecnologia | Versão |
|---|---|---|
| Backend | Python + FastAPI | 3.12 + ^0.135 |
| ORM | SQLAlchemy async | ^2.0.49 |
| Migrações | Alembic | ^1.13 |
| Schemas | Pydantic v2 | ^2.0 |
| Package manager | uv | latest |
| IA / LLM | OpenRouter via LangChain | ^0.3 |
| Vector DB | Qdrant | ^1.x |
| Cache / Sessões | Redis 7 | ^7 |
| Jobs assíncronos | Celery | ^5.x |
| Banco de dados | PostgreSQL | 16 |
| Frontend Portal | Angular 21 (padrão Automaxia) | ^21.2 |
| Frontend Admin | Angular 21 (padrão Automaxia) | ^21.2 |
| Containerização | Docker multi-stage | — |
| Orquestração | Kubernetes (NKP Zello) | — |
| CI/CD | GitLab CI | — |
| WhatsApp | Evolution API | — |
| E-mail | SendGrid | — |

---

## Princípios de Segurança

1. JWT obrigatório em todas as rotas protegidas — sem exceção
2. RBAC verificado em todo endpoint interno (4 roles: PACIENTE_EXTERNO, RECEPCIONISTA, MEDICO, ADMIN)
3. CPF sempre mascarado em logs, respostas e qualquer output externo
4. NUNCA expor API keys no frontend — todas as chamadas LLM passam pelo backend
5. Rate limiting obrigatório: SMS 1/min por CPF, Chat 60 msgs/hora por sessão
6. Credenciais NUNCA hardcoded — exclusivamente via pydantic-settings + .env

---

## Princípios de Qualidade de Código

### Backend (Python)
1. Type hints obrigatórios em toda função, método e variável de módulo
2. `uv` como package manager — NUNCA usar pip diretamente
3. `fastapi[standard]` como instalação oficial
4. `lifespan` via `@asynccontextmanager` — NUNCA `@app.on_event` (deprecated)
5. SQLAlchemy 2.0: sintaxe `Mapped[]` + `mapped_column()` — NUNCA sintaxe 1.x
6. Async obrigatório: toda query usa `async/await` com `AsyncSession`
7. Alembic para toda mudança de schema — NUNCA `Base.metadata.create_all()`
8. `Depends()` para injeção — NUNCA instanciar services no handler
9. `structlog` — NUNCA `print()` em produção
10. `asyncio_mode = "auto"` no pyproject.toml — NUNCA `@pytest.mark.asyncio` manual
11. Métodos de negócio em português: `agendar`, `cancelar`, `buscar_disponibilidade`
12. Infra/config em inglês: nomes de tabelas, colunas, variáveis de ambiente

### Frontend (Angular 21)
1. `standalone: true` obrigatório — `@NgModule` é PROIBIDO
2. `ChangeDetectionStrategy.OnPush` em TODOS os componentes
3. `provideZonelessChangeDetection()` no `app.config.ts`
4. Signals para estado local: `signal()`, `computed()`, `effect()`
5. Vitest para testes — NUNCA Karma/Jasmine
6. `strict: true` no tsconfig — NUNCA `any` implícito
7. `@use` em SCSS — NUNCA `@import`
8. Métodos CRUD em português: `listar`, `buscarPorId`, `criar`, `atualizar`, `desativar`

### IA / OpenRouter
1. NUNCA fazer chamada LLM sem registrar tokens — todo response passa pelo `billing_service`
2. Modo EMERGENCIA tem prioridade absoluta — detectado → SAMU 192 → bloqueia agendamento
3. RAG é contexto, não resposta — trechos de protocolos nunca exibidos crus ao paciente
4. Roteamento de modelos por feature — modelo correto para cada contexto

---

## Princípios de Arquitetura

### Obrigatórios
- API-first: contratos REST/WebSocket definidos no PLAN.md antes de qualquer implementação
- Two-frontend: portal externo (Angular, acesso por CPF+SMS) e admin interno (Angular, JWT)
- Billing integrado: toda chamada LLM captura tokens e custo em `token_usage`
- Jobs assíncronos: lembretes, alertas de custo e cleanup via Celery — nunca no request cycle
- Subagente de deploy: CI/CD no GitLab com stages test → build → push → deploy

### Proibidos
- Lógica de negócio no handler/controller (vai no service)
- Query síncrona ao banco (SQLAlchemy sempre async)
- Estado global no frontend sem Signals
- Chamada direta ao OpenRouter sem passar pelo roteador de modelos
- Variável de ambiente hardcoded em qualquer arquivo que vai para o repositório

---

## Glossário do Domínio

| Termo | Definição |
|---|---|
| **Consulta** | Agendamento confirmado entre paciente e médico em um slot específico |
| **Slot** | Janela de tempo disponível na agenda de um médico |
| **Triagem** | Processo do chatbot de coletar sintomas e classificar urgência |
| **Urgência** | Classificação clínica: BAIXA, MEDIA, ALTA, EMERGENCIA |
| **EMERGENCIA** | Situação que requer atendimento imediato — exibe SAMU 192, bloqueia agendamento |
| **Sessão de Chat** | Conversa completa do paciente com o bot (portal ou WhatsApp) |
| **Billing** | Rastreamento de tokens consumidos e custo em USD por chamada LLM |
| **RAG** | Recuperação de trechos de protocolos clínicos para contextualizar a triagem |
| **Evolution API** | Serviço de integração com WhatsApp Business |
| **Canal** | Origem do agendamento: PORTAL, WHATSAPP, INTERNO |

---

## Decisões Irreversíveis

1. **Dois frontends separados** — portal e admin são aplicações Angular distintas, não módulos de uma só
2. **OpenRouter** como gateway de modelos — não chamar providers diretamente
3. **PostgreSQL** como banco principal — não usar SQLite em nenhum ambiente
4. **Qdrant** para embeddings RAG — não usar pgvector ou Pinecone
5. **Evolution API** para WhatsApp — não usar Twilio WhatsApp diretamente
6. **Celery + Redis** para jobs — não usar FastAPI BackgroundTasks para jobs longos

---

> **Aprovado por:** Junior Payão — Abril 2026
> **Qualquer alteração neste arquivo exige aprovação explícita e novo commit documentado.**