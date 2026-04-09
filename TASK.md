# TASKS — MedBot Agendamentos Médicos

> Derivado de: PLAN.md | Validado contra: SPEC-MEDBOT.md
> Atualizar este arquivo a cada task concluída.
> Status: ⬜ Pendente | 🔄 Em progresso | ✅ Concluída | ❌ Bloqueada

---

## Progresso Geral

`[●●●●●●●●●●]` 95% — 124/129 tasks concluídas (G9 Deploy + T85 + T103-T104 + G16-G17 BACKLOG pendentes)


| Grupo                             | Tasks     | Concluídas  | Progresso       |
| --------------------------------- | --------- | ----------- | --------------- |
| G0 — Setup & Infra                | T01–T04   | 4/4         | `[●●●●●]` 100%  |
| G1 — Autenticação                 | T05–T07   | 3/3         | `[●●●●●]` 100%  |
| G2 — Agenda & Consultas           | T08–T13   | 6/6         | `[●●●●●]` 100%  |
| G3 — Chat IA                      | T14–T21   | 8/8         | `[●●●●●]` 100%  |
| G4 — RAG                          | T22–T24   | 3/3         | `[●●●●●]` 100%  |
| G5 — Billing Tokens               | T25–T29   | 5/5         | `[●●●●●]` 100%  |
| G6 — Notificações                 | T30–T33   | 4/4         | `[●●●●●]` 100%  |
| G7 — Frontend Portal              | T34–T39   | 6/6         | `[●●●●●]` 100%  |
| G8 — Frontend Admin               | T40–T46   | 7/7         | `[●●●●●]` 100%  |
| G9 — Deploy                       | T47–T50   | 0/4         | `[○○○○○]` 0%    |
| G10 — Refinamento Arquitetural IA | T51–T55   | 5/5         | `[●●●●●]` 100%  |
| G11 — Multi-tenancy               | T56–T63   | 8/8         | `[●●●●●]` 100%  |
| G12 — Licenciamento por Cliente   | T64–T74   | 11/11       | `[●●●●●]` 100%  |
| G13 — Revisão de Qualidade        | T75–T77   | 3/3         | `[●●●●●]` 100%  |
| G14 — Fluxo Guiado Agendamento    | T78–T85   | 7/8 (T85🔄) | `[●●●●○]` 87%   |
| G15 — Diferenciais de Mercado     | T86–T104  | 17/19       | `[●●●●○]` 89%   |
| G16 — N3 Enterprise               | T105–T107 | 0/3         | `[BACKLOG]`     |
| G17 — Plataforma BotFlow          | T108–T111 | 0/4         | `[BACKLOG]`     |
| G18 — Qualidade: Correções IA     | T112–T114 | 3/3         | `[●●●●●]` 100%  |
| G19 — Dashboard Gerencial v2      | T115–T119 | 5/5         | `[●●●●●]` 100%  |
| G20 — Agenda Gerencial            | T120–T123 | 4/4         | `[●●●●●]` 100%  |
| G21 — Multi-tenancy UX Fixes      | T124–T129 | 6/6         | `[●●●●●]` 100%  |
| G22 — ADMIN_GLOBAL Platform       | T130–T142 | 13/13       | `[●●●●●]` 100%  |
| G23 — Painel RECEPCIONISTA        | T143–T145 | 0/3         | `[BACKLOG]`     |
| G24 — Painel MÉDICO               | T146–T148 | 0/3         | `[BACKLOG]`     |


---

## GRUPO 0 — Setup & Infra `[●●●●●]` 100% ✅

### ✅ T01: Scaffold FastAPI + pyproject.toml

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/core/{config,database,redis,logging}.py`, `backend/.env.example`, `backend/docker-compose.yml`, `backend/Dockerfile`

### ✅ T02: Docker Compose local + Alembic

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`

### ✅ T03: Models SQLAlchemy 2.0 + migration inicial

- **Concluída:** Abril 2026
- **Arquivos gerados:** 8 models em `backend/app/models/` (base, especialidade, medico, paciente, slot, consulta, sessao_chat, token_usage, usuario)
- **Migration:** `alembic/versions/89102304387e_initial_schema.py`

### ✅ T04: Config, Security e Fixtures de Teste

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/core/security.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`
- **Testes:** 2 passando

---

## GRUPO 1 — Autenticação `[●●●●●]` 100% ✅

### ✅ T05: Auth SMS — Paciente Externo

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/schemas/auth.py`, `backend/app/services/auth_service.py`, `backend/app/api/v1/endpoints/auth.py`
- **Testes:** 8 unit (rate limit, código expirado, código incorreto, CPF mascarado em logs)
- **ADR:** bcrypt direto em vez de passlib (incompatibilidade bcrypt>=5.0)

### ✅ T06: Auth Interna JWT — Usuários do Painel

- **Concluída:** Abril 2026
- **Arquivos:** Integrado em `auth_service.py` (login_interno, renovar_token)
- **Testes:** 6 unit (login sucesso, email inexistente, senha incorreta, medico_id no token, refresh, access rejeitado como refresh)

### ✅ T07: Middleware + Guards RBAC

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/api/v1/dependencies.py` (get_current_user, require_role)
- **Testes:** 7 unit + 9 integration (RBAC por role, token invalido, refresh rejeitado como access)

---

## GRUPO 2 — Agenda e Consultas `[●●●●●]` 100% ✅

### ✅ T08: CRUD Especialidades

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/schemas/especialidade.py`, `backend/app/services/especialidade_service.py`, `backend/app/api/v1/endpoints/especialidades.py`
- **Testes:** 6 unit (criar, listar, buscar, atualizar, atualizar inexistente, desativar)

### ✅ T09: CRUD Médicos + Geração de Slots

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/schemas/medico.py`, `backend/app/services/medico_service.py`, `backend/app/api/v1/endpoints/medicos.py`
- **Testes:** 5 unit (criar, gerar slots sem almoco, com almoco, pular fds, medico inexistente)

### ✅ T10: CRUD Pacientes

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/schemas/paciente.py`, `backend/app/services/paciente_service.py`, `backend/app/api/v1/endpoints/pacientes.py`
- **Testes:** 5 unit (criar, buscar CPF, desativar, CPF nao exposto em log, CPF mascarado no response)

### ✅ T11: Serviço de Disponibilidade de Agenda

- **Concluída:** Abril 2026
- **Arquivos:** Integrado em `backend/app/services/agenda_service.py` + `backend/app/api/v1/endpoints/agenda.py`
- **Testes:** 1 unit (buscar_disponibilidade retorna lista filtrada)

### ✅ T12: Criação e Cancelamento de Consultas

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/schemas/consulta.py`, integrado em agenda_service.py
- **Testes:** 7 unit (agendar sucesso, slot inexistente, slot ocupado, cancelar libera slot, cancelar inexistente, ja cancelada, ja realizada)

### ✅ T13: Job Celery — Cleanup de Slots Expirados

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/workers/celery_app.py`, `backend/app/workers/slot_cleanup.py`
- **Beat schedule:** A cada 5 minutos, libera slots AGENDADOS sem confirmacao por >10min

---

## GRUPO 3 — Chat IA `[●●○○○]` 50%

### ✅ T14: LangChain + OpenRouter Base

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/chat_service.py`, `backend/app/services/ia/__init__.py`
- **Testes:** 5 unit (criar sessao, dados iniciais, sessao expirada, historico preservado, encerrar sessao)
- **Fix:** `_URGENCIA_ORDEM` map para comparacao correta de ConsultaUrgencia (str enum)

### ✅ T15: Roteador de Modelos por Feature

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/router.py`
- **Testes:** 8 unit (saudacao→llama, coleta→llama, triagem→biomistral, rag→gemini, complexo→claude, agendamento→llama, desconhecida→default, api key vazia)
- **Atualização (Abril 2026):** Em ambiente Ollama local, `triagem_clinica` e `rag_protocolo` passaram a priorizar `cniongolo/biomistral:latest` (ADR-010). Features de menor complexidade seguem em `llama3.1:8b`.
- **Atualização (Abril 2026):** Startup da API agora valida automaticamente disponibilidade dos modelos Ollama configurados e gera alerta em log quando houver modelo ausente (`app.main.validar_modelos_ollama`).

### ✅ T16: Memória de Sessão Redis (TTL 30min)

- **Concluída:** Abril 2026
- **Arquivos:** Integrado em `chat_service.py` (criar_sessao, processar_mensagem, encerrar_sessao)
- **Testes:** Cobertos em test_chat_service.py (TTL 30min verificado, sessao expirada retorna aviso)

### ✅ T17: Triagem + Classificação de Urgência

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/triagem.py`
- **Testes:** 15 unit (7 emergencia, case insensitive, sintomas normais, classif baixa/media/alta, febre alta, intensidade, duracao)

### ✅ T18: Sugestão de Especialidade + Apresentação de Slots

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/sugestao.py`
- **Testes:** 11 unit (8 sugestao sintoma→especialidade, 3 busca slots max 3/vazio/filtro)

### ✅ T19: Confirmação de Agendamento pelo Chat

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/confirmacao.py`
- **Testes:** 5 unit (sucesso, slot indisponivel, slot inexistente, encerra sessao, salva triagem)

### ✅ T20: WebSocket Endpoint

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/api/v1/endpoints/chat.py` (WS + REST sessao)
- **Testes:** 3 integration (conexao+mensagem, sessao expirada, criar sessao REST)
- **Endpoints:** `WS /v1/chat/ws/{token}`, `POST /v1/chat/sessao`, `POST /v1/chat/encerrar`

