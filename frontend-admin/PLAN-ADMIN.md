# PLAN — Frontend Admin MedBot (G18)
> Derivado de: SPEC-ADMIN.md | Stack: Angular 21 + Angular Material 21
> Status: AGUARDANDO APROVAÇÃO

---

## Stack Fixada (CONSTITUTION.md)

| Tecnologia | Versão | Uso |
|---|---|---|
| Angular | 21.2.x | Framework + standalone components |
| Angular Material | 21.2.x | UI components (mat-table, mat-dialog, mat-sidenav...) |
| Angular CDK | 21.2.x | Dialog, overlay, drag-drop |
| TypeScript | ~5.9 | Strict mode |
| RxJS | ~7.8 | HTTP + interop com Signals |
| Chart.js | ^4.4 | Gráficos (já instalado) |
| Vitest | via @analogjs | Testes unitários |

---

## ADR-038: Angular Material em vez de CSS customizado

- **Contexto:** G8 foi construído com CSS artesanal — não escalável para >10 telas
- **Decisão:** Instalar `@angular/material` + `@angular/cdk`, usar tema Material Design 3 com paleta saúde
- **Justificativa:** Componentes acessíveis out-of-the-box, dark/light mode via tokens CSS, menos código
- **Trade-off:** ~250KB bundle adicional (aceitável para admin)

---

## ADR-039: Reactive Forms para formulários complexos

- **Contexto:** Formulários de Estabelecimento (15+ campos) e Licença inviáveis com template-driven
- **Decisão:** Usar `ReactiveFormsModule` com `FormBuilder` para forms de criação/edição
- **Justificativa:** Validação tipada, dirty/pristine tracking, disable/enable de campos por role
- **Trade-off:** Mais boilerplate — mitigado por helper `fb.group()`

---

## ADR-040: ToastService centralizado

- **Contexto:** Toda operação async precisa de feedback — código duplicado se cada componente instancia MatSnackBar
- **Decisão:** `ToastService` singleton que encapsula MatSnackBar com métodos `sucesso(msg)`, `erro(msg)`, `aviso(msg)`
- **Justificativa:** Consistência visual, fácil de testar (mock único)
- **Trade-off:** Nenhum relevante

---

## Arquitetura de Componentes

```
frontend-admin/src/app/
├── core/
│   ├── guards/
│   │   └── auth.guard.ts              (existente — manter)
│   ├── interceptors/
│   │   └── auth.interceptor.ts        (mover de services/ para interceptors/)
│   └── services/
│       ├── api.service.ts             (existente — manter)
│       ├── auth-admin.service.ts      (existente — manter)
│       ├── agenda-admin.service.ts    (existente — manter)
│       ├── dashboard.service.ts       (existente — melhorar)
│       └── toast.service.ts           (NOVO — wraps MatSnackBar)
├── shared/
│   ├── shell/
│   │   ├── shell.component.*          (refatorar — mat-sidenav)
│   │   └── breadcrumb.component.*     (NOVO)
│   ├── components/
│   │   ├── empty-state/               (NOVO — reusável)
│   │   ├── confirm-dialog/            (NOVO — mat-dialog genérico)
│   │   └── page-header/               (NOVO — título + ações)
│   └── pipes/
│       └── status-label.pipe.ts       (NOVO — traduz enums para PT-BR)
├── features/
│   ├── auth/                          (existente — adicionar Material)
│   ├── dashboard/                     (existente — melhorar RF-12)
│   ├── agenda/                        (existente — melhorar RF-13)
│   ├── medicos/                       (existente — melhorar RF-14)
│   ├── billing/                       (existente — manter)
│   ├── especialidades/                (NOVO — RF-05)
│   ├── pacientes/                     (NOVO — RF-04)
│   ├── consultas/                     (NOVO — RF-11)
│   ├── estabelecimentos/              (NOVO — RF-07, ADMIN_GLOBAL)
│   ├── licenca/                       (NOVO — RF-08 + RF-09)
│   ├── documentos/                    (NOVO — RF-10, RAG)
│   └── selecionar-estabelecimento/    (existente — melhorar com Material)
└── models/
    ├── paciente.model.ts              (NOVO — centralizar interfaces)
    ├── especialidade.model.ts         (NOVO)
    ├── estabelecimento.model.ts       (NOVO)
    ├── licenca.model.ts               (NOVO)
    └── consulta.model.ts              (NOVO)
```

---

## Rotas Completas

```typescript
// Rotas públicas
{ path: 'login', loadComponent: () => LoginComponent }

// ADMIN_GLOBAL — seleção de estabelecimento
{ path: 'selecionar-estabelecimento', canActivate: [authGuard], ... }

// Shell (requer auth)
{
  path: '', component: ShellComponent, canActivate: [authGuard],
  children: [
    // Todos os usuários autenticados
    { path: 'dashboard',      loadComponent: DashboardComponent },
    { path: 'agenda',         loadComponent: AgendaComponent },
    { path: 'medicos',        loadComponent: MedicosComponent },
    { path: 'especialidades', loadComponent: EspecialidadesComponent },
    { path: 'pacientes',      loadComponent: PacientesComponent },
    { path: 'consultas',      loadComponent: ConsultasComponent },
    { path: 'billing',        loadComponent: BillingComponent },
    { path: 'billing/config', loadComponent: BillingConfigComponent },
    { path: 'minha-licenca',  loadComponent: MinhaLicencaComponent },
    { path: 'documentos',     loadComponent: DocumentosComponent },

    // ADMIN_GLOBAL apenas
    { path: 'estabelecimentos',        loadComponent: EstabelecimentosComponent },
    { path: 'estabelecimentos/:id',    loadComponent: EstabelecimentoDetalheComponent },

    { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
  ]
}
```

