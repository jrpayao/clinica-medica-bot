import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router, NavigationEnd } from '@angular/router';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { filter, map } from 'rxjs/operators';
import { toSignal } from '@angular/core/rxjs-interop';

import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';

import { AuthAdminService } from '../../core/services/auth-admin.service';
import { DashboardService } from '../../core/services/dashboard.service';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  modos: Array<'global' | 'escopado' | 'estabelecimento' | '*'>;
}

const NAV_ITEMS: NavItem[] = [
  // ── Modo global (ADMIN_GLOBAL sem clínica) ──────────────────────
  { path: '/platform-dashboard', label: 'Dashboard',        icon: 'dashboard',        modos: ['global'] },
  { path: '/dashboard',          label: 'Dashboard',        icon: 'dashboard',        modos: ['escopado', 'estabelecimento'] },
  { path: '/estabelecimentos',   label: 'Estabelecimentos', icon: 'business',         modos: ['global'] },
  { path: '/licencas',           label: 'Licenças',         icon: 'verified',         modos: ['global'] },
  { path: '/usuarios',           label: 'Usuários',         icon: 'manage_accounts',  modos: ['global', 'estabelecimento'] },
  { path: '/billing',            label: 'Billing Global',   icon: 'payments',         modos: ['global'] },
  { path: '/auditoria',          label: 'Auditoria',        icon: 'history',          modos: ['global'] },

  // ── Modo escopado (ADMIN_GLOBAL dentro de uma clínica) ──────────
  { path: '/agenda',             label: 'Agenda',           icon: 'calendar_month',   modos: ['escopado', 'estabelecimento'] },
  { path: '/atendimentos',       label: 'Atendimentos',     icon: 'event_note',       modos: ['escopado', 'estabelecimento'] },
  { path: '/clientes',           label: 'Clientes',         icon: 'group',            modos: ['escopado', 'estabelecimento'] },
  { path: '/profissionais',      label: 'Profissionais',    icon: 'medical_services', modos: ['escopado', 'estabelecimento'] },
  { path: '/especialidades',     label: 'Especialidades',   icon: 'category',         modos: ['escopado', 'estabelecimento'] },
  { path: '/convenios',          label: 'Convênios',        icon: 'health_and_safety', modos: ['escopado', 'estabelecimento'] },
  { path: '/billing',            label: 'Billing IA',       icon: 'payments',         modos: ['escopado'] },
  { path: '/documentos',         label: 'Documentos RAG',   icon: 'description',      modos: ['escopado', 'estabelecimento'] },

  // ── Apenas ADMIN_ESTABELECIMENTO ────────────────────────────────
  { path: '/minha-licenca',      label: 'Minha Licença',    icon: 'verified',         modos: ['estabelecimento'] },
];

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterOutlet, RouterLink, RouterLinkActive,
    ReactiveFormsModule,
    MatSidenavModule, MatToolbarModule, MatIconModule,
    MatButtonModule, MatTooltipModule, MatDividerModule,
    MatMenuModule, MatSelectModule, MatFormFieldModule,
  ],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ShellComponent implements OnInit {
  readonly auth = inject(AuthAdminService);
  readonly ds   = inject(DashboardService);
  private readonly router = inject(Router);

  /** Sidebar aberta em mobile (< 768px) */
  readonly sidebarAberta = signal(false);

  /** true quando a janela é larga o suficiente para sidebar fixa */
  readonly isDesktop = signal(window.innerWidth >= 768);

  @HostListener('window:resize')
  onResize(): void {
    this.isDesktop.set(window.innerWidth >= 768);
    if (this.isDesktop()) this.sidebarAberta.set(false);
  }

  /** Modo do sidenav: 'side' em desktop, 'over' em mobile */
  readonly sidenavMode = computed(() => (this.isDesktop() ? 'side' : 'over'));

  /** Sidenav aberta: sempre em desktop, controlada em mobile */
  readonly sidenavOpened = computed(() => this.isDesktop() || this.sidebarAberta());

  /** Nome do título da rota ativa */
  readonly tituloPagina = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map(() => {
        const url = this.router.url.split('?')[0].split('/')[1] ?? '';
        return NAV_ITEMS.find((n) => n.path === '/' + url)?.label ?? 'MedBot Admin';
      }),
    ),
    { initialValue: 'Dashboard' },
  );

  /** Itens de menu filtrados pela role e modo do usuário logado */
  readonly navItemsFiltrados = computed(() => {
    const role = this.auth.usuario()?.role ?? '';
    const modoGlobal = this.isModoGlobal();
    const modoEscopado = this.isModoEscopado();

    return NAV_ITEMS.filter((item) => {
      if (role === 'ADMIN_GLOBAL' && modoGlobal)   return item.modos.includes('global');
      if (role === 'ADMIN_GLOBAL' && modoEscopado) return item.modos.includes('escopado');
      if (role === 'ADMIN_ESTABELECIMENTO')        return item.modos.includes('estabelecimento');
      return false;
    });
  });

  /** True quando ADMIN_GLOBAL está em modo global (sem estabelecimento ativo — nem JWT nem filtro do toolbar) */
  readonly isModoGlobal = computed(
    () => this.auth.usuario()?.role === 'ADMIN_GLOBAL' && !this.auth.estabelecimentoAtivoId()
  );

  /** True quando ADMIN_GLOBAL opera dentro de um estabelecimento (JWT escopado OU filtro do toolbar selecionado) */
  readonly isModoEscopado = computed(
    () => this.auth.usuario()?.role === 'ADMIN_GLOBAL' && !!this.auth.estabelecimentoAtivoId()
  );

  /** Ctrl do seletor de estabelecimento no toolbar (modo global) */
  readonly filtroEstCtrl = new FormControl<number | null>(null);

  /** Nome do estabelecimento ativo para exibir no toolbar (modo escopado) */
  readonly nomeEstabelecimentoAtivo = computed(() => {
    const id = this.auth.estabelecimentoAtivoId();
    if (!id) return null;
    return this.ds.estabelecimentos().find((e) => e.id === id)?.nome ?? `#${id}`;
  });

  async ngOnInit(): Promise<void> {
    if (this.auth.usuario()?.role === 'ADMIN_GLOBAL') {
      await this.ds.carregarEstabelecimentos();
      // Sincronizar seletor com filtro persistido na sessão
      this.filtroEstCtrl.setValue(this.auth.estabelecimentoAtivoId(), { emitEvent: false });
    }

    this.filtroEstCtrl.valueChanges.subscribe((id) => {
      this.auth.selecionarFiltroGlobal(id);
    });
  }

  toggleSidebar(): void {
    this.sidebarAberta.update((v) => !v);
  }

  async trocarEstabelecimento(): Promise<void> {
    try {
      await this.auth.voltarModoGlobal();
      // Sincronizar o FormControl com o estado limpo — evita desync filtroEstCtrl vs _estabelecimentoFiltroId
      this.filtroEstCtrl.setValue(null, { emitEvent: false });
    } catch {
      this.router.navigate(['/selecionar-estabelecimento']);
    }
  }

  irParaSelecao(): void {
    this.router.navigate(['/selecionar-estabelecimento']);
  }

  sair(): void {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
