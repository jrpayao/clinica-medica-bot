# SPEC — Frontend Admin MedBot (G18 — Upgrade Completo)
> Status: APROVADO
> Derivado de: SPEC-MEDBOT.md § G8 + endpoints mapeados Abril 2026

---

## Contexto

O frontend-admin atual tem 8 telas funcionais (G8 concluído) mas construídas com CSS customizado
e sem Angular Material. Faltam telas para 5 domínios cobertos pelo backend, e as telas existentes
carecem de loading states, empty states, toasts, paginação e UX profissional.

Este SPEC define o upgrade completo para um painel de gestão de nível profissional, fácil de usar
e bem documentado, cobrindo 100% dos endpoints admin disponíveis.

---

## Personas Afetadas

| Persona | Frequência | Contexto |
|---|---|---|
| ADMIN_GLOBAL | Diária | Gerencia todas as clínicas, ativa licenças, monitora plataforma |
| ADMIN_ESTABELECIMENTO | Diária | Gerencia médicos, agenda, pacientes e custos da sua clínica |
| RECEPCIONISTA | Diária | Visualiza agenda, cancela consultas, lista pacientes |

---

## RF — Requisitos Funcionais

### RF-01: Design System com Angular Material
QUANDO o usuário acessa qualquer tela, O SISTEMA DEVE renderizar UI com Angular Material 21
(Material Design 3), incluindo tema de cores customizado para saúde (azul primário + verde secundário).
**Critério de aceite:** `ng build` sem erros; todas as telas usam componentes `mat-*`.

### RF-02: Shell Responsivo
O SISTEMA DEVE exibir sidebar colapsável via `mat-sidenav`, com modo `over` em telas < 768px
e modo `side` em telas ≥ 768px. Header com breadcrumb dinâmico e nome do estabelecimento ativo.
**Critério de aceite:** Sidebar abre/fecha em mobile; breadcrumb reflete rota atual.

### RF-03: Feedback Visual Global
QUANDO qualquer operação assíncrona ocorrer, O SISTEMA DEVE:
- Mostrar `mat-progress-bar` no topo (loading global)
- Exibir `MatSnackBar` de sucesso (verde) ou erro (vermelho) por 4 segundos
- Mostrar skeleton loaders em tabelas enquanto carrega
**Critério de aceite:** Toda operação async tem indicador visual antes e após.

### RF-04: Módulo Pacientes
QUANDO ADMIN_ESTABELECIMENTO ou RECEPCIONISTA acessa `/pacientes`, O SISTEMA DEVE:
- Listar pacientes em `mat-table` com paginação (MatPaginator), busca por nome/CPF
- Exibir CPF mascarado conforme vem da API (`123.***.***.89`)
- Permitir editar nome, telefone, email, convênio
- Mostrar empty state ilustrado quando não há pacientes
**Critério de aceite:** GET `/v1/pacientes/` carrega; edição via PATCH funciona.

### RF-05: Módulo Especialidades
QUANDO ADMIN_ESTABELECIMENTO acessa `/especialidades`, O SISTEMA DEVE:
- Listar especialidades em cards coloridos (usando `cor_hex` da API)
- Permitir criar, editar e desativar especialidades
- Exibir ícone personalizado por especialidade
- Formulário com seletor de cor via `<input type="color">`
**Critério de aceite:** CRUD completo em `/v1/especialidades/` funciona.

### RF-06: Geração de Slots de Agenda
QUANDO ADMIN_ESTABELECIMENTO clica em "Gerar Agenda" na tela de médicos, O SISTEMA DEVE:
- Abrir `mat-dialog` com formulário: data início/fim, hora início/fim, intervalo almoço, dias da semana
- Validar que data fim ≥ data início
- Chamar `POST /v1/medicos/{id}/slots` e mostrar quantidade de slots criados
**Critério de aceite:** Dialog abre; slots são criados e contagem é exibida.

### RF-07: Módulo Estabelecimentos (ADMIN_GLOBAL)
QUANDO ADMIN_GLOBAL acessa `/estabelecimentos`, O SISTEMA DEVE:
- Listar todos os estabelecimentos em tabela com: nome, tipo, plano, status licença, cidade
- Permitir criar novo estabelecimento com formulário completo (CNPJ, endereço, responsável)
- Permitir editar estabelecimento existente
- Clicar em linha abre detalhes com abas: Dados | Licença | Médicos (count)
**Critério de aceite:** CRUD completo em `/v1/estabelecimentos/` funciona; só visível para ADMIN_GLOBAL.

### RF-08: Módulo Licenças (ADMIN_GLOBAL)
QUANDO ADMIN_GLOBAL acessa detalhes de estabelecimento > aba Licença, O SISTEMA DEVE:
- Exibir status atual (TRIAL/ATIVA/EXPIRADA/SUSPENSA) com badge colorido
- Mostrar dias restantes e quotas utilizadas (médicos, consultas/mês)
- Permitir atualizar plano, status, adicionar meses, registrar motivo de suspensão
**Critério de aceite:** PATCH `/v1/admin/licenca/{id}` funciona; status atualiza em tempo real.

