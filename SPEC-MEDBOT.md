# SPEC-MEDBOT — Sistema de Agendamento Médico com IA
> Versão: 1.0 | Status: RASCUNHO | Metodologia: SDD (Spec-Driven Development)

---

## 0. VISÃO GERAL DO SISTEMA

**Nome do Produto:** MedBot Agendamentos  
**Domínio:** Saúde — Agendamento de Consultas Médicas  
**Paradigma:** API-first, chatbot-first, offline-capable PWA  
**Stack Backend:** Python 3.12 + FastAPI + LangChain + OpenRouter  
**Stack Frontend:** Angular 21 (padrão Automaxia) + Angular Material 3  
**Banco:** PostgreSQL 16 + Redis 7  
**IA/RAG:** OpenRouter (multi-modelo) + Qdrant  
**Notificações:** Evolution API (WhatsApp) + SendGrid (Email)  
**Deploy:** Docker + Kubernetes (NKP Zello)

---

## 1. PERSONAS E PERFIS (ROLES)

| Role | Descrição | Acesso |
|---|---|---|
| `PACIENTE_EXTERNO` | Usuário do portal público ou WhatsApp | Portal externo + WhatsApp |
| `RECEPCIONISTA` | Operador interno que gerencia agenda | Painel interno (leitura/escrita) |
| `MEDICO` | Visualiza própria agenda e triagem do paciente | Painel interno (leitura) |
| `ADMIN` | Configuração total do sistema | Painel interno completo |
| `SISTEMA` | Serviço de jobs (Celery), sem UI | Apenas API interna |

---

## 2. ENTIDADES PRINCIPAIS

### 2.1 Paciente
```
id, cpf (único), nome, data_nascimento, telefone, email,
convenio, numero_carteirinha, created_at, ativo
```

### 2.2 Médico
```
id, crm, nome, especialidade_id, email, telefone,
duracao_consulta_min (default: 30), ativo, created_at
```

### 2.3 Especialidade
```
id, nome, descricao, cor_hex, icone, ativo
```

### 2.4 Slot de Agenda
```
id, medico_id, data, hora_inicio, hora_fim,
status (DISPONIVEL | BLOQUEADO | AGENDADO | ENCAIXE),
motivo_bloqueio, created_at
```

### 2.5 Consulta (Agendamento)
```
id, slot_id, paciente_id, medico_id, especialidade_id,
tipo (EXTERNO | INTERNO | ENCAIXE | RETORNO),
status (AGENDADA | CONFIRMADA | CANCELADA | REALIZADA | FALTA),
triagem_resumo (JSON), urgencia (BAIXA | MEDIA | ALTA | EMERGENCIA),
canal_origem (PORTAL | WHATSAPP | INTERNO),
observacoes, created_at, updated_at
```

### 2.6 Sessão de Chat
```
id, session_token, paciente_id (nullable), canal (PORTAL | WHATSAPP),
status (ATIVA | ENCERRADA | AGENDOU | ABANDONOU),
modelo_ia_usado, created_at, encerrada_at
```

### 2.7 Uso de Tokens (Billing IA)
```
id, session_id, modelo, feature
(TRIAGEM | AGENDAMENTO | RAG | RESUMO | GERAL),
prompt_tokens, completion_tokens, total_tokens,
cost_usd, user_type (EXTERNO | INTERNO),
created_at
```

### 2.8 Configuração de Limites (Alertas)
```
id, chave (daily_limit_usd | monthly_limit_usd | alert_threshold_pct),
valor, updated_by, updated_at
```

---

## 3. MÓDULOS DO SISTEMA

### MÓDULO A — Portal Externo (Paciente)
Interface pública. Acesso por CPF + código SMS.

### MÓDULO B — Chat Bot IA
Motor de triagem e agendamento conversacional. Usado no portal e WhatsApp.

### MÓDULO C — Painel Interno
Dashboard administrativo para recepcionistas, médicos e admins.

### MÓDULO D — API Backend
FastAPI REST + WebSocket. Serve os dois frontends e o WhatsApp.

### MÓDULO E — Motor de IA (LangChain + OpenRouter)
Orquestração de modelos, RAG, memória de sessão e roteamento por custo.

