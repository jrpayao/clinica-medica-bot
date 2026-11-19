import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'auth',
    pathMatch: 'full',
  },
  {
    path: 'auth',
    loadComponent: () =>
      import('./features/auth/auth.component').then((m) => m.AuthComponent),
  },
  {
    path: 'chat',
    loadComponent: () =>
      import('./features/chat/chat.component').then((m) => m.ChatComponent),
  },
  {
    path: 'teleconsulta/:token',
    loadComponent: () =>
      import('./features/teleconsulta/teleconsulta.component').then((m) => m.TeleconsultaComponent),
  },
  {
    path: 'agendamentos',
    loadComponent: () =>
      import('./features/agendamentos/agendamentos.component').then(
        (m) => m.AgendamentosComponent
      ),
  },
];
