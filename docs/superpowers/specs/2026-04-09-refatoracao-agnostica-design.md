# Spec — Refatoração Agnóstica + Catálogo de Serviços
> Data: 2026-04-09 | Status: APROVADO
> Grupos: G25 (Refatoração) + G26 (Vocabulário + Catálogo)

---

## Contexto e Motivação

O sistema foi construído com terminologia médica hardcoded (`medico`, `consulta`, `paciente`). Para suportar clínicas de estética, odontologia, biomedicina e outros segmentos sem refatoração futura, é necessário:

1. **G25** — Renomear entidades para termos agnósticos no código e banco
2. **G26** — Permitir que cada estabelecimento configure seu próprio vocabulário e catálogo de serviços

O produto ainda não foi lançado, portanto não há preocupação com backwards compatibility.

---

## G25 — Refatoração Agnóstica

### Renomeações

| De | Para | Escopo |
|---|---|---|
| `medico` | `profissional` | tabela, model, service, schema, endpoint, frontend |
| `consulta` | `atendimento` | tabela, model, service, schema, endpoint, frontend |
| `paciente` | `cliente` | tabela, model, service, schema, endpoint, frontend |
| `medico_estabelecimento` | `profissional_estabelecimento` | tabela, model |
| `ConsultaStatus` | `AtendimentoStatus` | enum Python + enum PostgreSQL |
| `/v1/medicos` | `/v1/profissionais` | endpoints |
| `/v1/consultas/*` | `/v1/atendimentos/*` | endpoints |
| `/v1/pacientes` | `/v1/clientes` | endpoints |

### O que NÃO muda no G25
- `especialidade` — mantém como qualificação/credencial do profissional
- `slot` — termo técnico de agenda, já agnóstico
- Lógica de negócio — apenas renomeação

### Novos status do enum AtendimentoStatus

Aproveitar a migration do G25 para adicionar os status do fluxo de recepção (G23):

```
AGENDADA            (existente)
CONFIRMADA          (existente)
CANCELADA           (existente)
PRESENTE            (novo) — cliente chegou na clínica
AGUARDANDO_ANAMNESE (novo) — recepcionista disparou anamnese
ANAMNESE_PREENCHIDA (novo) — cliente preencheu (futuro, via chat)
FICHA_CONCLUIDA     (novo) — recepcionista validou a ficha
AGUARDANDO_PAGAMENTO(novo)
PAGO                (novo)
AGUARDANDO_PROFISSIONAL (novo) — pronto para entrar com o profissional
EM_ATENDIMENTO      (novo) — profissional atendendo (G24)
CONCLUIDA           (existente)
FALTOU              (novo) — não compareceu
```

### Migration Alembic (única)

```sql
-- Renomear tabelas
ALTER TABLE medicos RENAME TO profissionais;
ALTER TABLE consultas RENAME TO atendimentos;
ALTER TABLE pacientes RENAME TO clientes;
ALTER TABLE medico_estabelecimento RENAME TO profissional_estabelecimento;

-- Renomear FKs e colunas medico_id → profissional_id
-- Renomear enum ConsultaStatus → AtendimentoStatus
-- Adicionar novos valores ao enum
```

### Histórico de status (tabela nova — decisão G23 Opção B)

```
consulta_status_historico → atendimento_status_historico

id                  SERIAL PK
atendimento_id      FK → atendimentos.id
status_anterior     AtendimentoStatus nullable
status_novo         AtendimentoStatus NOT NULL
usuario_id          FK → usuarios.id
observacao          TEXT nullable
created_at          TIMESTAMPTZ default now()
```

Índices: `(atendimento_id, created_at)`, `(usuario_id)`

A tabela `atendimentos` mantém o campo `status` como espelho do último registro — atualizado sincronamente em toda transição.

---

## G26 — Vocabulário Configurável + Catálogo de Serviços

### Vocabulário por estabelecimento

Campos adicionados a `EstabelecimentoSaude`:

```
label_profissional   VARCHAR(50) default 'Médico'
label_atendimento    VARCHAR(50) default 'Consulta'
label_cliente        VARCHAR(50) default 'Paciente'
label_especialidade  VARCHAR(50) default 'Especialidade'
```

O ADMIN_ESTABELECIMENTO configura esses valores no painel. O frontend lê do JWT ou de endpoint `/v1/estabelecimentos/meu` e aplica nos labels de toda a interface.

### Modelo TipoAtendimento

Catálogo de serviços por estabelecimento:

```
id                  SERIAL PK
estabelecimento_id  FK → estabelecimentos.id
nome                VARCHAR(100) NOT NULL   -- "Botox", "Limpeza de Pele", "Consulta"
descricao           TEXT nullable
duracao_min         INTEGER default 30
preco               NUMERIC(10,2) nullable
ativo               BOOLEAN default true
created_at          TIMESTAMPTZ
```