### MÓDULO F — Billing & Monitoramento de Tokens
Captura, persiste e alerta sobre consumo de tokens e custo por modelo.

### MÓDULO G — Notificações
Lembretes automáticos via WhatsApp e Email com confirmação e reagendamento.

---

## 4. ESPECIFICAÇÕES FUNCIONAIS (Formato GEARS)

---

### 4A — AUTENTICAÇÃO

```
QUANDO o paciente acessa o portal externo,
O SISTEMA DEVE solicitar CPF e enviar código SMS de 6 dígitos.

SE o código SMS expirar (>5 min),
ENTÃO O SISTEMA DEVE permitir reenvio com rate limit de 1/min.

QUANDO o usuário interno acessa o painel,
O SISTEMA DEVE autenticar via email + senha com JWT (access 15min + refresh 7d).

SE o role do usuário for MEDICO,
ENTÃO O SISTEMA DEVE restringir visualização apenas à própria agenda e triagens.
```

---

### 4B — CHATBOT / TRIAGEM IA

```
QUANDO o paciente inicia uma conversa no portal ou WhatsApp,
O SISTEMA DEVE criar uma sessão de chat com session_token único.

ENQUANTO a sessão está ATIVA,
O SISTEMA DEVE manter contexto das mensagens anteriores via Redis (TTL 30min).

QUANDO o bot coleta os sintomas do paciente,
O SISTEMA DEVE classificar urgência em: BAIXA | MEDIA | ALTA | EMERGENCIA.

SE a urgência for EMERGENCIA,
ENTÃO O SISTEMA DEVE exibir IMEDIATAMENTE número do SAMU (192) e UPA mais próxima,
E NÃO DEVE prosseguir com agendamento.

SE a urgência for ALTA,
ENTÃO O SISTEMA DEVE priorizar slots do mesmo dia ou próximo dia útil.

QUANDO o bot identifica os sintomas,
O SISTEMA DEVE sugerir automaticamente a especialidade mais adequada.

QUANDO o paciente confirma a especialidade,
O SISTEMA DEVE apresentar os próximos 3 horários disponíveis.

QUANDO o paciente escolhe um horário,
O SISTEMA DEVE confirmar o agendamento e gerar resumo da triagem em JSON.

AO finalizar o agendamento,
O SISTEMA DEVE encerrar a sessão com status AGENDOU e disparar notificação de confirmação.
```

---

### 4C — ROTEAMENTO DE MODELOS IA

```
QUANDO a mensagem for saudação ou coleta de dados básicos (nome, sintoma inicial),
O SISTEMA DEVE usar modelo econômico: meta-llama/llama-3.3-70b-instruct.

QUANDO a mensagem exigir análise clínica de sintomas ou sugestão de especialidade,
O SISTEMA DEVE usar modelo médico: microsoft/biomistral-7b ou llama com prompt RAG.

SE o paciente relatar sintomas complexos ou múltiplas comorbidades,
ENTÃO O SISTEMA DEVE escalar para modelo premium: anthropic/claude-sonnet-4-5.

SEMPRE QUE uma chamada ao LLM for concluída,
O SISTEMA DEVE registrar em token_usage: modelo, tokens, custo_usd, feature, session_id.
```

---

### 4D — AGENDAMENTO EXTERNO (Portal/WhatsApp)

```
QUANDO o paciente solicita agendamento,
O SISTEMA DEVE verificar se já existe CPF cadastrado.

SE o CPF não existir,
ENTÃO O SISTEMA DEVE criar o paciente com dados coletados pelo bot.

QUANDO o sistema apresenta horários,
O SISTEMA DEVE mostrar apenas slots com status DISPONIVEL nos próximos 30 dias.

QUANDO o slot for reservado,
O SISTEMA DEVE alterar status para AGENDADO e bloquear para outros pacientes.

SE o paciente não confirmar o agendamento em 10 minutos,
ENTÃO O SISTEMA DEVE liberar o slot automaticamente (job Celery).

QUANDO o agendamento for confirmado,
O SISTEMA DEVE enviar comprovante via WhatsApp e Email com opção de cancelamento.
```

---

### 4E — AGENDAMENTO INTERNO (Recepção)