### ✅ T21: Webhook WhatsApp (Evolution API)

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/whatsapp_service.py`, webhook em `chat.py`
- **Testes:** 6 unit (extrair texto, extendedText, fromMe ignorado, evento nao-mensagem, telefone limpo, enviar mensagem)
- **Endpoint:** `POST /v1/chat/webhook/whatsapp`

---

## GRUPO 4 — RAG `[●●●●●]` 100% ✅

### ✅ T22: Qdrant Client + Collection de Protocolos

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/rag.py`
- **Testes:** 7 unit (get_client, collection name, vector size, criar/nao recriar collection, health ok/falha)
- **Config:** VECTOR_SIZE=1536 (text-embedding-3-small), Distance.COSINE

### ✅ T23: Ingestão de PDFs

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/api/v1/endpoints/rag.py`
- **Testes:** 8 unit (chunk simples/longo/overlap/vazio/None, indexar cria pontos/vazio/payload)
- **Endpoint:** `POST /v1/rag/documentos` (ADMIN), `GET /v1/rag/health`

### ✅ T24: Retrieval no Fluxo de Triagem

- **Concluída:** Abril 2026
- **Arquivos:** `buscar_contexto()` em `rag.py`
- **Testes:** 5 unit (chunks relevantes, sem resultados, top_k, score_threshold, documento_id)

---

## GRUPO 5 — Billing Tokens `[●●●●●]` 100% ✅

### ✅ T25: Middleware de Captura de Tokens

- **Concluída:** Abril 2026 (implementado junto com G3/T14)
- **Arquivos:** `backend/app/services/ia/billing.py` (registrar_uso)
- **Testes:** Cobertos em `test_billing.py` (registrar_uso_persiste_no_banco, feature_invalida_usa_geral)

### ✅ T26: Cálculo de Custo por Modelo

- **Concluída:** Abril 2026 (implementado junto com G3/T14)
- **Arquivos:** `backend/app/services/ia/billing.py` (calcular_custo)
- **Testes:** Cobertos em `test_billing.py` (custo llama, biomistral, claude, modelo desconhecido)

### ✅ T27: Endpoints Dashboard Billing

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/api/v1/endpoints/billing.py`
- **Testes:** 4 unit (resumo diario/sem uso, por modelo, por feature)
- **Endpoints:** `GET /v1/billing/dashboard` (ADMIN), `GET /v1/billing/export` (ADMIN)

### ✅ T28: Job Celery — Alertas de Custo

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/workers/billing_alert.py`
- **Testes:** 6 unit (abaixo 80%, em 80%, em 100%, acima 100%, entre 80-100%, limite zero)
- **Beat schedule:** A cada 10 minutos, verifica limites de custo

### ✅ T29: Exportação CSV

- **Concluída:** Abril 2026
- **Arquivos:** Integrado em `billing.py` endpoint (StreamingResponse CSV)
- **Testes:** 3 unit (sem filtro, com datas, lista vazia)
- **Endpoint:** `GET /v1/billing/export?inicio=&fim=` → CSV download

---

## GRUPO 6 — Notificações `[●●●●●]` 100% ✅

### ✅ T30: Serviço WhatsApp (Evolution API)

- **Concluída:** Abril 2026
- **Arquivos:** `backend/app/services/whatsapp_service.py` (templates adicionados)
- **Testes:** 4 unit (template confirmacao, lembrete, cancelamento, sem link opcional)

### ✅ T31: Serviço de E-mail (SendGrid)

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/notificacao_service.py`
- **Testes:** 4 unit (template email confirmacao, lembrete, enviar sucesso, enviar falha)
- **Decisão:** httpx direto para SendGrid API (sem SDK extra)

### ✅ T32: Jobs Celery — Lembretes D-1 e H-2

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/workers/lembretes.py`
- **Testes:** 4 unit (buscar D-1, buscar H-2, enviar ambos canais, falha WA nao impede email)
- **Beat schedule:** D-1 a cada 1h, H-2 a cada 30min

### ✅ T33: Link Tokenizado de Confirmação/Cancelamento

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/link_tokenizado.py`, `backend/app/api/v1/endpoints/acoes.py`
- **Testes:** 7 unit (criar confirmar/cancelar, validar correto/cancelar, expirado, invalido, vazio)
- **Endpoint:** `GET /v1/acoes/{token}` (público) — 410 se expirado

---

## GRUPO 7 — Frontend Portal `[●●●●●]` 100% ✅

### ✅ T34: Scaffold Angular 21 — Portal

- **Depende de:** T07
- **Arquivos:** `frontend-portal/` (completo — padrão Automaxia)
- **Ação:** Criar
- **TDAD:** Vitest configurado — `ng test` passa com spec base
- **Verificação:** `ng serve` roda em localhost:4200 | `ng build` sem erros | nenhum @NgModule

### ✅ T35: Login CPF + SMS

- **Depende de:** T34, T05
- **Arquivos:** `frontend-portal/src/app/features/auth/`
- **Ação:** Criar
- **TDAD:** `frontend-portal/src/app/features/auth/auth.component.spec.ts` (RED primeiro)
- **Verificação:** Usuário digita CPF → código SMS → token JWT armazenado

### ✅ T36: Chat UI WebSocket

- **Depende de:** T34, T20
- **Arquivos:** `frontend-portal/src/app/features/chat/`
- **Ação:** Criar
- **TDAD:** `frontend-portal/src/app/features/chat/chat.component.spec.ts` (RED primeiro)
- **Verificação:** Mensagem enviada → resposta do bot aparece | indicador "digitando..." durante processamento

### ✅ T37: Confirmação de Agendamento

- **Depende de:** T36
- **Arquivos:** `frontend-portal/src/app/features/chat/` (expandir)
- **Ação:** Editar
- **TDAD:** spec de confirmação (RED primeiro)
- **Verificação:** Slot selecionado no chat → card de confirmação com data/hora/médico

### ✅ T38: Meus Agendamentos

- **Depende de:** T34, T12
- **Arquivos:** `frontend-portal/src/app/features/agendamentos/`
- **Ação:** Criar
- **TDAD:** spec da lista de agendamentos (RED primeiro)
- **Verificação:** Lista de consultas do paciente | status visual por consulta | opção cancelar

### ✅ T39: PWA Config

- **Depende de:** T34
- **Arquivos:** `frontend-portal/ngsw-config.json`, `frontend-portal/src/manifest.webmanifest`
- **Ação:** Criar
- **TDAD:** Não se aplica — verificação manual
- **Verificação:** App instalável no Android/iPhone | funciona offline com dados em cache

---

## GRUPO 8 — Frontend Admin `[●●●●●]` 100% ✅

### ✅ T40: Scaffold Angular 21 — Admin

- **Concluída:** Abril 2026
- **Arquivos gerados:** `frontend-admin/` — scaffold completo padrão Automaxia
  - `app.config.ts`, `app.routes.ts`, `app.ts`
  - `core/guards/auth.guard.ts`
  - `core/services/` — `api.service.ts`, `auth-admin.service.ts`, `auth.interceptor.ts`, `agenda-admin.service.ts`, `dashboard.service.ts`
  - `features/auth/login.component.*` — login com email+senha
  - `features/agenda/agenda.component.*` — estrutura do calendário
  - `features/dashboard/dashboard.component.*` — estrutura do dashboard KPIs
  - `shared/shell/shell.component.*` — sidebar com navegação
  - `environments/`, `vite.config.ts`, `tsconfig*.json`, `angular.json`

### ✅ T41: Dashboard KPIs

- **Depende de:** T40, T27
- **Arquivos:** `frontend-admin/src/app/features/dashboard/`
- **Ação:** Criar
- **TDAD:** spec do dashboard (RED primeiro)
- **Verificação:** KPIs do dia | custo IA atual vs limite | gráfico de uso por modelo (Chart.js)

### ✅ T42: Calendário de Agenda

- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/agenda/agenda.component.*`
- **Verificação:** Visão por dia com navegação anterior/próximo | filtro por médico | slots agrupados por hora | click abre modal

### ✅ T43: Modal de Detalhe + Triagem IA

- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/agenda/agenda-modal.component.*`
- **Verificação:** Modal com dados do paciente, status, urgência, resumo da triagem IA, canal de origem

### ✅ T44: CRUD Médicos e Especialidades

- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/medicos/medicos.component.*`, `medicos.service.ts`
- **Verificação:** Listagem de médicos com tabela | modal de criação/edição | desativar médico | especialidades carregadas da API

### ✅ T45: Dashboard Billing

- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/billing/billing.component.*`, `billing.service.ts`
- **Verificação:** Gráfico de barras por modelo (custo + chamadas) | gráfico doughnut por feature | tabela detalhada | barra de progresso do limite | export CSV

### ✅ T46: Config de Limites de Custo

- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/billing/billing-config.component.*`
- **Backend:** `PATCH /v1/billing/config` + `GET /v1/billing/config` adicionados em `endpoints/billing.py`
- **Verificação:** ADMIN altera limite diário/mensal/threshold → salvo via API | confirmação visual

---

## GRUPO 9 — Deploy `[○○○○○]` 0%

> Estratégia em 3 fases — ver ADR-007 em docs/decisoes-tecnicas.md

### T47: Dockerfiles backend e frontends

- **Depende de:** T46
- **Arquivos:** `backend/Dockerfile`, `frontend-portal/Dockerfile`, `frontend-admin/Dockerfile`, `infra/nginx/default.conf`
- **Ação:** Criar
- **TDAD:** Verificação via docker build
- **Verificação:** docker build sem erros | nginx com SPA fallback

### T48: railway.toml — Fase 1 Demo

- **Depende de:** T47
- **Arquivos:** `railway.toml`, `.env.railway.example`
- **Ação:** Criar
- **TDAD:** Verificação via Railway dashboard
- **Verificação:** railway up sobe tudo | GET /health ok | frontends acessíveis

### T49: vercel.json — Frontends

- **Depende de:** T47
- **Arquivos:** `frontend-portal/vercel.json`, `frontend-admin/vercel.json`
- **Ação:** Criar
- **TDAD:** Não se aplica
- **Verificação:** vercel deploy ok | SPA routing funciona

### T50: Infra Fase 2 — Hostinger KVM 4 + CapRover
- **Depende de:** T47
- **Arquivos:** `infra/hostinger/captain-definition`, `infra/hostinger/docker-compose.prod.yml`, `infra/hostinger/evolution-api-compose.yml`, `infra/hostinger/setup.sh`
- **Ação:** Criar arquivos + executar setup no VPS
- **Setup no VPS (via terminal Hostinger hPanel):**
  1. Instalar Docker: `curl -fsSL https://get.docker.com | sh`
  2. Instalar CapRover: `docker run -p 80:80 -p 443:443 -p 3000:3000 -v /var/run/docker.sock:/var/run/docker.sock caprover/caprover`
  3. Acessar `http://[IP_VPS]:3000` → configurar domínio + senha
  4. Deploy cada app via CapRover dashboard ou CLI
  5. Evolution API: novo app → docker-compose → scan QR Code WhatsApp
