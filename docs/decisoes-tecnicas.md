# Decisões Técnicas — MedBot
> Architecture Decision Records (ADRs)
> Registrar aqui TODA decisão técnica tomada durante o desenvolvimento.
> Formato: uma decisão por seção, imutável após registro.

---

## Como usar este arquivo

Quando o agente ou o desenvolvedor tomar uma decisão técnica não prevista no PLAN.md:

1. Adicionar uma nova seção `ADR-{NNN}` ao final deste arquivo
2. Preencher todos os campos
3. Nunca editar ADRs já registradas — apenas adicionar novas

---

## ADR-001: FastAPI em vez de Django REST Framework
- **Data:** Abril 2026
- **Contexto:** Escolha do framework Python principal para a API
- **Decisão:** FastAPI 0.135
- **Justificativa:** WebSocket nativo, async-first desde o início, Pydantic v2 integrado, performance superior, autodoc OpenAPI sem configuração extra
- **Alternativas consideradas:** Django REST Framework (mais maduro, admin nativo), Flask (mais simples)
- **Trade-offs aceitos:** Menor ecossistema de plugins que Django, sem painel admin nativo
- **Aprovado por:** Junior Payão

---

## ADR-002: Dois frontends Angular separados
- **Data:** Abril 2026
- **Contexto:** Portal público (paciente) e painel interno (recepcionista/médico/admin) poderiam ser um único app Angular com lazy loading por role
- **Decisão:** Duas aplicações Angular 21 completamente separadas
- **Justificativa:** Superfícies de ataque independentes (portal exposto à internet, admin restrito à rede interna), ciclos de release e deploy independentes, bundle menor por aplicação
- **Alternativas consideradas:** Single SPA com módulos por role, Micro-frontends
- **Trade-offs aceitos:** Código compartilhado requer biblioteca ou duplicação
- **Aprovado por:** Junior Payão

---

## ADR-003: OpenRouter como gateway LLM
- **Data:** Abril 2026
- **Contexto:** Acessar múltiplos modelos (LLaMA, BioMistral, Gemini, Claude) para roteamento por custo e especialidade
- **Decisão:** OpenRouter via LangChain
- **Justificativa:** Troca de modelo sem alterar código, roteamento por custo automático, fallback, faturamento unificado
- **Alternativas consideradas:** SDK direto da Anthropic, SDK direto da Google, hub próprio
- **Trade-offs aceitos:** Latência adicional ~50ms, dependência de terceiro, custo de markup do OpenRouter
- **Aprovado por:** Junior Payão

---

## ADR-004: Qdrant standalone para RAG
- **Data:** Abril 2026
- **Contexto:** Vector store para embeddings dos protocolos clínicos
- **Decisão:** Qdrant ^1.x em container separado
- **Justificativa:** Performance superior ao pgvector para coleções > 10k vetores, filtros híbridos nativos, não requer extensão no PostgreSQL
- **Alternativas consideradas:** pgvector (mesmo banco), Pinecone (SaaS), Chroma (local)
- **Trade-offs aceitos:** Mais um serviço para operar e monitorar
- **Aprovado por:** Junior Payão

---

## ADR-005: Evolution API para WhatsApp
- **Data:** Abril 2026
- **Contexto:** Integração com WhatsApp Business para notificações e chat
- **Decisão:** Evolution API self-hosted
- **Justificativa:** Self-hosted elimina custo por mensagem, controle total dos dados, API simples
- **Alternativas consideradas:** Twilio WhatsApp (pago por mensagem), Meta Cloud API direta
- **Trade-offs aceitos:** Responsabilidade pela operação da Evolution API, risco de instabilidade
- **Aprovado por:** Junior Payão

---

## ADR-006: uv como package manager Python
- **Data:** Abril 2026
- **Contexto:** Gerenciamento de dependências Python do backend
- **Decisão:** uv (Astral)
- **Justificativa:** 10-100x mais rápido que pip, lockfile determinístico, compatível com pyproject.toml, recomendado pela documentação oficial FastAPI
- **Alternativas consideradas:** pip + requirements.txt, Poetry, Pipenv
- **Trade-offs aceitos:** Ferramenta relativamente nova (2024), menor comunidade que pip
- **Aprovado por:** Junior Payão

---

## ADR-007: Estratégia de deploy em fases (atualizado — Abril 2026)
- **Fase 1 — Demo:** Railway Free Trial (30 dias, grátis, zero config)
- **Fase 2 — MVP validado + projetos pessoais:** Hostinger KVM 4
  R$62,99/mês (12 meses, cupom TECMUNDO -10% = R$755,89/ano)
  4 vCPU | 16 GB RAM | 200 GB NVMe | 8 TB banda | 1 Gbps
  Ubuntu 24.04 LTS | Brasil — Campinas (28ms latência) | BRL sem câmbio
  Backups semanais grátis | DDoS protection | API pública + MCP (Kodee)
  CapRover gerencia todos os apps — MedBot + projetos pessoais
  Domínio grátis por 1 ano incluso | 30 dias reembolso