```
QUANDO a recepcionista acessa o painel interno,
O SISTEMA DEVE exibir a agenda do dia em formato de calendário (dia/semana/mês).

QUANDO a recepcionista cria um agendamento manual,
O SISTEMA DEVE permitir encaixe fora dos slots padrão (tipo ENCAIXE).

QUANDO a recepcionista visualiza uma consulta agendada externamente,
O SISTEMA DEVE exibir o resumo de triagem gerado pelo bot.

QUANDO a recepcionista cancela uma consulta,
O SISTEMA DEVE solicitar motivo e liberar o slot automaticamente.

QUANDO o médico acessa o painel,
O SISTEMA DEVE exibir lista do dia com: nome, horário, especialidade, urgência e resumo IA.
```

---

### 4F — BILLING E MONITORAMENTO DE TOKENS

```
SEMPRE QUE uma chamada LLM for realizada,
O SISTEMA DEVE persistir em token_usage com: session_id, modelo, feature,
prompt_tokens, completion_tokens, total_tokens, cost_usd.

QUANDO o custo diário acumulado atingir 80% do limite configurado,
O SISTEMA DEVE enviar alerta por email ao ADMIN.

SE o custo diário ultrapassar o limite configurado,
ENTÃO O SISTEMA DEVE bloquear uso do modelo premium e usar apenas modelo econômico.

QUANDO o ADMIN acessa o dashboard de billing,
O SISTEMA DEVE exibir: custo total (dia/semana/mês), breakdown por modelo,
breakdown por feature, sessões ativas, média de tokens por conversa.

O SISTEMA DEVE permitir exportar relatório de custos em CSV por período.
```

---

### 4G — NOTIFICAÇÕES

```
24 horas antes da consulta,
O SISTEMA DEVE enviar lembrete via WhatsApp com link de confirmação ou cancelamento.

2 horas antes da consulta,
O SISTEMA DEVE enviar segundo lembrete via WhatsApp.

SE o paciente confirmar pelo link,
ENTÃO O SISTEMA DEVE atualizar status da consulta para CONFIRMADA.

SE o paciente cancelar pelo link,
ENTÃO O SISTEMA DEVE liberar o slot e perguntar se deseja reagendar.

SE a consulta chegar ao horário sem confirmação,
ENTÃO O SISTEMA DEVE manter status AGENDADA (não cancela automaticamente).
```

---

### 4H — RAG (Recuperação com Protocolos Clínicos)

```
QUANDO o bot realiza triagem de sintomas,
O SISTEMA DEVE consultar a base vetorial (Qdrant) com os sintomas como query.

O SISTEMA DEVE usar os trechos recuperados como contexto adicional ao prompt do LLM.

QUANDO um novo protocolo clínico for adicionado ao sistema,
O SISTEMA DEVE processar o PDF, gerar embeddings e indexar no Qdrant automaticamente.

O SISTEMA NÃO DEVE apresentar ao paciente os trechos brutos dos protocolos,
apenas usar como base para a resposta do bot.
```

---

### 4I — DASHBOARD GERENCIAL v2
> Implementado: Abril 2026 — G19 (T115–T119)

```
QUANDO o administrador acessa o painel,
O SISTEMA DEVE exibir KPIs do dia: total de consultas, agendadas, realizadas, canceladas.

QUANDO o administrador clica em um KPI de consultas,
O SISTEMA DEVE navegar para o módulo de Consultas filtrando pelo status correspondente.

O SISTEMA DEVE exibir taxa de ocupação do dia: slots ocupados / total de slots disponíveis.

O SISTEMA DEVE exibir as próximas 5 consultas do dia com: hora, paciente, médico, especialidade e urgência.

O SISTEMA DEVE exibir alertas automáticos quando:
  - Houver consultas com urgência ALTA ou EMERGENCIA sem atendimento
  - Houver consultas AGENDADAS pendentes de confirmação
  - O custo de IA diário atingir 80% do limite configurado

SE o usuário for ADMIN_GLOBAL,
ENTÃO O SISTEMA DEVE permitir filtrar o dashboard por estabelecimento via seletor.

SE o usuário for ADMIN_ESTABELECIMENTO,
ENTÃO O SISTEMA DEVE exibir apenas dados do próprio estabelecimento (isolamento multi-tenant).

O SISTEMA NÃO DEVE exibir dados de um estabelecimento para outro (vazamento de dados entre tenants).

QUANDO o administrador seleciona um estabelecimento no seletor,
O SISTEMA DEVE recarregar todos os KPIs do dashboard imediatamente.

O SISTEMA DEVE exibir custo de IA com barra de progresso proporcional ao limite diário,
colorida conforme nível: primária (<70%) | acento (70-89%) | alerta (>=90%).
```