- **TDAD:** Não se aplica — verificação via CapRover dashboard
- **Verificação:**
  CapRover rodando em [IP_VPS]:3000 ✅
  HTTPS automático via Let's Encrypt ✅
  Backend: `GET https://api.medbot.[dominio]/health` → `{"status":"ok"}` ✅
  Portal: `https://portal.medbot.[dominio]` carrega ✅
  Admin: `https://admin.medbot.[dominio]` carrega ✅
  Evolution API conectada: WhatsApp "Conectado" no painel ✅
  PostgreSQL e Redis acessíveis internamente pelo backend ✅

---

---

## GRUPO 10 — Refinamento Arquitetural IA `[●●●●●]` 100% ✅

> Lacunas identificadas na análise do `docs/medbot_arquitetura.md` em Abril 2026.
> Não bloqueiam G8/G9 — podem ser implementadas em paralelo ou após o MVP.
> Ver ADR-011 a ADR-013 em `docs/decisoes-tecnicas.md` para contexto.

### ✅ T51: Classificador de Intenção Separado

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/intent_classifier.py`
- **Testes:** 15 unit — saude/agendamento/geral por keyword, case-insensitive, confianca 0.0-1.0
- **Abordagem:** Contagem de matches de palavras-chave por categoria, sem chamada LLM (zero latência/custo)

### ✅ T52: Máquina de Estados Explícita no Chat

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/state_machine.py`
- **Testes:** 18 unit — transições válidas/inválidas, fluxo completo, `InvalidTransitionError`
- **Estados:** `ChatEstado` StrEnum com 9 estados | `_VALID_TRANSITIONS` define grafo permitido | `avancar_estado()` valida antes de transitar

### ✅ T53: Prompts Estruturados por Modelo + Parâmetros de Temperatura

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/prompts.py`
- **Arquivos editados:** `backend/app/services/ia/chat_service.py` (usa `obter_prompt_sistema()` e `obter_params_llm()`)
- **Testes:** 19 unit — prompts distintos por feature, temperatura correta por modelo, whitelist
- **Parâmetros:** LLaMA `temp=0.6` | BioMistral `temp=0.2 + top_p=0.9 + repeat_penalty=1.1`

### ✅ T54: Validações de Robustez do Fluxo LLM

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/services/ia/robustez.py`
- **Testes:** 17 unit — extrair_json_llm (retry trigger), validar_especialidade (whitelist), verificar_limite_perguntas (máx 3), FALLBACK_MESSAGE
- **Funções:** `extrair_json_llm()` com regex fallback | `validar_especialidade()` case-insensitive | `verificar_limite_perguntas()` | `FALLBACK_MESSAGE` para erros LLM

### ✅ T55: Camada de Orquestração do ChatService

- **Concluída:** Abril 2026
- **Arquivos editados:** `backend/app/services/ia/chat_service.py`
- **Testes gerados:** `backend/tests/unit/test_chat_orquestracao.py` (14 unit)
- **Testes atualizados:** `backend/tests/unit/test_chat_service.py` (campo `etapa` → `estado`)
- **Resultado:** 240 testes passando, zero regressões
- **O que foi conectado:**
  - `detectar_emergencia()` chamado **antes** do LLM em cada mensagem (Regra de Ouro)
  - `ChatEstado` substitui campo livre `etapa` → estado persistido com FSM válida
  - `_ESTADO_FEATURE` mapeia estado → feature key → modelo correto (BioMistral ativado em TRIAGEM)
  - JSON estruturado do BioMistral extraído via `extrair_json_llm()` com fallback
  - Especialidade validada via `validar_especialidade()` contra whitelist
  - Contador `perguntas_coleta` incrementado em COLETANDO_SINTOMAS
  - Avanço automático START→COLETANDO→TRIAGEM→SUGESTAO baseado em lógica de estado
  - `dados_coletados` agora tem campos estruturados: `sintomas`, `especialidade`, `medico`, `horario`

---

---

## GRUPO 11 — Multi-tenancy `[●●●●●●●●]` 100%

### ✅ T56: ADR-015 + Registrar grupo G11 nos artefatos SDD

- **Arquivos:** `docs/decisoes-tecnicas.md`, `TASK.md`, `CLAUDE.md`

### ✅ T57: Model EstabelecimentoSaude + schema + migration Alembic

- **Arquivos a gerar:** `backend/app/models/estabelecimento.py`, `backend/app/schemas/estabelecimento.py`, `backend/tests/unit/test_estabelecimento.py`, nova migration Alembic
- **Campos:** `id`, `nome`, `cnpj` (único), `slug`, `tipo` (enum TipoEstabelecimento), `ativo`, `plano`, `created_at`
- **TipoEstabelecimento:** HOSPITAL | CLINICA | UBS | LABORATORIO | POSTO_SAUDE | OUTRO

### ✅ T58: Ampliar UsuarioRole + campo estabelecimento_id em Usuario

- **Arquivos:** `backend/app/models/usuario.py`, migration Alembic
- **Novos roles:** `ADMIN_GLOBAL` (acessa todos), `ADMIN_ESTABELECIMENTO` (limitado a 1)
- **ADMIN antigo** renomeado para `ADMIN_ESTABELECIMENTO` (breaking change documentado)

### ✅ T59: Adicionar estabelecimento_id nas 6 tabelas de domínio

- **Tabelas:** `especialidades`, `medicos`, `pacientes`, `slots`, `consultas`, `sessoes_chat`
- **Migration:** retrocompatível — DEFAULT 1, depois NOT NULL

### ✅ T60: estabelecimento_id no JWT + dependency get_estabelecimento_id

- **Arquivos:** `backend/app/services/auth_service.py`, `backend/app/api/v1/dependencies.py`
- **JWT payload:** inclui `estabelecimento_id` (null para ADMIN_GLOBAL)

### ✅ T61: Filtro por estabelecimento_id nos endpoints de domínio

- **Arquivos:** `backend/app/services/especialidade_service.py`, `medico_service.py`, `paciente_service.py`, `agenda_service.py`
- **Padrão:** `select(Model).where(Model.estabelecimento_id == estabelecimento_id)`

### ✅ T62: CRUD /v1/estabelecimentos/ + endpoint selecionar-estabelecimento

- **Arquivos a gerar:** `backend/app/models/estabelecimento.py` (já em T57), `backend/app/services/estabelecimento_service.py`, `backend/app/api/v1/endpoints/estabelecimentos.py`
- **Endpoints:** GET / | POST / | PATCH /{id} | POST /admin/selecionar-estabelecimento

### ✅ T63: Seed atualizado com 2 estabelecimentos

- **Arquivo:** `backend/scripts/seed.py`
- **Dados:** 1 Hospital São Lucas + 1 Clínica Vida (médicos e pacientes distribuídos)

---

## GRUPO 12 — Licenciamento por Cliente `[●●●●●]` 100% ✅

> Sistema de licenciamento que controla ciclo de vida (TRIAL → ATIVA → EXPIRADA | SUSPENSA),
> quotas por plano e gestão manual pelo ADMIN_GLOBAL. Ver ADR-016 a ADR-018.

### ✅ T64: Campos contato + responsável legal em EstabelecimentoSaude

- **Concluída:** Abril 2026
- **Arquivos editados:** `backend/app/models/estabelecimento.py`, `backend/app/schemas/estabelecimento.py`
- **Migration:** `backend/alembic/versions/7d076b3ea7af_add_contato_responsavel_estabelecimento.py`
- **Campos:** email, telefone, endereço, cidade, estado, CEP + responsavel_{nome, cpf, email, telefone, cargo}

### ✅ T65: Model Licenca + relationship em EstabelecimentoSaude + `__init__.py`

- **Concluída:** Abril 2026
- **Arquivos gerados:** `backend/app/models/licenca.py`
- **Arquivos editados:** `backend/app/models/estabelecimento.py` (relationship), `backend/app/models/__init__.py`
- **Status enum:** TRIAL | ATIVA | EXPIRADA | SUSPENSA

### ✅ T66: PLANO_QUOTAS e TRIAL_DIAS em `config.py`

- **Concluída:** Abril 2026
- **Arquivo:** `backend/app/core/config.py`
- **Quotas:** basico (1 médico, 100 consultas/mês), pro (10, 1000), enterprise (ilimitado)

### ✅ T67: Migration Alembic `add_licencas` + backfill

- **Concluída:** Abril 2026
- **Migration:** `backend/alembic/versions/0facc6b9e1eb_add_licencas.py`
- **Backfill:** TRIAL criado para cada estabelecimento existente com `trial_expira_em = created_at + 14d`

### ✅ T68: Schemas Pydantic v2 (`licenca.py`)

- **Concluída:** Abril 2026
- **Arquivo gerado:** `backend/app/schemas/licenca.py`
- **Schemas:** `LicencaResponse` (com `dias_restantes` calculado + `PlanoQuotaInfo`), `AdminLicencaUpdate`