- **Fase 3 — Plataforma multi-bot:** mesmo KVM 4 já contratado
  Suporta 5-10 bots (MedBot, EduBot, TransitoBot) via CapRover
  Custo por bot adicional: praticamente R$0 de infra extra
- **Por que KVM 4 em vez de KVM 2:**
  KVM 4 (R$62,99) vs KVM 2 (R$43,99) = R$19/mês a mais
  Dobra recursos: 4 vCPU / 16GB / 200GB vs 2 vCPU / 8GB / 100GB
  Cabe MedBot + projetos pessoais + futuro multi-bot confortavelmente
  KVM 2 ficaria apertado com múltiplos projetos simultâneos
- **Stack no VPS (todos via CapRover + Docker):**
  FastAPI + Celery + Redis + Qdrant + PostgreSQL + Evolution API
  frontends Angular (portal + admin) via Nginx + CapRover
  Evolution API — WhatsApp free, open source, Apache 2.0
  Sem custo de licença de nenhum serviço
- **Evolution API no VPS:**
  Free e open source (Apache 2.0) — R$0 de licença
  Roda em Docker no mesmo VPS — sem VPS extra
  Scan QR Code via WhatsApp > Dispositivos conectados — 30 segundos
  Performance adequada para MVP (até 500 msgs/dia confortavelmente)
  Risco: atualizações WhatsApp Web — mitigado usando tag :latest
- **Trade-off aceito:** PostgreSQL e Redis em Docker no VPS em vez de
  serviços gerenciados — aceitável para MVP e multi-bot
- **Aprovado por:** Junior Payão

---

## ADR-008: Gestão de secrets por fase
- **Data:** Abril 2026
- **Contexto:** API keys do OpenRouter, Evolution API e SendGrid precisam de proteção em todos os ambientes
- **Decisão:** Railway Variables (Fases 1/2) → variáveis de ambiente CapRover (Fase 3)
- **Justificativa:** Railway tem gestão de secrets embutida. CapRover expõe via painel protegido por senha. Vault desnecessário no MVP
- **Trade-offs:** Sem Sealed Secrets ou Vault — complexidade desnecessária para esta fase
- **Aprovado por:** Junior Payão

---

## ADR-009: Ollama local em vez de OpenRouter para desenvolvimento
- **Data:** Abril 2026
- **Contexto:** Ambiente de desenvolvimento com Alienware Area 51 (RTX 5090 32GB VRAM + 64GB RAM). OpenRouter exige chave paga e latência de rede para cada chamada LLM.
- **Decisão:** Substituir OpenRouter por Ollama local (`http://localhost:11434/v1`) em desenvolvimento. Produção mantém OpenRouter.
- **Modelos adotados:** `llama3.1:8b` para todos os fluxos de chat/triagem, `nomic-embed-text` para embeddings RAG.
- **Justificativa:** Ollama expõe API OpenAI-compatível — zero mudança de código além de `.env`. RTX 5090 roda `llama3.1:8b` (4.9GB) inteiramente na VRAM com latência < 500ms. Custo zero em dev.
- **Alternativas consideradas:** Continuar com OpenRouter (custo em dev), usar `llama3.3:70b` local (43GB, partial offload, mais lento).
- **Trade-offs aceitos:** `llama3.1:8b` tem qualidade inferior ao `biomistral` para triagem clínica e ao Claude Sonnet para casos complexos. Aceitável para desenvolvimento e demo MVP. Produção pode usar OpenRouter com modelos especializados.
- **Caminho de upgrade:** Para produção, reverter `.env` para OpenRouter com os modelos originais (`biomistral-7b`, `claude-sonnet-4-6`). O código não muda.
- **Aprovado por:** Junior Payão

---

## ADR-010: Modelo medico especializado no Ollama para triagem
- **Data:** Abril 2026
- **Contexto:** Com ADR-009, o ambiente de desenvolvimento ficou 100% local, mas o uso de `llama3.1:8b` em todas as etapas reduz acurácia na triagem clínica e na sugestão de especialidade.
- **Decisão:** Priorizar `cniongolo/biomistral:latest` (Ollama) nas features de triagem e contexto clínico (`triagem_clinica` e `rag_protocolo`), mantendo `llama3.1:8b` para saudação/coleta/agendamento.
- **Justificativa:** `BioMistral` é ajustado para domínio biomédico e melhora qualidade de respostas clínicas sem abandonar custo zero e latência local do Ollama.
- **Alternativas consideradas:** Manter `llama3.1:8b` em todo fluxo (mais simples, menor qualidade clínica), usar somente modelo premium em nuvem (melhor qualidade, maior custo e latência).
- **Trade-offs aceitos:** Necessidade de baixar modelo adicional local (`ollama pull cniongolo/biomistral:latest`) e consumo maior de VRAM do que `llama3.1:8b`.
- **Caminho de rollback:** Definir `MODEL_MEDICO` e `MODEL_RAG` para `llama3.1:8b` no `.env`.
- **Aprovado por:** Junior Payão