---

### 4J — AGENDA GERENCIAL (Slots do Dia)
> Implementado: Abril 2026 — G20 (T120–T123)

```
QUANDO o administrador acessa a Agenda do dia,
O SISTEMA DEVE retornar todos os slots do dia via LEFT JOIN com consultas embutidas.

O SISTEMA DEVE exibir slots em todos os status: DISPONIVEL, AGENDADO, BLOQUEADO, ENCAIXE, RESERVADO.

SE o slot tiver consulta associada,
ENTÃO O SISTEMA DEVE embutir dados do paciente: nome e CPF mascarado.

O SISTEMA NÃO DEVE exibir o CPF completo do paciente em nenhuma resposta de API ou tela.
O CPF DEVE ser sempre mascarado no formato: 123.***.***-01

O SISTEMA DEVE permitir filtrar a agenda por especialidade (client-side).
O SISTEMA DEVE permitir filtrar a agenda por médico:
  - O filtro de especialidade DEVE limitar o dropdown de médicos à especialidade selecionada.
  - O filtro de médico DEVE recarregar do backend via GET /agenda/slots/dia/{data}?medico_id=N.

SE o usuário for ADMIN_GLOBAL sem estabelecimento selecionado (JWT sem est_id),
ENTÃO O SISTEMA DEVE exibir estado informativo: "Selecione um estabelecimento para ver a agenda".
E O SISTEMA DEVE exibir seletor de estabelecimento para que o Admin Global obtenha token com escopo.

QUANDO o Admin Global seleciona um estabelecimento na Agenda,
O SISTEMA DEVE obter novo JWT com escopo (POST /admin/selecionar-estabelecimento),
E DEVE recarregar a agenda e a lista de médicos automaticamente.

O SISTEMA DEVE trocar de data de duas formas: datepicker ou botões de dia anterior/próximo.
```

---

### 4K — QUALIDADE IA: SEGURANÇA E COMPORTAMENTO
> Implementado: Abril 2026 — G18 (T112–T114)

```
QUANDO a urgência classificada for EMERGENCIA,
O SISTEMA DEVE exibir IMEDIATAMENTE: "Em caso de EMERGÊNCIA [...] ligue para o SAMU 192"
E NÃO DEVE oferecer agendamento de consulta.

SE a mensagem recebida durante coleta de convênio for saudação (oi, olá, bom dia etc.) ou tiver ≤ 2 caracteres,
ENTÃO O SISTEMA NÃO DEVE interpretar como nome de convênio.
O SISTEMA DEVE repetir a pergunta sobre convênio sem avançar o estado.

O SISTEMA DEVE usar temperatura 0.6 para o modelo llama3.1:8b nos fluxos de saudação e coleta,
permitindo respostas mais naturais (ADR-028).
```

---

## 5. PLANO TÉCNICO — BACKEND (FastAPI)

### 5.1 Estrutura de Pastas