### ✅ T69: `LicencaService` completo

- **Concluída:** Abril 2026
- **Arquivo gerado:** `backend/app/services/licenca_service.py`
- **Métodos:** ativar_trial, buscar_por_estabelecimento, verificar_validade, calcular_dias_restantes, ativar_plano, suspender, reativar, verificar_quota_medicos, verificar_quota_consultas_mes, contar_medicos_ativos, contar_consultas_mes
- **Exceptions:** LicencaNaoEncontradaError, QuotaMedicosExcedidaError, QuotaConsultasExcedidaError

### ✅ T70: Editar `EstabelecimentoService.criar()` para chamar `ativar_trial`

- **Concluída:** Abril 2026
- **Arquivo:** `backend/app/services/estabelecimento_service.py`
- **Comportamento:** Trial criado automaticamente na mesma transação ao criar estabelecimento

### ✅ T71: Dependencies `verificar_licenca_ativa` + `require_quota_medico` + `require_quota_consulta`

- **Concluída:** Abril 2026
- **Arquivo:** `backend/app/api/v1/dependencies.py`
- **HTTP 402:** TRIAL expirado ou EXPIRADA | **HTTP 403:** SUSPENSA

### ✅ T72: Editar `router.py` — injetar `LICENCA_DEP` nos routers de domínio

- **Concluída:** Abril 2026
- **Arquivo:** `backend/app/api/v1/router.py`
- **Com licença:** especialidades, médicos, pacientes, agenda, chat
- **Sem licença:** auth, estabelecimentos, licença, ações, billing, rag

### ✅ T73: Endpoints `GET /v1/licenca/minha` e `PATCH /v1/admin/licenca/{id}`

- **Concluída:** Abril 2026
- **Arquivo gerado:** `backend/app/api/v1/endpoints/licenca.py`
- **GET:** retorna status, dias restantes e quota (acessível mesmo expirado)
- **PATCH:** ADMIN_GLOBAL ativa, renova, suspende ou reativa qualquer licença

### ✅ T74: Testes unitários LicencaService + atualizar TASK.md e CLAUDE.md

- **Concluída:** Abril 2026
- **Arquivo gerado:** `backend/tests/unit/test_licenca_service.py`
- **Testes:** 22 unit — ativar_trial, verificar_validade (6 cenários), dias_restantes, suspender, reativar (3 cenários), quotas médicos/consultas (enterprise ilimitado)

---

## GRUPO 13 — Revisão de Qualidade `/simplify` `[●●●]` 100%

### ✅ T75: /simplify frontend-portal
- **Depende de:** T34–T39
- **Arquivos:** todos os `.ts` e `.scss` em `frontend-portal/src/`
- **Ação:** Executar /simplify + corrigir issues
- **Verificação:** `ng build` sem erros | zero `console.log()` | zero `any` implícito

### ✅ T76: /simplify frontend-admin
- **Depende de:** T40–T46
- **Arquivos:** todos os `.ts` e `.scss` em `frontend-admin/src/`
- **Ação:** Executar /simplify + corrigir issues
- **Verificação:** `ng build` sem erros | zero `console.log()` | zero `any` implícito

### ✅ T77: Validação final pós-simplify
- **Depende de:** T75, T76
- **Ação:** Rodar `ng build` nos dois projetos e confirmar zero erros
- **Verificação:** `ng build frontend-portal` ✅ | `ng build frontend-admin` ✅

---

## GRUPO 14 — Fluxo Guiado de Agendamento `[●●●●●●●○]` 87% 🔄

### ✅ T78: Model Convenio + migration + seed
- **Depende de:** T57 (EstabelecimentoSaude)
- **Arquivos:** `backend/app/models/convenio.py`, `backend/app/schemas/convenio.py`, migration Alembic, `backend/scripts/seed.py`
- **Campos:** id, nome, ativo, estabelecimento_id (FK)
- **Seed:** Unimed, Bradesco Saúde, SulAmérica, Amil, Porto Seguro Saúde, Hapvida
- **TDAD:** `tests/unit/test_convenio_model.py` (RED primeiro)
- **Verificação:** migration roda | seed cria convênios | filtro por estabelecimento funciona

### ✅ T79: Endpoint GET /v1/convenios
- **Depende de:** T78
- **Arquivos:** `backend/app/api/v1/endpoints/convenios.py`, `backend/app/services/convenio_service.py`
- **Endpoint:** `GET /v1/convenios` → lista ativos do estabelecimento
- **TDAD:** `tests/unit/test_convenio_service.py` (RED primeiro)
- **Verificação:** retorna lista filtrada por estabelecimento_id | retorna lista vazia sem erro

### ✅ T80: Campo convenio_id em Paciente + migration
- **Depende de:** T78
- **Arquivos:** `backend/app/models/paciente.py`, migration Alembic
- **Campos:** convenio_id (FK nullable), tipo_atendimento ENUM(CONVENIO, PARTICULAR)
- **TDAD:** `tests/unit/test_paciente_convenio.py` (RED primeiro)
- **Verificação:** paciente pode ter convenio_id null | migration retrocompatível

### ✅ T81: Filtro por convênio em /v1/agenda/disponivel
- **Depende de:** T79, T80
- **Arquivos:** `backend/app/services/agenda_service.py`
- **Lógica:** quando convenio_id informado, retornar apenas slots de médicos que atendem aquele convênio
- **TDAD:** `tests/unit/test_agenda_convenio.py` (RED primeiro)
- **Verificação:** slot de médico sem convênio não aparece | particular sempre aparece

### ✅ T82: Novos estados FSM do chat
- **Depende de:** T52 (state_machine.py)
- **Arquivos:** `backend/app/services/ia/state_machine.py`
- **Novos estados:** COLETANDO_NOME → COLETANDO_CONVENIO → OUVINDO_SINTOMAS → SUGERINDO_ESPECIALIDADE → APRESENTANDO_SLOTS → COLETANDO_CONTATO → CONFIRMANDO
- **TDAD:** `tests/unit/test_state_machine_fluxo.py` (RED primeiro)
- **Verificação:** transições válidas | InvalidTransitionError nas inválidas | fluxo completo de ponta a ponta

### ✅ T83: Prompts e lógica de coleta de dados no chat_service
- **Depende de:** T82
- **Arquivos:** `backend/app/services/ia/chat_service.py`, `backend/app/services/ia/prompts.py`
- **Regras:** uma pergunta por mensagem | sem asteriscos | sem diagnóstico | EMERGENCY → SAMU 192
- **TDAD:** `tests/unit/test_chat_fluxo_guiado.py` (RED primeiro)
- **Verificação:** fluxo completo sem pular etapas | dados incompletos bloqueiam confirmação | timeout libera slot

### ✅ T84: Estado RESERVADO no slot com timeout
- **Depende de:** T83
- **Arquivos:** `backend/app/models/slot.py`, `backend/app/workers/slot_cleanup.py`, migration Alembic
- **Lógica:** SlotStatus adiciona RESERVADO. Job Celery libera slots RESERVADO com mais de 10min.
- **TDAD:** `tests/unit/test_slot_reservado.py` (RED primeiro)
- **Verificação:** slot vai RESERVADO ao escolher | volta DISPONIVEL após 10min | vai AGENDADO após confirmação

### 🔄 T85: Fluxo guiado completo — backend + frontend (reaberta)
- **Depende de:** T83, T84
- **ADR:** ADR-035, ADR-036, ADR-037
- **Status:** Reaberta — critério "fluxo completo nome→confirmação" não estava atendido

#### T85.1 ✅ — Backend: estados COLETANDO_CONTATO + CONFIRMANDO
- **Arquivos:** `backend/app/services/ia/chat_service.py`
- **Implementado:** `_processar_slot_selecionado`, `_processar_coleta_contato`, `_processar_criar_agendamento`
- **TDAD pendente:** `tests/unit/test_chat_fluxo_booking.py` — testes RED não escritos antes do código (violação registrada em ADR-037)
- **Verificação:** ao clicar no card, bot pede telefone → email → resumo → "Sim" → `Consulta` criada no banco

#### T85.2 ✅ — Backend: especialidades dinâmicas do banco
- **Arquivos:** `backend/app/services/ia/chat_service.py`, `backend/app/services/ia/prompts.py`
- **Implementado:** `criar_sessao()` carrega especialidades do DB; `obter_prompt_conversa(especialidades)` gera prompt dinâmico; `_extrair_especialidade_do_texto()` usa lista da sessão
- **ADR:** ADR-035
- **TDAD pendente:** `tests/unit/test_prompt_dinamico.py`
- **Verificação:** clínica com 4 especialidades → prompt lista apenas as 4; LLM não menciona especialidades fora da lista

#### T85.3 ✅ — Backend: `POST /v1/chat/sessao` autenticação opcional
- **Arquivos:** `backend/app/api/v1/endpoints/chat.py`, `backend/app/api/v1/dependencies.py`
- **Implementado:** `get_estabelecimento_id_chat` (HTTPBearer auto_error=False); `estabelecimento_id` aceito no body como fallback
- **ADR:** ver ADR-030
- **Verificação:** portal anônimo com `estabelecimento_id: 1` no body → sessão criada sem JWT

#### T85.4 ✅ — Frontend: reconexão + cards desabilitados quando desconectado
- **Arquivos:** `frontend-portal/src/app/features/chat/chat.component.*`
- **Implementado:** cards desabilitados com `!chat.conectado()`; botão "Reconectar"; método `reconectar()`
- **Verificação:** backend offline → cards acinzentados + botão reconectar visível