## ADR-011: Máquina de estados implementada como campo livre no Redis
- **Data:** Abril 2026
- **Contexto:** A arquitetura em `docs/medbot_arquitetura.md` define 9 estados formais com transições sequenciais (`START → COLETANDO_SINTOMAS → TRIAGEM → ... → FINALIZADO`). Uma FSM explícita com validação de transições é mais robusta mas aumenta complexidade.
- **Decisão:** MVP usa campo `etapa` livre armazenado na sessão Redis em `chat_service.py`. Sem validação formal de ordem de estados.
- **Justificativa:** Simplicidade no MVP — o fluxo feliz funciona sem FSM formal. A validação de ordem de estados é desnecessária enquanto o frontend controla o fluxo.
- **Alternativas consideradas:** FSM com biblioteca `transitions` (Python), Enum de estados com `__transitions__` manual.
- **Trade-offs aceitos:** Sem prevenção de transições inválidas (ex: ir de SAUDACAO direto para CONFIRMACAO). Risco baixo no MVP onde só existe um cliente (portal Angular).
- **Caminho de upgrade:** Implementar T52 (`state_machine.py`) quando houver múltiplos canais (portal + WhatsApp) com possibilidade de conflito de estado.
- **Aprovado por:** Junior Payão

---

## ADR-012: Classificação de intenção embutida na etapa da sessão
- **Data:** Abril 2026
- **Contexto:** A arquitetura define um módulo dedicado de classificação de intenção pré-LLM que retorna `{"tipo": "saude" | "agendamento" | "geral"}` antes de qualquer roteamento de modelo. O `chat_service.py` usa diretamente a `etapa` da sessão para selecionar o modelo via `router.py`.
- **Decisão:** Não criar `intent_classifier.py` separado no MVP. O roteador de modelos (`router.py` + `ROUTING_RULES` em `config.py`) cobre o caso de uso imediato sem passo adicional.
- **Justificativa:** O classificador separado exige uma chamada LLM extra (latência + custo) antes da mensagem principal. No MVP, o contexto da `etapa` é suficiente para rotear o modelo correto.
- **Alternativas consideradas:** Classificador baseado em regras (sem LLM), classificador leve com LLaMA em modo zero-shot.
- **Trade-offs aceitos:** Sem pré-filtragem de intenção — mensagens fora de contexto (ex: perguntas sobre futebol) chegam ao LLM principal. Risco mitigado pelo `SYSTEM_PROMPT` restritivo.
- **Caminho de upgrade:** Implementar T51 (`intent_classifier.py`) quando houver dados suficientes para fine-tuning ou quando o volume de mensagens fora de escopo for relevante.
- **Aprovado por:** Junior Payão

---

## ADR-013: temperature=0.3 fixo para todos os modelos LLM
- **Data:** Abril 2026
- **Contexto:** A arquitetura especifica parâmetros distintos por modelo — LLaMA 3.1 com `temperature=0.6` (mais criativo para conversação) e BioMistral com `temperature=0.2 + top_p=0.9 + repeat_penalty=1.1` (mais determinístico para triagem clínica). O `_criar_llm()` em `chat_service.py` aplica `temperature=0.3` fixo via LangChain `ChatOpenAI`.
- **Decisão:** `temperature=0.3` conservador e uniforme para todos os modelos no MVP.
- **Justificativa:** `0.3` é um meio-termo funcional — mais determinístico que `0.6` (reduz alucinações conversacionais) e ligeiramente mais flexível que `0.2` (evita respostas repetitivas). `top_p` e `repeat_penalty` não são parâmetros nativos do `ChatOpenAI` do LangChain sem configuração adicional de `model_kwargs`.
- **Alternativas consideradas:** Passar `model_kwargs={"top_p": 0.9, "repetition_penalty": 1.1}` para BioMistral via LangChain (funcional com OpenRouter).
- **Trade-offs aceitos:** Triagem clínica ligeiramente menos determinística que o ideal. Conversação ligeiramente mais conservadora que o ideal. Impacto baixo no MVP.
- **Caminho de upgrade:** Implementar T53 — criar `_criar_llm(modelo, feature)` com parâmetros distintos por modelo e feature.
- **Aprovado por:** Junior Payão

---

## ADR-014: Scaffold frontend-admin entregue sem telas de feature
- **Data:** Abril 2026
- **Contexto:** T40 (Scaffold Angular 21 — Admin) foi executada criando a estrutura base do `frontend-admin/`. Porém as telas de feature (T41 Dashboard KPIs, T42 Calendário, T43 Modal Triagem, T44 CRUD Médicos, T45 Dashboard Billing, T46 Config Limites) foram criadas como estrutura de arquivos mas sem implementação completa das funcionalidades.
- **Decisão:** Registrar T40 como ✅ concluída (scaffold entregue) e manter T41–T46 como ⬜ pendentes para implementação incremental.
- **Justificativa:** O scaffold garante que o projeto compila e serve em `localhost:4201`, com rotas, guard de autenticação, interceptor JWT e serviços HTTP configurados. As features podem ser implementadas independentemente sem risco de retrabalho na estrutura.
- **Alternativas consideradas:** Marcar T40 como parcial (🔄) até todas as features estarem prontas.
- **Trade-offs aceitos:** TASK.md pode parecer otimista ao marcar T40 como concluída sem features visíveis. Mitigado pelo registro explícito do escopo entregue na task.
- **Aprovado por:** Junior Payão