```
medbot-api/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py
│   │   │   ├── pacientes.py
│   │   │   ├── medicos.py
│   │   │   ├── especialidades.py
│   │   │   ├── agenda.py
│   │   │   ├── consultas.py
│   │   │   ├── chat.py          # WebSocket + REST
│   │   │   ├── billing.py
│   │   │   └── notificacoes.py
│   ├── core/
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # AsyncPG pool
│   │   ├── redis.py             # Redis client
│   │   └── security.py         # JWT + hashing
│   ├── services/
│   │   ├── ia/
│   │   │   ├── chat_service.py  # Orquestrador LangChain
│   │   │   ├── triagem.py       # Classificação de urgência
│   │   │   ├── rag.py           # Qdrant retrieval
│   │   │   ├── router.py        # Roteamento de modelos
│   │   │   └── billing.py      # Track tokens + custo
│   │   ├── agenda_service.py
│   │   ├── notificacao_service.py
│   │   └── whatsapp_service.py
│   ├── models/                  # SQLAlchemy async models
│   ├── schemas/                 # Pydantic v2 schemas
│   ├── workers/                 # Celery tasks
│   │   ├── lembretes.py
│   │   ├── slot_cleanup.py
│   │   └── billing_alert.py
│   └── main.py
├── alembic/                     # Migrations
├── tests/                       # Pytest
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

### 5.2 Endpoints Principais

| Método | Rota | Role | Descrição |
|---|---|---|---|
| POST | /v1/auth/sms/request | PUBLIC | Solicita código SMS |
| POST | /v1/auth/sms/verify | PUBLIC | Verifica código, retorna JWT |
| POST | /v1/auth/login | PUBLIC | Login interno (email+senha) |
| GET | /v1/agenda/disponivel | PUBLIC | Slots disponíveis por especialidade |
| POST | /v1/consultas | PACIENTE/RECEP | Agendar consulta |
| PATCH | /v1/consultas/{id}/cancelar | PACIENTE/RECEP | Cancelar consulta |
| WS | /v1/chat/ws/{session_token} | PUBLIC | WebSocket do chatbot |
| POST | /v1/chat/whatsapp | SISTEMA | Webhook Evolution API |
| GET | /v1/billing/dashboard | ADMIN | Dashboard de custos |
| GET | /v1/billing/export | ADMIN | Exportar CSV de custos |
| POST | /v1/rag/documentos | ADMIN | Upload protocolo clínico |

---

## 6. PLANO TÉCNICO — FRONTEND (Angular 21)

### 6.1 Aplicações Separadas

**App 1: Portal Externo** (`medbot-portal`)
- Rota base: `/`
- Páginas: Home, Chat/Triagem, Meus Agendamentos, Confirmação
- Auth: JWT via CPF + SMS
- PWA: sim (instalável no celular)

**App 2: Painel Interno** (`medbot-admin`)
- Rota base: `/admin`
- Páginas: Dashboard, Agenda (Calendário), Consultas, Pacientes, Médicos, Billing, Config
- Auth: JWT email + senha com RBAC
- PWA: opcional

### 6.2 Estrutura de Módulos (Padrão Automaxia)

```
src/app/
├── core/
│   ├── auth/          # Guards, Interceptors, AuthService
│   ├── models/        # Interfaces TypeScript
│   └── services/      # Services compartilhados
├── shared/
│   ├── components/    # ChatWidget, CalendarView, StatusBadge
│   └── pipes/         # currency-brl, tokens-format
├── features/
│   ├── chat/          # Chat UI + WebSocket
│   ├── agenda/        # Calendário visual
│   ├── consultas/     # Lista + detalhe
│   ├── pacientes/     # CRUD (admin)
│   ├── medicos/       # CRUD (admin)
│   └── billing/       # Dashboard de tokens/custos
```

---

## 7. INFRAESTRUTURA (Kubernetes / NKP Zello)

```yaml
Serviços:
  medbot-api:        FastAPI (2 replicas)
  medbot-portal:     Nginx Angular (2 replicas)
  medbot-admin:      Nginx Angular (2 replicas)
  postgres:          PostgreSQL 16 (StatefulSet)
  redis:             Redis 7 (StatefulSet)
  qdrant:            Qdrant 1.x (StatefulSet)
  celery-worker:     Celery (2 replicas)
  celery-beat:       Celery Beat (1 replica)

Ingress:
  portal.medbot.com.br   → medbot-portal
  admin.medbot.com.br    → medbot-admin
  api.medbot.com.br      → medbot-api
```

---

## 8. VARIÁVEIS DE AMBIENTE

```env
# OpenRouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Modelos
MODEL_ECONOMICO=meta-llama/llama-3.3-70b-instruct
MODEL_MEDICO=microsoft/biomistral-7b
MODEL_PREMIUM=anthropic/claude-sonnet-4-5

# Billing Limits
DAILY_LIMIT_USD=10.00
MONTHLY_LIMIT_USD=200.00
ALERT_THRESHOLD_PCT=80

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/medbot
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333

# WhatsApp
EVOLUTION_API_URL=http://evolution:8080
EVOLUTION_API_KEY=...
WHATSAPP_INSTANCE=medbot