#### T85.5 ✅ — Testes TDAD retroativos
- **Arquivos a criar:** `backend/tests/unit/test_chat_fluxo_booking.py`, `backend/tests/unit/test_prompt_dinamico.py`
- **Cobertura mínima:**
  - `test_slot_selecionado_pede_telefone` — confirmar:ID → estado COLETANDO_CONTATO + mensagem com "telefone"
  - `test_coleta_telefone_pede_email` — step telefone → armazena telefone, pede email
  - `test_coleta_email_mostra_resumo` — step email → estado CONFIRMANDO + resumo
  - `test_criar_agendamento_persiste_consulta` — "Sim" → Consulta no banco
  - `test_prompt_usa_especialidades_da_sessao` — especialidades da sessão aparecem no prompt
  - `test_especialidade_nao_disponivel_usa_fallback` — "nutricionista" → Clínica Geral
- **Verificação:** `uv run pytest tests/unit/test_chat_fluxo_booking.py -v` passa

---

## GRUPO 15 — Diferenciais de Mercado `[○○○○○○○○○○○○○○○○○○]` 0%

### N1 — Alto Impacto, Baixo Esforço

### ✅ T86: Histórico clínico — Model SessaoHistorico + migration
- **Depende de:** T22, T16
- **Arquivos:** `backend/app/models/sessao_historico.py`, migration Alembic
- **Campos:** id, paciente_id (FK), sessao_id (FK), sintomas_relatados (JSONB), especialidade_sugerida, urgencia, resumo_triagem (TEXT), created_at
- **TDAD:** `tests/unit/test_sessao_historico.py` (RED primeiro)
- **Verificação:** migration roda | campos persistem | filtro por paciente_id funciona

### ✅ T87: Histórico clínico — Persistir triagem ao confirmar
- **Depende de:** T86
- **Arquivos:** `backend/app/services/ia/confirmacao.py`, `backend/app/services/ia/chat_service.py`
- **Lógica:** ao confirmar agendamento, salvar automaticamente dados da triagem em SessaoHistorico antes de encerrar sessão
- **TDAD:** `tests/unit/test_historico_persistencia.py` (RED primeiro)
- **Verificação:** após confirmação, registro existe em SessaoHistorico | dados corretos (sintomas, urgência, resumo)

### ✅ T88: Histórico clínico — Injetar contexto nas novas sessões
- **Depende de:** T87
- **Arquivos:** `backend/app/services/ia/chat_service.py`, `backend/app/services/ia/prompts.py`
- **Lógica:** ao iniciar nova sessão com paciente identificado, buscar últimas 3 sessões de SessaoHistorico e injetar como contexto no SystemMessage
- **TDAD:** `tests/unit/test_historico_contexto.py` (RED primeiro)
- **Verificação:** bot usa histórico anterior | sem histórico → fluxo normal sem erro

### ✅ T89: Fila de espera — Model FilaEspera + migration
- **Depende de:** T78, T80
- **Arquivos:** `backend/app/models/fila_espera.py`, `backend/app/schemas/fila_espera.py`, migration Alembic
- **Campos:** id, paciente_id (FK), estabelecimento_id (FK), especialidade_id (FK nullable), convenio_id (FK nullable), status ENUM(AGUARDANDO, NOTIFICADO, AGENDADO, CANCELADO), notificado_em, created_at
- **TDAD:** `tests/unit/test_fila_espera_model.py` (RED primeiro)
- **Verificação:** migration roda | status transita corretamente

### ✅ T90: Fila de espera — Endpoint + service
- **Depende de:** T89
- **Arquivos:** `backend/app/services/fila_espera_service.py`, `backend/app/api/v1/endpoints/fila_espera.py`
- **Endpoints:** POST /v1/fila-espera | DELETE /v1/fila-espera/{id} | GET /v1/admin/fila-espera
- **Lógica no chat:** quando não há slots: oferecer entrada na fila com chips [Sim, entrar na lista] [Não, obrigado]
- **TDAD:** `tests/unit/test_fila_espera_service.py` (RED primeiro)
- **Verificação:** paciente entra na fila | admin vê fila | paciente sai da fila

### ✅ T91: Fila de espera — Job Celery monitora slots
- **Depende de:** T90
- **Arquivos:** `backend/app/workers/fila_espera.py`
- **Lógica:** a cada 5 min, verificar slots DISPONIVEL que atendam pacientes na fila (especialidade + convenio). Se encontrar → WhatsApp → slot RESERVADO por 30 min → se não responder → próximo da fila
- **TDAD:** `tests/unit/test_fila_espera_worker.py` (RED primeiro)
- **Verificação:** paciente recebe WhatsApp quando slot abre | slot fica RESERVADO | próximo notificado se timeout

### ✅ T92: Resumo de triagem — Gerar resumo estruturado
- **Depende de:** T87
- **Arquivos:** `backend/app/services/ia/resumo_triagem.py`
- **Lógica:** após consulta confirmada, gerar resumo com LLM (modelo econômico). Máx 200 palavras. Nunca usa termos de diagnóstico.
- **TDAD:** `tests/unit/test_resumo_triagem.py` (RED primeiro)
- **Verificação:** resumo gerado | sem diagnóstico | máx 200 palavras | dados corretos

### ✅ T93: Resumo de triagem — Enviar para o médico
- **Depende de:** T92
- **Arquivos:** `backend/app/workers/resumo_medico.py`
- **Lógica:** 30 min antes da consulta, job Celery envia ao médico (WhatsApp + email). Beat schedule a cada 15 min.
- **TDAD:** `tests/unit/test_resumo_worker.py` (RED primeiro)
- **Verificação:** médico recebe WhatsApp 30 min antes | email enviado | não reenvia se já enviou

---

### N2 — Alto Impacto, Médio Esforço

### ✅ T94: Relatórios — Endpoints de analytics
- **Depende de:** T27
- **Arquivos:** `backend/app/api/v1/endpoints/relatorios.py`, `backend/app/services/relatorio_service.py`
- **Endpoints (ADMIN):** GET /v1/relatorios/ocupacao | /confirmacao | /sintomas | /custo-por-agendamento | /fila-espera
- **TDAD:** `tests/unit/test_relatorio_service.py` (RED primeiro)
- **Verificação:** todos endpoints retornam dados agregados | filtro por período funciona | filtro por medico_id opcional

### ✅ T95: Relatórios — Dashboard frontend-admin
- **Depende de:** T94
- **Arquivos:** `frontend-admin/src/app/features/relatorios/`
- **Componentes:** KPI cards | gráfico de barras (Chart.js) | doughnut top sintomas | tabela médicos | date range picker
- **TDAD:** specs dos componentes (RED primeiro)
- **Verificação:** ng build sem erros | dados carregam | filtro de período atualiza gráficos

### ✅ T96: Reagendamento — Detectar cancelamento pelo médico/admin
- **Depende de:** T12
- **Arquivos:** `backend/app/services/consulta_service.py`, `backend/app/workers/reagendamento.py`
- **Novo campo:** Consulta.motivo_cancelamento ENUM(PACIENTE, MEDICO, ESTABELECIMENTO, SISTEMA)
- **Lógica:** disparar job Celery apenas para cancelamentos MEDICO ou ESTABELECIMENTO
- **TDAD:** `tests/unit/test_cancelamento_motivo.py` (RED primeiro)
- **Verificação:** motivo persiste | job disparado apenas para cancelamentos do lado do estabelecimento

### ✅ T97: Reagendamento — Buscar e oferecer novos slots
- **Depende de:** T96
- **Arquivos:** `backend/app/workers/reagendamento.py`
- **Lógica:** busca 3 slots disponíveis (mesma especialidade + convenio). WhatsApp com 3 opções numeradas. Timeout 30 min → notificar recepção.
- **TDAD:** `tests/unit/test_reagendamento_worker.py` (RED primeiro)
- **Verificação:** WhatsApp enviado com 3 opções | resposta "1" agenda slot 1 | timeout notifica recepção

### ✅ T98: Reagendamento — Webhook de resposta WhatsApp
- **Depende de:** T97, T21
- **Arquivos:** `backend/app/api/v1/endpoints/chat.py`, `backend/app/services/reagendamento_service.py`
- **Lógica:** webhook recebe "1"/"2"/"3" → identifica contexto via sessão Redis → agenda slot → confirma via WhatsApp
- **TDAD:** `tests/unit/test_reagendamento_webhook.py` (RED primeiro)
- **Verificação:** resposta "1" agenda slot 1 | resposta inválida → orientação | "0" → cancela e notifica recepção

### ✅ T99: Avaliação — Model Avaliacao + migration
- **Depende de:** T12
- **Arquivos:** `backend/app/models/avaliacao.py`, `backend/app/schemas/avaliacao.py`, migration Alembic
- **Campos:** id, consulta_id (FK unique), paciente_id (FK), medico_id (FK), nota INT (1-5), comentario TEXT nullable, canal ENUM(WHATSAPP, PORTAL), created_at
- **TDAD:** `tests/unit/test_avaliacao_model.py` (RED primeiro)
- **Verificação:** migration roda | nota entre 1-5 | uma avaliação por consulta (unique)

### ✅ T100: Avaliação — Job Celery dispara 24h após consulta
- **Depende de:** T99
- **Arquivos:** `backend/app/workers/avaliacao.py`
- **Lógica:** a cada hora, verificar consultas REALIZADA há 24h e sem avaliação. Enviar WhatsApp com opções 1-5. Timeout 48h.
- **TDAD:** `tests/unit/test_avaliacao_worker.py` (RED primeiro)
- **Verificação:** WhatsApp enviado 24h após REALIZADA | não envia se já avaliado | não envia se cancelada

### ✅ T101: Avaliação — Webhook de resposta + comentário opcional
- **Depende de:** T100, T21
- **Arquivos:** `backend/app/services/avaliacao_service.py`, expandir webhook em `chat.py`
- **Lógica:** resposta com nota → pedir comentário opcional → "pular" aceito → salvar → encerrar. Nota < 3 → notificar recepção via email.
- **TDAD:** `tests/unit/test_avaliacao_webhook.py` (RED primeiro)
- **Verificação:** nota salva | comentário opcional | nota baixa notifica recepção | "pular" encerra sem comentário