## ADR-015: Multi-tenancy por row-level isolation (coluna hospital_id)
- **Data:** Abril 2026
- **Contexto:** O produto precisa suportar múltiplos hospitais/clientes na mesma instância da plataforma. Um ADMIN_GLOBAL pode gerenciar N hospitais distintos, cada um com seus próprios médicos, especialidades, pacientes, slots e consultas completamente isolados.
- **Decisão:** Usar row-level multi-tenancy: coluna `hospital_id FK → hospitais.id` adicionada em todas as tabelas de domínio (`especialidades`, `medicos`, `pacientes`, `slots`, `consultas`, `sessoes_chat`, `usuarios`). O contexto de tenant é transportado no JWT (`hospital_id` no payload) e aplicado automaticamente via dependency `get_hospital_id` injetada nos endpoints.
- **Justificativa:** Row-level é a abordagem padrão para SaaS B2B (Stripe, Linear, Notion): (1) um único schema Postgres simplifica migrations e backups; (2) queries cross-tenant são possíveis para ADMIN_GLOBAL sem conexão extra; (3) menor complexidade operacional que schema-per-tenant no MVP; (4) facilita auditoria com filtros simples por `hospital_id`.
- **Alternativas consideradas:** Schema separado por tenant (Postgres `SET search_path`) — descartado por complexidade de migrations e conexão pool; banco separado por tenant — descartado por custo operacional no MVP.
- **Trade-offs aceitos:** Um bug de filtragem pode vazar dados entre tenants se `hospital_id` não for aplicado em todos os queries — mitigado pela dependency obrigatória `get_hospital_id` e pelo padrão de serviço que sempre recebe `hospital_id` como parâmetro explícito. ADMIN_GLOBAL tem acesso cross-tenant por design — requer auditoria mais rigorosa desse role.
- **Novos roles:** `ADMIN_GLOBAL` (sem `hospital_id` no JWT, acessa tudo), `ADMIN_HOSPITAL` (renomeado de `ADMIN`, escopo restrito ao hospital).
- **Aprovado por:** Junior Payão

## ADR-015: Multi-tenancy via row-level com EstabelecimentoSaude
- **Data:** Abril 2026
- **Contexto:** A plataforma MedBot precisa suportar múltiplos clientes (estabelecimentos de saúde) na mesma infraestrutura. Um admin global deve poder gerenciar N estabelecimentos. O termo "Hospital" foi descartado por ser restritivo — a plataforma atende hospitais, clínicas, UBS, laboratórios e postos de saúde.
- **Decisão:** Row-level multi-tenancy com coluna `estabelecimento_id` em todas as tabelas de domínio. Entidade `EstabelecimentoSaude` com campo `tipo` (enum: HOSPITAL, CLINICA, UBS, LABORATORIO, POSTO_SAUDE, OUTRO). Novos roles: ADMIN_GLOBAL (acessa N estabelecimentos) e ADMIN_ESTABELECIMENTO (limitado a 1). O `estabelecimento_id` viaja no JWT de todos os usuários exceto ADMIN_GLOBAL.
- **Justificativa:** Row-level é o padrão de mercado para SaaS B2B (Stripe, Linear, Notion). Schema-per-tenant foi descartado pela complexidade de migrations. A generalização para `EstabelecimentoSaude` permite expandir o mercado além de hospitais sem retrabalho de schema.
- **Alternativas consideradas:** Schema separado por tenant (descartado — complexidade operacional), tabela de tipos separada (descartado — overkill para MVP, enum é suficiente e pode ser migrado para tabela depois).
- **Trade-offs aceitos:** Todos os queries precisam de filtro `WHERE estabelecimento_id = ?`. Mitigado pela dependency `get_estabelecimento_id` injetada automaticamente.
- **Aprovado por:** Junior Payão

---

## ADR-016: Tabela separada `licencas` vs campos em `estabelecimentos`
- **Data:** Abril 2026
- **Contexto:** O sistema precisa rastrear ciclo de vida de licença (TRIAL → ATIVA → EXPIRADA | SUSPENSA) com campos de auditoria (suspensa_por, suspensa_em, motivo_suspensao), datas de expiração distintas (trial vs licença paga) e campos reservados para integração futura com gateway de pagamento.
- **Decisão:** Tabela separada `licencas` com FK `estabelecimento_id UNIQUE` (relacionamento 1:1). Relationship `licenca` adicionado em `EstabelecimentoSaude` via SQLAlchemy `uselist=False`.
- **Justificativa:** Ciclo de vida de licença é um domínio distinto de dados cadastrais do estabelecimento. Separar evita: (1) poluir a tabela central com 10+ campos opcionais; (2) misturar contextos de auditoria financeira com dados operacionais; (3) dificultar futura extração para microsserviço de billing. A FK UNIQUE garante integridade sem necessidade de tabela de junção.
- **Alternativas consideradas:** Campos em `estabelecimentos` (descartado — acoplamento alto), tabela `licenca_historico` com múltiplos registros (descartado — complexidade desnecessária no MVP, histórico pode ser adicionado depois).
- **Trade-offs aceitos:** JOIN necessário para acessar dados de licença junto com dados do estabelecimento. Mitigado pelo relationship SQLAlchemy lazy-loaded.
- **Aprovado por:** Junior Payão