---

## Tema Angular Material

```scss
// styles.scss
@use '@angular/material' as mat;

$medbot-primary: mat.define-theme((
  color: (
    theme-type: light,
    primary: mat.$azure-palette,
    tertiary: mat.$green-palette,
  ),
  typography: (
    brand-family: 'Inter, sans-serif',
    plain-family: 'Inter, sans-serif',
  ),
  density: (scale: 0),
));

html {
  @include mat.all-component-themes($medbot-primary);
}

// Dark mode
@media (prefers-color-scheme: dark) {
  $medbot-dark: mat.define-theme((color: (theme-type: dark, primary: mat.$azure-palette)));
  html { @include mat.all-component-colors($medbot-dark); }
}
```

---

## Sidebar — Items por Role

```typescript
type NavItem = { path: string; label: string; icon: string; roles: string[] };

const NAV_ITEMS: NavItem[] = [
  // Todos
  { path: '/dashboard',      label: 'Dashboard',      icon: 'dashboard',    roles: ['*'] },
  { path: '/agenda',         label: 'Agenda',          icon: 'calendar_month', roles: ['*'] },
  { path: '/consultas',      label: 'Consultas',       icon: 'event_note',   roles: ['*'] },
  { path: '/medicos',        label: 'Médicos',         icon: 'medical_services', roles: ['ADMIN_ESTABELECIMENTO', 'ADMIN_GLOBAL'] },
  { path: '/especialidades', label: 'Especialidades',  icon: 'category',     roles: ['ADMIN_ESTABELECIMENTO', 'ADMIN_GLOBAL'] },
  { path: '/pacientes',      label: 'Pacientes',       icon: 'group',        roles: ['*'] },
  // Admin
  { path: '/billing',        label: 'Billing IA',      icon: 'payments',     roles: ['ADMIN_ESTABELECIMENTO', 'ADMIN_GLOBAL'] },
  { path: '/minha-licenca',  label: 'Minha Licença',   icon: 'verified',     roles: ['ADMIN_ESTABELECIMENTO'] },
  { path: '/documentos',     label: 'Documentos RAG',  icon: 'description',  roles: ['ADMIN_ESTABELECIMENTO', 'ADMIN_GLOBAL'] },
  // ADMIN_GLOBAL exclusivo
  { path: '/estabelecimentos', label: 'Estabelecimentos', icon: 'business', roles: ['ADMIN_GLOBAL'] },
];
```

---

## APIs mapeadas por Feature

| Tela | Endpoints |
|---|---|
| Dashboard | GET /billing/dashboard, GET /billing/dashboard/modelos |
| Agenda | GET /agenda/slots/dia/{data}, GET /medicos/, GET /especialidades/ |
| Médicos | GET/POST/PATCH/DELETE /medicos/, POST /medicos/{id}/slots |
| Especialidades | GET/POST/PATCH/DELETE /especialidades/ |
| Pacientes | GET/PATCH /pacientes/, GET /pacientes/{id} |
| Consultas | GET /agenda/consultas/paciente/{id}, PATCH /agenda/consultas/{id}/cancelar |
| Billing | GET/PATCH /billing/config, GET /billing/dashboard, GET /billing/export |
| Minha Licença | GET /licenca/minha |
| Documentos RAG | POST /rag/documentos, GET /rag/health |
| Estabelecimentos | GET/POST/PATCH/DELETE /estabelecimentos/ |
| Licença (Admin) | PATCH /admin/licenca/{id} |

---

## Componentes Shared Reutilizáveis

### EmptyStateComponent
```typescript
// Inputs: icon (string), title (string), description (string), ctaLabel? (string)
// Output: ctaClick (EventEmitter)
// Uso: <app-empty-state icon="group" title="Nenhum paciente" [ctaLabel]="'Adicionar'" />
```

### ConfirmDialogComponent
```typescript
// Usado via MatDialog.open(ConfirmDialogComponent, { data: { titulo, mensagem, confirmLabel } })
// Retorna: true (confirmou) | false (cancelou)
```

### PageHeaderComponent
```typescript
// Inputs: titulo (string), subtitulo? (string)
// Content projection: ng-content para botões de ação
// Uso: <app-page-header titulo="Médicos"><button mat-raised-button>Novo</button></app-page-header>
```

---

## Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| Bundle size aumentar muito com Material | Tree-shaking automático — importar apenas módulos usados |
| Breaking change nos componentes existentes | Manter CSS customizado como fallback durante transição |
| Tema Material conflitar com estilos existentes | Usar encapsulação SCSS por componente |
| Consultas sem paciente_id (agendamentos via chat) | Rota `/v1/agenda/consultas` não existe — usar `/agenda/slots/dia` + filtro AGENDADO |