# JWT
SECRET_KEY=...
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## 9. TASKS DE IMPLEMENTAÇÃO (Ordem de Execução)

### GRUPO 0 — Setup
```
T01: Scaffold do projeto FastAPI (pyproject.toml, estrutura de pastas)
T02: Configurar Docker Compose local (postgres, redis, qdrant)
T03: Configurar Alembic + criar migrations das entidades
T04: Configurar settings (pydantic-settings + .env)
```

### GRUPO 1 — Auth
```
T05: Implementar auth via SMS (Twilio/Zenvia + Redis TTL)
T06: Implementar auth interna JWT (email + senha + RBAC)
T07: Implementar middleware de autenticação FastAPI
```

### GRUPO 2 — Agenda e Consultas
```
T08: CRUD de Especialidades
T09: CRUD de Médicos + geração automática de slots
T10: CRUD de Pacientes
T11: Serviço de disponibilidade de agenda
T12: Criação e cancelamento de consultas
T13: Job Celery: cleanup de slots reservados expirados
```

### GRUPO 3 — Chat IA
```
T14: Configurar LangChain + OpenRouter (cliente base)
T15: Implementar roteador de modelos por complexidade
T16: Implementar memória de sessão via Redis
T17: Implementar triagem: coleta de sintomas + classificação de urgência
T18: Implementar sugestão de especialidade + apresentação de slots
T19: Implementar confirmação de agendamento pelo chat
T20: Implementar WebSocket endpoint (/v1/chat/ws)
T21: Implementar webhook WhatsApp (Evolution API)
```

### GRUPO 4 — RAG
```
T22: Configurar cliente Qdrant + collection de protocolos
T23: Implementar ingestão de PDFs (upload → chunking → embedding → indexar)
T24: Implementar retrieval no fluxo de triagem
```

### GRUPO 5 — Billing
```
T25: Implementar middleware de captura de tokens em toda chamada LLM
T26: Implementar cálculo de custo por modelo (tabela de preços configurável)
T27: Implementar endpoints de dashboard de billing
T28: Implementar job Celery de alertas de custo (80% e 100%)
T29: Implementar exportação CSV
```

### GRUPO 6 — Notificações
```
T30: Implementar serviço de WhatsApp (Evolution API)
T31: Implementar serviço de Email (SendGrid)
T32: Implementar jobs Celery de lembretes (D-1 e H-2)
T33: Implementar link de confirmação/cancelamento tokenizado
```

### GRUPO 7 — Frontend Portal Externo
```
T34: Scaffold Angular 21 (padrão Automaxia)
T35: Tela de login (CPF + SMS)
T36: Chat UI com WebSocket (bolhas, digitando, status)
T37: Tela de confirmação de agendamento
T38: Tela de meus agendamentos
T39: PWA config + installable
```

### GRUPO 8 — Frontend Painel Interno
```
T40: Scaffold Angular 21 admin (padrão Automaxia)
T41: Dashboard com KPIs (consultas do dia, taxa de confirmação, custo IA)
T42: Calendário de agenda (dia/semana/mês)
T43: Modal de detalhe da consulta com triagem IA
T44: CRUD de médicos e especialidades
T45: Dashboard de Billing (gráficos + tabela + export CSV)
T46: Config de limites de custo
```

### GRUPO 9 — Deploy
```
T47: Dockerfile multi-stage FastAPI
T48: Dockerfile multi-stage Angular (nginx 1.27-alpine)
T49: Manifests Kubernetes (deployments, services, ingress, PVC)
T50: CI/CD GitLab (test → build → push → deploy)
```

---

## 10. CRITÉRIOS DE ACEITE (MVP)

- [ ] Paciente consegue agendar uma consulta do zero via chat em menos de 3 minutos
- [ ] Bot detecta EMERGENCIA e exibe SAMU antes de qualquer agendamento
- [ ] Recepcionista consegue ver, criar e cancelar consultas no painel interno
- [ ] Médico visualiza agenda do dia com resumo de triagem IA
- [ ] Todo uso de token é registrado com custo em USD
- [ ] Alerta é disparado quando custo diário atinge 80% do limite
- [ ] Lembrete WhatsApp enviado 24h antes da consulta
- [ ] Sistema opera em Kubernetes com 2 réplicas do backend