---

## ADR-017: Verificação de licença via FastAPI Dependency vs Middleware ASGI
- **Data:** Abril 2026
- **Contexto:** Precisamos bloquear acesso aos endpoints de domínio (médicos, pacientes, agenda, chat) quando a licença está expirada ou suspensa, sem quebrar endpoints públicos (auth, licença, billing) nem endpoints de bootstrap (criar estabelecimento).
- **Decisão:** FastAPI Dependency `verificar_licenca_ativa` injetada via `dependencies=[Depends(verificar_licenca_ativa)]` no `include_router()` dos routers de domínio.
- **Justificativa:** (1) Composição natural com `get_db` e `get_estabelecimento_id` — a dependency já recebe o `estabelecimento_id` validado do JWT; (2) Seletividade: aplicada apenas nos routers corretos, sem regex de path; (3) Testabilidade: pode ser mockada em testes de integração com `app.dependency_overrides`; (4) HTTP semântico correto: 402 (pagamento requerido) e 403 (suspenso) distintos por caso — difícil de fazer em middleware genérico.
- **Alternativas consideradas:** Middleware ASGI (descartado — sem acesso fácil ao `estabelecimento_id` do JWT sem re-validação, dificuldade para distinguir rotas públicas), decorator por endpoint (descartado — verboso, propenso a esquecer em novos endpoints).
- **Trade-offs aceitos:** Dois hits no banco por request nos routers de domínio (get_estabelecimento_id + buscar_licenca). Mitigado por cache Redis futuro se necessário.
- **Aprovado por:** Junior Payão

---

## ADR-018: Quotas de plano em `config.py` vs banco de dados
- **Data:** Abril 2026
- **Contexto:** Os planos (basico, pro, enterprise) têm limites de médicos ativos, consultas/mês e canais disponíveis. Esses limites precisam ser verificados em tempo real ao criar médicos e consultas.
- **Decisão:** Quotas definidas como dicionário `PLANO_QUOTAS` em `config.py` (código-fonte), não em tabela de banco de dados.
- **Justificativa:** (1) Regras de negócio da plataforma, não dados de usuário — pertencem ao código; (2) Mudanças de quota são alterações de produto que requerem deploy intencional, não updates de banco por engano; (3) Sem overhead de query adicional para buscar quotas — `PLANO_QUOTAS[plano]` é O(1) em memória; (4) Visibilidade total em code review — qualquer alteração de quota fica em diff.
- **Alternativas consideradas:** Tabela `planos` com campos de quota (descartado — dados estáticos de produto em banco são overkill no MVP, complica testes), variáveis de ambiente por plano (descartado — não escala para múltiplos campos por plano).
- **Trade-offs aceitos:** Alterar quotas exige novo deploy. Aceitável no MVP onde mudanças de produto são intencionais. Caminho de upgrade: mover para tabela quando houver planos customizados por cliente enterprise.
- **Aprovado por:** Junior Payão

---

## ADR-019: Revisão de qualidade com /simplify nos frontends
- **Data:** Abril 2026
- **Contexto:** Backend e frontends 100% entregues. Antes do deploy, aplicar revisão de qualidade automática nos dois frontends via /simplify.
- **Decisão:** Executar /simplify em todos os arquivos TypeScript/SCSS dos dois frontends e corrigir issues antes de iniciar o Grupo 9 — Deploy.
- **Escopo:** `frontend-portal/` (T34–T39) e `frontend-admin/` (T40–T46)
- **Aprovado por:** Junior Payão

## ADR-020: Fluxo Guiado de Agendamento com Coleta de Dados e Convênios
- **Data:** Abril 2026
- **Contexto:** O fluxo atual do chat coleta nome e sintomas na mesma mensagem, gerando respostas longas com asteriscos e sem estrutura. Faltam dados obrigatórios (telefone, email) e suporte a convênios.
- **Decisão:** Refatorar FSM e prompts do chat para fluxo guiado de 7 etapas, uma pergunta por vez. Adicionar model `Convenio` com endpoint dinâmico por estabelecimento. Slot vai para RESERVADO ao selecionar e só para AGENDADO após confirmação com dados completos.
- **Consequências:** Nova tabela `convenios`, campo `convenio_id` em `Paciente`, estado `RESERVADO` em `SlotStatus`, novos estados FSM, prompts refatorados sem asteriscos.
- **Aprovado por:** Junior Payão

## ADR-021: Histórico Clínico do Paciente no Chat
- **Data:** Abril 2026
- **Contexto:** Bot recomeça do zero a cada sessão, desperdiçando contexto de triagens anteriores do mesmo paciente.
- **Decisão:** Armazenar histórico de sessões anteriores no PostgreSQL (`sessoes_historico`) e injetar como contexto no prompt do sistema nas novas sessões. Máximo 3 sessões anteriores para não inflar o contexto LLM.
- **Consequências:** Nova tabela `sessoes_historico`, busca por `paciente_id` ao criar sessão, injeção no `SystemMessage`.
- **Aprovado por:** Junior Payão