### ✅ T102: Avaliação — Endpoints e NPS no painel admin
- **Depende de:** T101
- **Arquivos:** `backend/app/api/v1/endpoints/avaliacoes.py`, `frontend-admin/src/app/features/relatorios/`
- **Endpoints:** GET /v1/admin/avaliacoes | GET /v1/admin/avaliacoes/nps
- **Frontend:** NPS score geral | ranking médicos | últimas avaliações com comentários | distribuição 1-5 estrelas
- **TDAD:** `tests/unit/test_avaliacao_endpoints.py` + specs frontend (RED primeiro)
- **Verificação:** NPS calculado corretamente | frontend exibe ranking

### T103: ✅ Abstração de provedor WhatsApp
- **Depende de:** T33, T21
- **Arquivos:** `backend/app/services/whatsapp/provider.py`, `backend/app/services/whatsapp/evolution.py`, `backend/app/services/whatsapp/uazapi.py`, `backend/app/core/config.py`
- **Lógica:** Protocolo `WhatsAppProvider` com adapters por provedor. `WHATSAPP_PROVIDER` no `.env` define qual usar em runtime. Encapsular Evolution API existente como `EvolutionProvider`. Adicionar `UazapiProvider` como alternativa gerenciada.
- **TDAD:** `tests/unit/test_whatsapp_provider.py` (RED primeiro)
- **Verificação:** trocar `WHATSAPP_PROVIDER=evolution` → `uazapi` sem mudar serviços de negócio | zero regressões

### T104: Testes E2E — integração dos diferenciais
- **Depende de:** T86–T103
- **Arquivos:** `backend/tests/integration/test_diferenciais.py`
- **Cenários:** (1) paciente retorna → bot reconhece histórico | (2) sem slot → fila → WhatsApp → agenda | (3) médico cancela → reagenda pelo WhatsApp | (4) avaliação 24h → painel admin | (5) admin vê relatórios NPS + ocupação | (6) troca de provedor WhatsApp sem impacto
- **TDAD:** RED primeiro para cada cenário
- **Verificação:** todos os cenários passam | zero regressões nos 373+ testes existentes

---

## Ordem de Execução G15

**Bloco N1 (menor esforço):**
T86 → T87 → T88 (histórico clínico)
T89 → T90 → T91 (fila de espera)
T92 → T93 (resumo para médico)

**Bloco N2 (médio esforço):**
T94 → T95 (relatórios)
T96 → T97 → T98 (reagendamento)
T99 → T100 → T101 → T102 (avaliação)

**Finalização G15:**
T103 (abstração WhatsApp) → T104 (E2E)

---

---

## GRUPO 18 — Qualidade: Correções IA `[●●●●●]` 100% ✅

### ✅ T112: Fix regressões — testes billing dashboard
- **Concluída:** Abril 2026
- **Arquivos:** `backend/tests/unit/test_billing_dashboard.py`
- **Fix:** `obter_resumo_por_feature` passou a retornar 4 colunas (adicionado `total_chamadas`). Mock atualizado de tuple 3 elementos para 4 elementos. Assertion `slots[0]["total_chamadas"] == 12` adicionada.
- **Verificação:** `uv run pytest tests/unit/test_billing_dashboard.py -q` → todos passando

### ✅ T113: Fix prompts IA — SAMU 192 e temperatura llama
- **Concluída:** Abril 2026
- **Arquivos:** `backend/app/services/ia/prompts.py`
- **Fix (segurança):** Instrução explícita de SAMU 192 adicionada ao system prompt para EMERGENCIA — bot não pode agendar, deve orientar ligar 192.
- **Fix (qualidade):** Temperatura `llama3.1:8b` aumentada de 0.3 → 0.6 (ADR-028) — respostas mais naturais em fluxos de saudação.
- **Verificação:** Testes de prompts passando; comportamento EMERGENCIA confirmado

### ✅ T114: Fix chat_service — detecção de saudação em COLETANDO_CONVENIO
- **Concluída:** Abril 2026
- **Arquivos:** `backend/app/services/ia/chat_service.py`
- **Fix:** No estado `COLETANDO_CONVENIO`, mensagens que são saudação (oi, olá, bom dia, etc.) ou com ≤ 2 caracteres não são mais aceitas como nome de convênio. Sistema repete a pergunta mantendo o estado.
- **Verificação:** Testes chat_service passando; saudação não avança o FSM

---

## GRUPO 19 — Dashboard Gerencial v2 `[●●●●●]` 100% ✅

### ✅ T115: Backend — endpoint GET /admin/dashboard (agregado)
- **Concluída:** Abril 2026
- **Arquivos:** `backend/app/api/v1/endpoints/admin_dashboard.py`, `backend/app/api/v1/router.py`
- **Endpoint:** `GET /v1/admin/dashboard?data=YYYY-MM-DD[&estabelecimento_id=N]`
- **Resposta agregada:** `{ data, filtro_estabelecimento_id, total_consultas, consultas_agendadas, consultas_realizadas, consultas_canceladas, taxa_ocupacao{slots_ocupados,total_slots,percentual}, proximas_consultas[5], alertas[], custo_ia_total, limite_diario, uso_modelos[] }`
- **RBAC:** `_resolver_est_id()` — ADMIN_ESTABELECIMENTO lê do JWT; ADMIN_GLOBAL aceita query param (ADR-026)
- **ADR:** ADR-025 (endpoint único), ADR-026 (ADMIN_GLOBAL query param)

### ✅ T116: TDAD — testes unitários /admin/dashboard
- **Concluída:** Abril 2026
- **Arquivos:** `backend/tests/unit/test_admin_dashboard.py`
- **Testes:** 10 — `obter_proximas_consultas` (4 casos), `obter_taxa_ocupacao` (3 casos), `calcular_alertas` (3 casos)
- **Cobertura:** slot sem consulta, taxa 0% e 50%, sem alertas, alerta urgência alta, alerta custo 80%
- **Verificação:** `uv run pytest tests/unit/test_admin_dashboard.py -q` → 10 passando

### ✅ T117: Frontend — DashboardService refatorado
- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/core/services/dashboard.service.ts`
- **Mudanças:** Interfaces `AdminDashboard`, `ProximaConsulta`, `TaxaOcupacao`, `Alerta`, `EstabelecimentoResumo`. Método `carregar(data?, estabelecimentoId?)` → GET único. Shortcuts: `kpi()`, `usoModelos()`, `proximas()`, `alertas()`, `taxaOcupacao()`. `carregarEstabelecimentos()` para ADMIN_GLOBAL.

### ✅ T118: Frontend — DashboardComponent v2 (KPIs navegáveis + alertas + próximas)
- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/dashboard/dashboard.component.{ts,html,scss}`
- **Funcionalidades:**
  - 5 KPI cards clicáveis → navegam para `/consultas?data=X[&status=Y]`
  - Alertas automáticos (urgência alta, pendentes, custo alto) com ícones e cores semânticas
  - Lista "Próximas 5 consultas" com hora, paciente, médico, especialidade, badge de urgência
  - Seletor de estabelecimento (ADMIN_GLOBAL) com `estabelecimentoCtrl.valueChanges` → reload automático
  - Custo IA clickável → `/billing`; Gráfico modelos clickável → `/billing`
  - Quick actions: Agenda, Consultas de Hoje, Billing
- **Imports adicionados:** `LowerCasePipe`, `RouterModule`, `MatChipsModule`, `MatListModule`, `Router`

### ✅ T119: Frontend — ConsultasComponent com query params
- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/consultas/consultas.component.ts`
- **Mudanças:** `ActivatedRoute` injetado; `ngOnInit` lê `?status` e `?data` dos query params; `filtroStatus.setValue(statusParam)` aplica filtro pré-selecionado; data param define a data de busca (padrão: hoje)
- **Resultado:** Dashboard → clique em KPI → Consultas já filtradas pelo status correto

---

## GRUPO 20 — Agenda Gerencial `[●●●●●]` 100% ✅

### ✅ T120: Backend — GET /agenda/slots/dia/{data}
- **Concluída:** Abril 2026
- **Arquivos:** `backend/app/services/agenda_service.py`, `backend/app/api/v1/endpoints/agenda.py`
- **Função:** `listar_slots_dia(db, data, estabelecimento_id, medico_id=None) → list[dict]`
- **Query:** LEFT JOIN Slot→Medico→Especialidade→Consulta→Paciente via SQLAlchemy `outerjoin`
- **Retorno por slot:** `{id, medico_id, medico_nome, especialidade_nome, data, hora_inicio("HH:MM"), hora_fim("HH:MM"), status, consulta: {...}|null}`
- **Segurança:** CPF sempre mascarado via `_mascarar_cpf()` → `"123.***.***-01"` (nunca exposto completo)
- **Filtro opcional:** `?medico_id=N`
- **RBAC:** `require_estabelecimento` — isola por tenant

### ✅ T121: TDAD — testes unitários agenda_slots_dia
- **Concluída:** Abril 2026
- **Arquivos:** `backend/tests/unit/test_agenda_slots_dia.py`
- **Testes:** 6 — slot com consulta, slot livre (consulta=None), CPF mascarado, dia vazio, filtro médico, hora formatada HH:MM
- **Fix TDAD:** `_row()` retorna tuple puro (não MagicMock) — `computed()` Angular não estava rastreando FormControl
- **Verificação:** `uv run pytest tests/unit/test_agenda_slots_dia.py -q` → 6 passando

### ✅ T122: Frontend — Agenda ADMIN_GLOBAL support
- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/agenda/agenda.component.{ts,html,scss}`
- **Mudanças:**
  - Injetados `AuthAdminService` e `DashboardService`
  - `isAdminGlobal` e `semEstabelecimento` computed signals
  - `estabelecimentoCtrl` + seletor visível apenas para ADMIN_GLOBAL
  - `semEstabelecimento()` → empty state "Selecione um estabelecimento" (bloqueia agenda)
  - `selecionarEstabelecimento(id)` → `POST /admin/selecionar-estabelecimento` → JWT scoped → reload
