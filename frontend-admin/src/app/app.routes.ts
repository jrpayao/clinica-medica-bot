import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'selecionar-estabelecimento',
    loadComponent: () =>
      import('./features/selecionar-estabelecimento/selecionar-estabelecimento.component').then(
        (m) => m.SelecionarEstabelecimentoComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: '',
    loadComponent: () =>
      import('./shared/shell/shell.component').then((m) => m.ShellComponent),
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },

      // ── Todos os roles ──────────────────────────────────────
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'agenda',
        loadComponent: () =>
          import('./features/agenda/agenda.component').then((m) => m.AgendaComponent),
      },
      {
        path: 'atendimentos',
        loadComponent: () =>
          import('./features/atendimentos/atendimentos.component').then((m) => m.AtendimentosComponent),
      },
      {
        path: 'clientes',
        loadComponent: () =>
          import('./features/clientes/clientes.component').then((m) => m.ClientesComponent),
      },

      // ── Admin + Global ──────────────────────────────────────
      {
        path: 'profissionais',
        loadComponent: () =>
          import('./features/profissionais/profissionais.component').then((m) => m.ProfissionaisComponent),
      },
      {
        path: 'especialidades',
        loadComponent: () =>
          import('./features/especialidades/especialidades.component').then(
            (m) => m.EspecialidadesComponent,
          ),
      },
      {
        path: 'billing',
        loadComponent: () =>
          import('./features/billing/billing.component').then((m) => m.BillingComponent),
      },
      {
        path: 'billing/config',
        loadComponent: () =>
          import('./features/billing/billing-config.component').then(
            (m) => m.BillingConfigComponent,
          ),
      },
      {
        path: 'documentos',
        loadComponent: () =>
          import('./features/documentos/documentos.component').then((m) => m.DocumentosComponent),
      },

      // ── Apenas ADMIN_ESTABELECIMENTO ────────────────────────
      {
        path: 'minha-licenca',
        loadComponent: () =>
          import('./features/licenca/minha-licenca.component').then(
            (m) => m.MinhaLicencaComponent,
          ),
      },

      // ── Apenas ADMIN_GLOBAL ─────────────────────────────────
      {
        path: 'estabelecimentos',
        loadComponent: () =>
          import('./features/estabelecimentos/estabelecimentos.component').then(
            (m) => m.EstabelecimentosComponent,
          ),
      },

      // ── G22: ADMIN_GLOBAL Platform (Tasks 8-11) ─────────────
      {
        path: 'platform-dashboard',
        loadComponent: () =>
          import('./features/platform-dashboard/platform-dashboard.component').then(
            (m) => m.PlatformDashboardComponent,
          ),
      },
      {
        path: 'licencas',
        loadComponent: () =>
          import('./features/licencas/licencas.component').then((m) => m.LicencasComponent),
      },
      {
        path: 'usuarios',
        loadComponent: () =>
          import('./features/usuarios/usuarios.component').then((m) => m.UsuariosComponent),
      },
      {
        path: 'auditoria',
        loadComponent: () =>
          import('./features/auditoria/auditoria.component').then((m) => m.AuditoriaComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