## ADR-022: Fila de Espera Inteligente
- **Data:** Abril 2026
- **Contexto:** Quando não há slots disponíveis, o sistema retorna mensagem negativa e perde o paciente permanentemente.
- **Decisão:** Adicionar model `FilaEspera`. Quando paciente tenta agendar sem slot disponível, entra na fila. Job Celery monitora cancelamentos e novos slots — notifica via WhatsApp automaticamente. Slot vai para RESERVADO por 30 min aguardando confirmação do paciente da fila.
- **Consequências:** Nova tabela `fila_espera`, worker Celery `fila_espera.py`, lógica no chat para oferecer fila.
- **Aprovado por:** Junior Payão

## ADR-023: Resumo de Triagem para o Médico
- **Data:** Abril 2026
- **Contexto:** Médico chega à consulta sem saber o que o paciente relatou ao bot, perdendo informação valiosa da triagem IA.
- **Decisão:** Após consulta confirmada, gerar resumo estruturado com LLM (modelo econômico) e enviar ao médico via WhatsApp e email 30 min antes da consulta. Nunca inclui termos de diagnóstico.
- **Consequências:** Novo service `resumo_triagem.py`, worker `resumo_medico.py`, campo `resumo_enviado_em` na Consulta.
- **Aprovado por:** Junior Payão

## ADR-024: Relatórios de Saúde do Estabelecimento
- **Data:** Abril 2026
- **Contexto:** Admin visualiza apenas billing de tokens. Gestores precisam de dados operacionais para tomada de decisão (ocupação, confirmações, sintomas frequentes, custo por agendamento).
- **Decisão:** Adicionar endpoints de relatórios agregados com filtro por período e médico. Frontend admin com gráficos Chart.js (barras, doughnut) e KPI cards.
- **Consequências:** Novo endpoint `/v1/relatorios/`, novo service `relatorio_service.py`, nova rota no frontend-admin.
- **Aprovado por:** Junior Payão

## ADR-025: Reagendamento Automático pelo WhatsApp
- **Data:** Abril 2026
- **Contexto:** Médico cancela consulta → recepcionista liga para cada paciente manualmente → processo lento e custoso.
- **Decisão:** Quando consulta é cancelada pelo lado do médico/estabelecimento, job Celery envia WhatsApp ao paciente com 3 novos slots para escolher. Paciente responde "1", "2" ou "3" no WhatsApp. Zero trabalho manual. Identificar contexto de reagendamento via sessão Redis.
- **Consequências:** Campo `motivo_cancelamento` em Consulta, worker `reagendamento.py`, expansão do webhook WhatsApp.
- **Aprovado por:** Junior Payão

## ADR-026: Avaliação Pós-Consulta (NPS)
- **Data:** Abril 2026
- **Contexto:** Estabelecimentos não têm feedback estruturado sobre qualidade das consultas e satisfação dos pacientes.
- **Decisão:** 24h após consulta marcada como REALIZADA, bot envia WhatsApp com avaliação de 1-5 estrelas. Resultado armazenado em model `Avaliacao` (unique por consulta) e exibido no painel admin com NPS calculado.
- **Consequências:** Nova tabela `avaliacoes`, worker `avaliacao.py`, expansão do webhook WhatsApp, endpoints e frontend de relatórios atualizados.
- **Aprovado por:** Junior Payão

## ADR-027: Abstração de Provedor WhatsApp
- **Data:** Abril 2026
- **Contexto:** Projeto usa Evolution API (free, self-hosted). Diferentes clientes e fases exigem provedores distintos sem mudar regras de negócio.
- **Decisão:** Protocolo `WhatsAppProvider` com adapters por provedor. `WHATSAPP_PROVIDER` no `.env` define qual usar em runtime. Provedores suportados: `evolution` | `uazapi` | `zapi` | `meta`.
- **Evolution API:** free, open source, Apache 2.0, roda no VPS. Performance: até ~500 msgs/dia. Setup: ~10 minutos com CapRover + scan QR Code.
- **Recomendação por fase:**
  Demo/MVP: Evolution API no Hostinger (já no VPS, custo zero)
  Escala/múltiplos clientes: UazAPI R$38/dispositivo (gerenciado)
  Enterprise: Meta Cloud API oficial (compliance total, zero risco ban)
- **Implementar como T103 — próxima task após G15 N1+N2 concluídos**
- **Aprovado por:** Junior Payão

## ADR-028: N3 Diferenciais Enterprise — BACKLOG
- **Data:** Abril 2026
- **Status:** Mapeado, não priorizado. Não iniciar sem aprovação explícita.
- **Itens mapeados:** FHIR HL7 (integração prontuário Tasy/MV), Telemedicina Nativa (Jitsi + compliance CFM), Dashboard Saúde Pública B2G (e-SUS/RNDS)
- **Pré-requisito:** contrato com estabelecimento que usa sistema de prontuário ou com secretaria de saúde
- **Aprovado por:** Junior Payão