### Tabela profissional_tipo_atendimento (N:N)

```
profissional_id     FK → profissionais.id
tipo_atendimento_id FK → tipo_atendimento.id
PRIMARY KEY (profissional_id, tipo_atendimento_id)
```

### Impacto no agendamento

- Cliente escolhe `tipo_atendimento` ao agendar (no lugar de `especialidade` direto)
- Sistema filtra profissionais que oferecem aquele `tipo_atendimento`
- `atendimento` passa a ter `tipo_atendimento_id` (FK) além de `especialidade_id` (que pode ser nullable)
- `especialidade` continua existindo como credencial do profissional (CRM, área de formação)

### Endpoints novos (G26)

```
GET  /v1/tipo-atendimento                    — listar do estabelecimento
POST /v1/tipo-atendimento                    — criar (ADMIN_ESTABELECIMENTO)
PATCH /v1/tipo-atendimento/{id}              — editar
GET  /v1/profissionais/{id}/tipo-atendimento — listar serviços do profissional
POST /v1/profissionais/{id}/tipo-atendimento — vincular serviço ao profissional
```

---

## G26 — Módulo de Convênios

### Entidades

**Convenio** (por estabelecimento)
```
id, nome, codigo_ans (nullable), cnpj (nullable),
telefone_autorizacao (nullable), email (nullable),
website (nullable), ativo, estabelecimento_id, created_at
```

**ConvenioPlano** (planos dentro de uma operadora)
```
id, convenio_id → Convenio
nome            ("Bronze", "Apartamento", "Executivo")
ativo, created_at
```

**ClienteConvenio** (cliente pode ter N carteirinhas)
```
id, cliente_id → Cliente
convenio_id    → Convenio
plano_id       → ConvenioPlano
numero_carteirinha  VARCHAR(50)
nome_titular        VARCHAR(200) nullable  (titular da empresa se diferente)
validade            DATE nullable
principal           BOOLEAN default false  (carteirinha padrão)
ativo               BOOLEAN default true
created_at
```

**Atendimento** — 2 campos novos:
```
cliente_convenio_id → ClienteConvenio nullable  (PARTICULAR = null)
numero_autorizacao  VARCHAR(50) nullable
```

### Regras de negócio
- Convenio e planos são configurados por estabelecimento
- Um cliente pode ter N carteirinhas ativas (`ClienteConvenio`)
- Apenas uma carteirinha pode ser `principal = true` por cliente por estabelecimento
- No atendimento: se `modalidade_pagamento = CONVENIO`, `cliente_convenio_id` é obrigatório
- `numero_autorizacao` é registrado pela recepcionista ao avançar para `AGUARDANDO_PROFISSIONAL`

### Endpoints novos (G26)
```
GET    /v1/convenios                         — listar do estabelecimento
POST   /v1/convenios                         — criar (ADMIN_ESTABELECIMENTO)
PATCH  /v1/convenios/{id}                    — editar
GET    /v1/convenios/{id}/planos             — listar planos de uma operadora
POST   /v1/convenios/{id}/planos             — criar plano
PATCH  /v1/convenios/{id}/planos/{plano_id}  — editar plano
GET    /v1/clientes/{id}/convenios           — listar carteirinhas do cliente
POST   /v1/clientes/{id}/convenios           — adicionar carteirinha
PATCH  /v1/clientes/{id}/convenios/{cc_id}   — editar/desativar carteirinha
```

### Integração com Chat
- Bot pergunta: particular ou convênio?
- Se convênio: lista `ClienteConvenio` ativos do cliente
- Cliente seleciona a carteirinha → `cliente_convenio_id` salvo no atendimento

---

## Sequência de Entrega

```
G25 (branch: feature/g25-refatoracao-agnostica)   ← rename
  → merge main
    → G26 (branch: feature/g26-convenios)          ← módulo convênios robusto
      → merge main
        → G27 (branch: feature/g27-vocabulario)    ← vocabulário + catálogo serviços
          → merge main
            → G23 (branch: feature/g23-painel-recepcionista)
              → G24 (Painel PROFISSIONAL)
```

---

## Critérios de Aceite

### G25
- [ ] `uv run pytest tests/ -q` — 0 falhas após refatoração
- [ ] `ng build` frontend-admin sem erros
- [ ] `ng build` frontend-portal sem erros
- [ ] `uv run alembic upgrade head` em banco limpo sem erros
- [ ] Endpoints `/v1/profissionais`, `/v1/atendimentos`, `/v1/clientes` respondendo

### G26
- [ ] ADMIN_ESTABELECIMENTO configura vocabulário e frontend reflete imediatamente
- [ ] ADMIN_ESTABELECIMENTO cadastra tipos de atendimento
- [ ] Agendamento via portal filtra profissionais por tipo de atendimento selecionado
- [ ] Testes unitários para TipoAtendimento service e endpoints