### RF-09: Minha Licença (ADMIN_ESTABELECIMENTO)
QUANDO ADMIN_ESTABELECIMENTO acessa `/minha-licenca`, O SISTEMA DEVE:
- Exibir painel com plano atual, status, dias restantes
- Mostrar barras de progresso para quotas: médicos ativos / máximo, consultas mês / máximo
- Exibir alert quando licença expira em ≤ 7 dias
**Critério de aceite:** GET `/v1/licenca/minha` carrega; progresso correto; alert visível.

### RF-10: Módulo RAG — Documentos
QUANDO ADMIN_ESTABELECIMENTO acessa `/documentos`, O SISTEMA DEVE:
- Exibir formulário para upload de protocolo/documento (título + texto)
- Chamar `POST /v1/rag/documentos` e mostrar chunks indexados
- Mostrar status do Qdrant via `GET /v1/rag/health`
**Critério de aceite:** Documento é indexado; chunks count é exibido; health badge verde/vermelho.

### RF-11: Consultas — Listagem e Cancelamento
QUANDO ADMIN_ESTABELECIMENTO ou RECEPCIONISTA acessa `/consultas`, O SISTEMA DEVE:
- Listar consultas com filtros: status, urgência, data, canal origem
- Badge de urgência colorido (BAIXA=cinza, MEDIA=amarelo, ALTA=laranja, EMERGENCIA=vermelho)
- Permitir cancelar consulta com dialog de motivo obrigatório (mín. 3 chars)
- Exibir resumo da triagem IA (se disponível) em painel expansível
**Critério de aceite:** Listagem carrega; cancelamento via PATCH funciona; filtros funcionam.

### RF-12: Melhorias Dashboard
O SISTEMA DEVE no Dashboard existente:
- Adicionar seletor de data (MatDatepicker) para navegar entre dias
- Exibir card "Consultas por Canal" (PORTAL / WHATSAPP / INTERNO) em gráfico doughnut
- Mostrar card de status da licença com link para `/minha-licenca`
**Critério de aceite:** Trocar data recarrega KPIs; gráfico canal é exibido.

### RF-13: Melhorias Agenda
O SISTEMA DEVE na Agenda existente:
- Adicionar mini-calendário lateral para selecionar data (MatDatepicker inline)
- Colorir slots por status (DISPONIVEL=verde, AGENDADO=azul, BLOQUEADO=cinza)
- Adicionar botão "Gerar Agenda" que abre dialog (RF-06)
- Filtro por especialidade além do filtro por médico já existente
**Critério de aceite:** Cores refletem status; "Gerar Agenda" abre dialog.

### RF-14: Melhorias Médicos
O SISTEMA DEVE na tela de Médicos:
- Substituir form modal inline por `mat-dialog` com `ReactiveFormsModule`
- Adicionar avatar gerado por iniciais (Material avatar)
- Exibir especialidade como chip colorido
- Botão "Gerar Agenda" por médico na tabela
**Critério de aceite:** Dialog com ReactiveFormsModule funciona; chips exibem cor da especialidade.

---

## RNF — Requisitos Não Funcionais

### RNF-01: Performance
O SISTEMA DEVE renderizar qualquer listagem em < 500ms após resposta da API.
Usar `trackBy` em todos os `@for`. Lazy loading em todos os módulos.

### RNF-02: Acessibilidade
O SISTEMA DEVE ter aria-labels em todos os botões de ação. Navegação por teclado funcional.
Contraste mínimo AA (WCAG 2.1).

### RNF-03: Segurança
O SISTEMA NÃO DEVE exibir telas ADMIN_GLOBAL para usuários com role diferente.
Menus devem ser filtrados por role no sidebar.

### RNF-04: Código
- Zero `console.log()` em produção
- Zero `any` implícito (TypeScript strict)
- Todos os componentes: `standalone: true` + `ChangeDetectionStrategy.OnPush`
- Signals para estado local, Observables apenas para HTTP
- SCSS modular com `@use`, sem `@import`

---

## Comportamentos Proibidos

- NUNCA exibir token JWT ou dados sensíveis em template
- NUNCA acessar endpoint ADMIN_GLOBAL sem verificar role no guard
- NUNCA usar `ngModel` em forms complexos — usar ReactiveFormsModule
- NUNCA mostrar CPF completo — sempre a versão mascarada da API

---

## Casos de Borda

| Situação | Comportamento |
|---|---|
| API retorna 402 (quota atingida) | Snackbar "Limite do plano atingido. Contate o suporte." |
| API retorna 403 (licença suspensa) | Redireciona para `/minha-licenca` com alert |
| Lista vazia | Empty state com ícone Material + botão CTA |
| Formulário com erro de validação | Highlight mat-form-field + mat-error inline |
| Perda de conexão | Snackbar "Sem conexão. Tente novamente." |

---

## Fora de Escopo

- Chat em tempo real no admin (isso é o portal do paciente)
- Relatórios avançados / BI (BACKLOG G16)
- Multi-tenant BotFlow (BACKLOG G17)
- App mobile (Capacitor)

---

## Critérios de Aceite Globais

- [ ] `ng build` sem erros nem warnings
- [ ] Todos os endpoints mapeados têm tela correspondente
- [ ] Angular Material instalado e tema customizado configurado
- [ ] Sidebar filtra itens de menu por role
- [ ] Loading state em toda operação async
- [ ] Snackbar em toda operação de escrita (sucesso + erro)
- [ ] Empty states em todas as tabelas
- [ ] Zero `any` implícito
- [ ] Zero `console.log()`