## ADR-029: Visão de Plataforma Multi-Bot — BACKLOG
- **Data:** Abril 2026
- **Contexto:** VPS Hostinger KVM 4 + CapRover já comporta múltiplos bots. Core já é multi-tenant (G11) e licenciado (G12). R$0 de infra adicional.
- **Decisão:** Registrado como G17. Iniciar somente após 3+ clientes MedBot em produção pagando. Estrutura: monorepo com `core/` reutilizável + `bots/saude/` + `bots/_template/`.
- **Bots mapeados:** MedBot (saúde), EduBot (educação), TransitoBot (trânsito/DETRAN), JurídicoBot, e outros
- **Aprovado por:** Junior Payão

## ADR-030: Bugs corrigidos em demo — Abril 2026
- **Data:** Abril 2026
- **Contexto:** Durante demo com cliente, quatro bugs críticos foram identificados e corrigidos em produção: (1) tela branca pós-login por quebra de cadeia flex entre `app-root`, `main` e `chat-container`; (2) loop infinito em `COLETANDO_CONVENIO` por ausência de tratamento para respostas afirmativas; (3) `POST /v1/chat/sessao` retornando 400 por ausência de licenças no banco (tabela `licencas` vazia após seed); (4) sessão Redis sem `estabelecimento_id`, impedindo consulta à agenda.
- **Decisão:** Corrigir todos em hotfix imediato sem branch separada, dado o contexto de demo ao vivo.
- **Arquivos alterados:** `app.scss`, `chat.component.scss`, `chat.component.ts/html`, `chat_service.py`, `chat.py` (endpoint), inserção manual de licenças no banco.
- **Trade-offs aceitos:** Licenças inseridas via SQL manual (não via seed script). Caminho de upgrade: adicionar `licencas` ao `scripts/seed.py`.
- **Aprovado por:** Junior Payão

---

## ADR-031: System prompt em inglês com regra de uma pergunta por vez
- **Data:** Abril 2026
- **Contexto:** O `SYSTEM_PROMPT_CONVERSA` original em português não impedia o LLM de fazer múltiplas perguntas em uma única mensagem, gerando respostas longas com bullet points e asteriscos mal renderizados.
- **Decisão:** Substituir pelo prompt em inglês fornecido pelo product owner, com regras explícitas: "Ask ONE question at a time", "2-3 sentences max", "Always respond in the same language the patient is using". Temperature reduzida de 0.6 para 0.3.
- **Justificativa:** LLMs seguem instruções em inglês com maior precisão que em português. A regra "respond in same language" garante que o paciente receba respostas em PT-BR mesmo com prompt em EN.
- **Arquivos alterados:** `backend/app/services/ia/prompts.py`
- **Trade-offs aceitos:** Prompt em idioma diferente do código-base pode causar estranheza em novos devs. Documentado aqui para rastreabilidade.
- **Aprovado por:** Junior Payão

---

## ADR-032: estabelecimento_id propagado via sessão Redis (não via WebSocket auth)
- **Data:** Abril 2026
- **Contexto:** O WebSocket `/v1/chat/ws/{token}` não suporta `HTTPBearer` dependency (incompatibilidade FastAPI + WebSocket). Sem o `estabelecimento_id` do JWT, o backend não conseguia consultar slots da agenda por tenant.
- **Decisão:** O endpoint `POST /v1/chat/sessao` (autenticado via JWT) captura o `estabelecimento_id` via `Depends(get_estabelecimento_id)` e o armazena na sessão Redis junto com o `session_token`. O WebSocket recupera o `estabelecimento_id` da sessão Redis ao processar cada mensagem.
- **Justificativa:** Padrão de "session enrichment" — o canal autenticado (REST) transfere contexto de segurança para o canal não-autenticado (WebSocket) via estado compartilhado (Redis). Alternativa (auth via query param no WS) descartada por expor o JWT na URL.
- **Arquivos alterados:** `backend/app/api/v1/endpoints/chat.py`, `backend/app/services/ia/chat_service.py`
- **Aprovado por:** Junior Payão

---

## ADR-033: Detecção de especialidade por texto livre + mapa de sinônimos
- **Data:** Abril 2026
- **Contexto:** O LLM retorna especialidades em linguagem natural ("Medicina Geral", "clínico geral", "cardiologista") que não batem exatamente com a whitelist canônica ("Clinica Geral", "Cardiologia"). A detecção por substring falhava para todos os sinônimos.
- **Decisão:** Adicionar `_SINONIMOS_ESPECIALIDADE: dict[str, str]` em `ChatService` mapeando variantes comuns para os nomes canônicos da whitelist. A função `_extrair_especialidade_do_texto` verifica a whitelist primeiro e os sinônimos em seguida.
- **Justificativa:** Evita depender de JSON estruturado do LLM para o fluxo guiado — o prompt conversacional não deve ser obrigado a retornar JSON. O mapa de sinônimos é uma camada de normalização no backend, seguindo a regra de ouro "LLM decide, backend controla".
- **Arquivos alterados:** `backend/app/services/ia/chat_service.py`
- **Trade-offs aceitos:** Mapa de sinônimos precisa ser mantido manualmente quando novas especialidades forem adicionadas. Alternativa (usar LLM para normalizar) descartada por adicionar latência e custo.
- **Aprovado por:** Junior Payão

---