- **ADR:** ADR-027 (JWT scoped para agenda vs query param para dashboard)

### ✅ T123: Frontend — Filtros Agenda (reactive fix + especialidade)
- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/agenda/agenda.component.{ts,html,scss}`
- **Fix crítico:** `computed(() => filtroMedicoCtrl.value)` não é reativo — FormControl não é Signal. Criado `filtroMedicoId = signal<number | null>(null)` sincronizado via `valueChanges`.
- **Filtro médico:** `filtroMedicoCtrl.valueChanges` → `filtroMedicoId.set(id)` + `agenda.filtroMedicoId.set(id)` + `carregarPorData()` (server-side via `?medico_id=N`)
- **Filtro especialidade:** `filtroEspecialidadeCtrl` + `filtroEspecialidadeId` signal. Client-side: filtra dropdown de médicos (`medicosFiltrados`) E slots exibidos. Ao trocar especialidade: médico resetado automaticamente (ADR-029).
- **Verificação:** `ng build` sem erros; filtros funcionam em cadeia especialidade → médico → data

---

## GRUPO 21 — Multi-tenancy UX Fixes `[●●●●●]` 100% ✅

> Correções do fluxo ADMIN_GLOBAL: reatividade ao trocar filtro global, retorno ao modo global via novo JWT, e visibilidade do seletor no toolbar.

### ✅ T124: Reatividade do filtro global — effect() em Dashboard e Agenda
- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/features/dashboard/dashboard.component.ts`, `frontend-admin/src/app/features/agenda/agenda.component.ts`
- **Problema:** Ao trocar o filtro global no toolbar (sinal `estabelecimentoAtivoId`), as páginas não recarregavam — `ngOnInit()` só roda uma vez.
- **Fix:** Adicionado `effect()` no `constructor()` de ambos os componentes para rastrear `auth.estabelecimentoAtivoId()`. Ao mudar (não-null), `untracked(() => _carregar())` é chamado. `untracked()` evita loop infinito ao impedir rastreamento das chamadas internas ao effect.
- **Removido:** `await this._carregar()` explícito do `ngOnInit()` do Dashboard (o effect cobre o carregamento inicial).
- **Verificação:** `ng build` sem erros; ao selecionar clínica no toolbar, dashboard e agenda recarregam automaticamente.

### ✅ T125: Backend — POST /admin/modo-global
- **Concluída:** Abril 2026
- **Arquivo:** `backend/app/api/v1/endpoints/estabelecimentos.py`
- **Endpoint:** `POST /v1/admin/modo-global` — requer `require_role("ADMIN_GLOBAL")`
- **Comportamento:** Emite novo JWT com `role=ADMIN_GLOBAL` e **sem** `estabelecimento_id`. Permite que ADMIN_GLOBAL com token escopado volte ao modo global sem expirar a sessão.
- **Resposta:** `{ access_token, token_type }` (`ModoGlobalResponse`)
- **Motivação:** JWT com 15min de expiração tornava inviável restaurar o token global original (ADR-030).

### ✅ T126: Frontend — voltarModoGlobal() + Shell.trocarEstabelecimento()
- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/src/app/core/services/auth-admin.service.ts`, `frontend-admin/src/app/shared/shell/shell.component.ts`, `frontend-admin/src/app/features/selecionar-estabelecimento/selecionar-estabelecimento.component.ts`
- **`voltarModoGlobal()`:** POST `/admin/modo-global` → atualiza localStorage + `_token` + `usuario()` signal (via `_aplicarToken`) + limpa `_estabelecimentoFiltroId` → `_modoSuperAdmin.set(true)`.
- **Shell `trocarEstabelecimento()`:** Chamava `router.navigate(['/selecionar-estabelecimento'])`. Agora chama `voltarModoGlobal()` diretamente — o seletor aparece no toolbar sem navegação extra. Fallback: redireciona se a API falhar.
- **Menu do usuário:** Split em dois botões condicionais — "Modo Global" (quando escopado) e "Selecionar estabelecimento" (quando global).
- **`continuarComoSuperAdmin()` na tela de seleção:** Agora async, chama `voltarModoGlobal()` com fallback para a flag-only anterior.

### ✅ T127: CSS fix — toolbar-est-select invisível no toolbar branco
- **Concluída:** Abril 2026
- **Arquivo:** `frontend-admin/src/app/shared/shell/shell.component.scss`
- **Problema:** `::ng-deep` forçava `color: #fff` e `border-color: rgba(255,255,255,.4)` — estilos projetados para toolbar azul-escuro. O toolbar do projeto tem fundo branco → texto e bordas invisíveis.
- **Diagnóstico:** Playwright confirmou o elemento presente no DOM (`isVisible() = true`) mas invisível na screenshot (branco sobre branco). O dropdown abria corretamente ao clicar na área invisível.
- **Fix:** Substituídas as cores brancas por: texto `var(--color-text, #1e293b)`, seta `var(--color-text-secondary, #64748b)`, borda `rgba(0,0,0,.25)`, ícone `var(--color-text-secondary, #64748b)`.

### ✅ T128: Playwright E2E — fluxo ADMIN_GLOBAL toolbar
- **Concluída:** Abril 2026
- **Arquivos:** `frontend-admin/playwright.config.ts`, `frontend-admin/e2e/admin-global-toolbar.spec.ts`
- **Testes (6/6 passando):**
  - T1: Login ADMIN_GLOBAL redireciona para `/selecionar-estabelecimento`
  - T2: Toolbar exibe `mat-select` em modo global (após "Modo Global")
  - T3: Selecionar clínica no dropdown carrega dados (empty state desaparece)
  - T4: Fluxo completo — selecionar clínica (JWT escopado) → swap → JWT sem est_id → seletor retorna
  - T5: "Todas as clínicas" exibe empty state e limpa dados
  - T6: Após swap escopado→global, `filtroEstCtrl` desync detectado e corrigido
- **Comando:** `npx playwright test e2e/admin-global-toolbar.spec.ts`

### ✅ T129: Dashboard agregado — ADMIN_GLOBAL "Todas as clínicas"
- **Concluída:** Abril 2026
- **Problema:** ADMIN_GLOBAL em modo global (filtro = null) via via "Todas as clínicas" via seletor no toolbar recebia HTTP 400 do backend (`require_estabelecimento` exigia est_id) e o frontend exibia empty state em vez de dados.
- **Arquivos modificados:**
  - `backend/app/api/v1/dependencies.py`
  - `backend/app/api/v1/endpoints/admin_dashboard.py`
  - `frontend-admin/src/app/features/dashboard/dashboard.component.ts`
  - `frontend-admin/src/app/features/dashboard/dashboard.component.html`
- **Backend:**
  - Adicionado `get_estabelecimento_id_opcional` em `dependencies.py`: retorna `int | None` — `None` para ADMIN_GLOBAL sem header (modo "todas as clínicas") em vez de HTTP 400.
  - `admin_dashboard.py`: trocado `require_estabelecimento` → `get_estabelecimento_id_opcional`; filtros `q_status` e `q_urg` agora condicionais (`if est_id is not None`); demais queries já aceitavam `None`.
- **Frontend:**
  - `effect()` agora dispara quando `!precisaSelecionarEstabelecimento()` em vez de `id !== null` — cobre tanto modo escopado quanto "todas as clínicas".
  - Template: `semEstabelecimento()` → `auth.precisaSelecionarEstabelecimento()` — empty state só aparece quando ADMIN_GLOBAL ainda não escolheu o modo, não quando está em modo global sem filtro.

---

## GRUPO 16 — N3 Enterprise `[BACKLOG — NÃO INICIAR]` ⛔
> Não iniciar sem aprovação explícita após validação do MVP.

### T105: Integração FHIR HL7 — BACKLOG
- Padrão HL7 FHIR para integração com Tasy, MV, Soul MV
- Pré-requisito: contrato com estabelecimento que usa prontuário

### T106: Telemedicina Nativa — BACKLOG
- Slot tipo TELECONSULTA com link Jitsi gerado automaticamente
- Link enviado 15min antes via WhatsApp
- Pré-requisito: compliance CFM + definir provedor de vídeo

### T107: Dashboard Saúde Pública B2G — BACKLOG
- Mapa de calor de sintomas por região, alertas de surtos
- Integração e-SUS / RNDS do Ministério da Saúde
- Pré-requisito: contrato com secretaria de saúde

---

## GRUPO 17 — Plataforma BotFlow `[BACKLOG — NÃO INICIAR]` ⛔
> Iniciar somente após 3+ clientes MedBot em produção pagando.
> VPS Hostinger KVM 4 + CapRover já pronto — R$0 de infra adicional.

### T108: Extrair core como biblioteca compartilhada — BACKLOG
- auth, whatsapp, billing, RAG, FSM base → pacote Python interno
- Estrutura monorepo: core/ + bots/saude/ + bots/_template/

### T109: Template de novo domínio (_template/) — BACKLOG
- Entidades, FSM e prompts parametrizáveis por domínio
- Novo bot funcional em 1-2 dias reaproveitando o core

### T110: EduBot — Bot de matrículas e aulas — BACKLOG
### T111: TransitoBot — Bot CNH/multas/DETRAN — BACKLOG

---

## GRUPO 22 — ADMIN_GLOBAL Platform Dashboard `[●●●●●●●●●●●●●]` 100% ✅

> **Concluído:** 2026-04-08

### ✅ T130: Fix — Remover PII de proximas_consultas (modo global)