## ADR-034: SUGERINDO_ESPECIALIDADE como estado de resposta direta (sem LLM)
- **Data:** Abril 2026
- **Contexto:** Quando o usuário confirmava intenção de agendar ("Gostaria de agendar"), o estado `SUGERINDO_ESPECIALIDADE` ainda chamava o LLM (`triagem_clinica`/BioMistral), que retornava texto genérico sobre "enviar e-mail com horários" em vez de apresentar os cards de slot.
- **Decisão:** `SUGERINDO_ESPECIALIDADE` passa a ser tratado em `_resposta_direta_fluxo_guiado`: qualquer resposta do usuário que não seja negação dispara transição imediata para `APRESENTANDO_SLOTS` + chamada a `_buscar_slots()`. O LLM não é chamado neste estado.
- **Justificativa:** Agendamento é fluxo determinístico — não há valor em chamar o LLM para apresentar uma lista de horários. Reduz latência (~2s) e elimina risco de alucinação no momento crítico do fechamento do agendamento.
- **Arquivos alterados:** `backend/app/services/ia/chat_service.py`
- **Aprovado por:** Junior Payão

## ADR-035: Especialidades carregadas do banco por sessão, não de lista hardcoded
- **Data:** Abril 2026
- **Contexto:** O system prompt do LLM em `OUVINDO_SINTOMAS` listava 14 especialidades hardcoded (`ESPECIALIDADES_WHITELIST`). O LLM dizia "não temos nutricionista, mas temos clínico geral" — informação falsa, já que a clínica tinha apenas 4 especialidades (Clínica Geral, Cardiologia, Neurologia, Ortopedia). Isso quebrava a confiança do paciente e gerava despedidas antecipadas ("Boa sorte!") em vez de apresentar os slots.
- **Decisão:** `criar_sessao()` consulta `Especialidade` no banco filtrando por `estabelecimento_id` e `ativo=True`, armazenando a lista real na sessão Redis (`session_data["especialidades"]`). O prompt é construído dinamicamente por `obter_prompt_conversa(especialidades)` usando apenas as especialidades da clínica. `_extrair_especialidade_do_texto()` recebe essa lista para detecção.
- **Justificativa:** Cada clínica tem suas próprias especialidades. Hardcodear a lista viola o isolamento multi-tenant e causa alucinação do LLM. Carga na criação de sessão é O(1) e amortizada para toda a conversa.
- **Trade-off:** Se o banco não tiver especialidades cadastradas, o prompt usa a `ESPECIALIDADES_WHITELIST` como fallback.
- **Arquivos alterados:** `backend/app/services/ia/chat_service.py`, `backend/app/services/ia/prompts.py`
- **Aprovado por:** Junior Payão

## ADR-036: Fluxo pós-slot incompleto em T83/T84/T85 — implementação dos estados COLETANDO_CONTATO e CONFIRMANDO
- **Data:** Abril 2026
- **Contexto:** T85 foi marcada como ✅ mas o critério de verificação "fluxo completo nome→confirmação" nunca foi atendido. Os estados `COLETANDO_CONTATO` e `CONFIRMANDO` existiam na FSM mas não tinham handlers em `processar_mensagem`. Ao clicar em um card de slot, o backend recebia `"confirmar:ID"` mas não havia handler para `APRESENTANDO_SLOTS` neste caso — caía no LLM com mensagem incompreensível.
- **Decisão:** Implementar 3 métodos assíncronos dedicados: `_processar_slot_selecionado` (guarda slot_id, pede telefone), `_processar_coleta_contato` (step machine: telefone→email→resumo), `_processar_criar_agendamento` (busca Slot+Medico, cria/reutiliza Paciente, chama `agendar_consulta`, commita). Slots temporários salvos em `session_data["slots_temp"]` para recuperar dados na confirmação.
- **Justificativa:** Fluxo de booking é 100% determinístico — não requer LLM. Separar em métodos async permite acesso ao DB. CPF usa placeholder `"00000000000"` para pacientes anônimos (sem cadastro prévio via SMS).
- **Trade-off:** CPF placeholder viola unicidade semântica — paciente anônimo não pode ser reconhecido em consultas futuras. Resolução: T85 deve incluir etapa de coleta de CPF ou autenticação SMS antes da confirmação (work in progress).
- **Arquivos alterados:** `backend/app/services/ia/chat_service.py`
- **Aprovado por:** Junior Payão

## ADR-037: Violação do processo SDD durante sessão de debugging de demo — Abril 2026
- **Data:** Abril 2026
- **Contexto:** Durante sessão de debugging de demo ao vivo, mudanças foram feitas em `chat_service.py`, `prompts.py`, `auth-admin.service.ts` e outros arquivos sem seguir o processo SDD (sem TDAD, sem spec prévia, sem ADR imediato). O agente operou em modo "firefighting" em vez de metodologia.
- **Decisão:** Registrar retroativamente todas as decisões (ADR-030 a ADR-037). T85 reberta como 🔄 e repartida em subtasks verificáveis com TDAD. Próximas mudanças ao `chat_service.py` exigem spec GEARS aprovada antes do código.
- **Aprovado por:** Junior Payão

<!-- Adicionar novas decisões abaixo -->