- **Grupo:** G22
- **Arquivos:** `backend/app/api/v1/endpoints/admin_dashboard.py`, `frontend-admin/src/app/features/dashboard/dashboard.component.html`
- **Ação:** Remover/mascarar `paciente_nome` e `medico_nome` na resposta quando `est_id=None`
- **TDAD:** Teste verifica que resposta sem est_id não contém campos PII
- **Verificação:** `uv run pytest tests/unit/test_admin_dashboard.py -q`

### ✅ T131: Model AuditoriaAcao + migration Alembic

- **Grupo:** G22
- **Arquivos:** `backend/app/models/auditoria.py`, `backend/alembic/versions/`
- **Ação:** Criar model SQLAlchemy 2.0 com campos: usuario_id, usuario_role, acao, estabelecimento_id, entidade, entidade_id, detalhes (JSONB), ip_origem, created_at
- **TDAD:** Teste verifica que migration aplica sem erro em banco limpo
- **Verificação:** `uv run alembic upgrade head`

### ✅ T132: AuditoriaService — registrar e listar eventos

- **Grupo:** G22
- **Depende de:** T131
- **Arquivos:** `backend/app/services/auditoria_service.py`, `backend/tests/unit/test_auditoria_service.py`
- **Ação:** Criar `AuditoriaService.registrar()` (não propaga exceção) e `AuditoriaService.listar()` (paginado)
- **TDAD:** Testes RED para registrar com sucesso, registrar sem propagar erro, listar com filtros
- **Verificação:** `uv run pytest tests/unit/test_auditoria_service.py -q`

### ✅ T133: Dependency registrar_acesso_clinica + integração nos endpoints

- **Grupo:** G22
- **Depende de:** T132
- **Arquivos:** `backend/app/api/v1/dependencies.py`
- **Ação:** Quando ADMIN_GLOBAL envia `X-Estabelecimento-ID`, registrar evento `ACESSO_CLINICA` via `AuditoriaService`
- **TDAD:** Teste verifica evento gerado ao acessar endpoint com header
- **Verificação:** `uv run pytest tests/integration/ -q`

### ✅ T134: Endpoint GET /v1/admin/plataforma/dashboard

- **Grupo:** G22
- **Depende de:** T132
- **Arquivos:** `backend/app/api/v1/endpoints/admin_plataforma.py`, `backend/tests/unit/test_admin_plataforma.py`
- **Ação:** Retornar: total estab. ativos/inativos, licenças por status, usuários por role, consultas hoje (sem PII), custo total, alertas de plataforma
- **TDAD:** Testes RED para cada métrica e para ausência de PII
- **Verificação:** `uv run pytest tests/unit/test_admin_plataforma.py -q`

### ✅ T135: Endpoint GET /v1/admin/licencas

- **Grupo:** G22
- **Depende de:** T131
- **Arquivos:** `backend/app/api/v1/endpoints/admin_plataforma.py`
- **Ação:** Listar todas as licenças com status, plano, datas, estabelecimento. Exclusivo ADMIN_GLOBAL.
- **TDAD:** Teste verifica RBAC (403 para ADMIN_ESTABELECIMENTO) e retorno correto
- **Verificação:** `uv run pytest tests/unit/test_admin_plataforma.py -q`

### ✅ T136: Endpoints CRUD /v1/admin/usuarios (gestão de staff por ADMIN_ESTABELECIMENTO)

- **Grupo:** G22
- **Arquivos:** `backend/app/api/v1/endpoints/admin_usuarios.py`, `backend/tests/unit/test_admin_usuarios.py`
- **Ação:** POST /usuarios (criar RECEPCIONISTA/MEDICO), GET /usuarios (listar do est.), PATCH /usuarios/{id} (atualizar/desativar)
- **TDAD:** Testes RED para criação, listagem isolada por est_id, desativação, RBAC
- **Verificação:** `uv run pytest tests/unit/test_admin_usuarios.py -q`

### ✅ T137: Endpoint GET /v1/admin/auditoria

- **Grupo:** G22
- **Depende de:** T132
- **Arquivos:** `backend/app/api/v1/endpoints/admin_plataforma.py`
- **Ação:** Listar eventos de auditoria paginados com filtros: acao, estabelecimento_id, data_inicio, data_fim
- **TDAD:** Teste verifica paginação, filtros, RBAC (somente ADMIN_GLOBAL)
- **Verificação:** `uv run pytest tests/unit/test_admin_plataforma.py -q`

### ✅ T138: Frontend — Fix authGuard + NAV_ITEMS por modo

- **Grupo:** G22
- **Arquivos:** `frontend-admin/src/app/core/guards/auth.guard.ts`, `frontend-admin/src/app/shared/shell/shell.component.ts`
- **Ação:** ADMIN_GLOBAL → dashboard de plataforma diretamente. NAV_ITEMS separado: global (Dashboard, Estabelecimentos, Licenças, Usuários, Billing, Auditoria) vs escopado (menu completo da clínica) vs ADMIN_ESTABELECIMENTO
- **Verificação:** ng build sem erros; navegação manual nos 3 modos

### ✅ T139: Frontend — PlatformDashboardComponent

- **Grupo:** G22
- **Depende de:** T134, T138
- **Arquivos:** `frontend-admin/src/app/features/platform-dashboard/`, `frontend-admin/src/app/core/services/dashboard.service.ts`
- **Ação:** 6 cards: estabelecimentos, licenças, billing, consultas (sem PII), usuários, alertas. Novo método `carregarPlataforma()` no DashboardService.
- **Verificação:** ng serve, acessar /dashboard como ADMIN_GLOBAL global

### ✅ T140: Frontend — LicencasGlobalComponent

- **Grupo:** G22
- **Depende de:** T135, T138
- **Arquivos:** `frontend-admin/src/app/features/licencas/`
- **Ação:** Tabela com status, plano, vencimento, ações (renovar, suspender). Filtros por status/estabelecimento.
- **Verificação:** ng serve, acessar /licencas como ADMIN_GLOBAL

### ✅ T141: Frontend — UsuariosComponent (ADMIN_GLOBAL global + ADMIN_ESTABELECIMENTO)

- **Grupo:** G22
- **Depende de:** T136, T138
- **Arquivos:** `frontend-admin/src/app/features/usuarios/`
- **Ação:** ADMIN_GLOBAL vê todos por role/estabelecimento. ADMIN_ESTABELECIMENTO vê/cria/desativa staff do próprio estabelecimento.
- **Verificação:** ng serve, testar nos dois roles

### ✅ T142: Frontend — AuditoriaComponent

- **Grupo:** G22
- **Depende de:** T137, T138
- **Arquivos:** `frontend-admin/src/app/features/auditoria/`
- **Ação:** Tabela paginada de eventos com filtros de data, tipo de ação, clínica. Somente ADMIN_GLOBAL.
- **Verificação:** ng serve, acessar /auditoria como ADMIN_GLOBAL

---

## GRUPO 23 — Painel RECEPCIONISTA `[BACKLOG — NÃO INICIAR]` ⛔

> Aguardar conclusão de G22 (T130–T142).

### T143: Backend — Endpoints operacionais para RECEPCIONISTA (agenda, consultas, pacientes)

- **Grupo:** G23 — BACKLOG
- **Descrição:** Verificar e ajustar RBAC dos endpoints de Agenda, Consultas, Pacientes para aceitar o role RECEPCIONISTA. Garantir isolamento por estabelecimento_id do JWT.

### T144: Frontend — Menu e dashboard operacional para RECEPCIONISTA

- **Grupo:** G23 — BACKLOG
- **Descrição:** NAV_ITEMS para RECEPCIONISTA: Dashboard (operacional), Agenda, Consultas, Pacientes, Médicos (somente leitura). Sem Billing, Licença, Auditoria.

### T145: Frontend — Dashboard operacional (consultas do dia, próximos atendimentos)

- **Grupo:** G23 — BACKLOG
- **Descrição:** Dashboard focado no dia a dia da recepção: consultas agendadas hoje, pacientes aguardando, alertas de urgência.

---

## GRUPO 24 — Painel MÉDICO `[BACKLOG — NÃO INICIAR]` ⛔

> Aguardar conclusão de G23.
> **Atenção:** o model `Medico` (agenda) precisa ser vinculado ao role `MEDICO` (usuário de login) — consultar ADR antes de iniciar.

### T146: Backend — Vincular Usuario.role=MEDICO ao model Medico (agenda)

- **Grupo:** G24 — BACKLOG
- **Descrição:** Criar ou utilizar FK entre `usuarios.id` e `medicos.usuario_id`. Médico faz login com email+senha e recebe `medico_id` no JWT para filtrar dados.

### T147: Backend — Endpoints com filtro por medico_id no JWT

- **Grupo:** G24 — BACKLOG
- **Descrição:** Agenda, Consultas e Pacientes filtrados automaticamente por `medico_id` quando role=MEDICO.

### T148: Frontend — Painel do Médico (agenda própria, consultas próprias)

- **Grupo:** G24 — BACKLOG
- **Descrição:** NAV_ITEMS para MEDICO: Minha Agenda, Minhas Consultas, Meus Pacientes. Médico pode atender em múltiplos estabelecimentos — considerar seleção de contexto.

---

## Critérios de Aceite Globais do MVP

- Paciente agenda consulta do zero via chat em menos de 3 minutos
- Bot detecta EMERGENCIA e exibe SAMU 192 antes de qualquer agendamento
- Recepcionista vê, cria e cancela consultas no painel admin
- Médico visualiza agenda do dia com resumo de triagem IA
- Todo uso de token é registrado com custo em USD
- Alerta enviado quando custo diário atinge 80% do limite
- Lembrete WhatsApp enviado 24h antes da consulta
- Deploy em Railway (demo) e Hostinger KVM 4 + CapRover (produção) com Evolution API para WhatsApp e HTTPS automático via CapRover

