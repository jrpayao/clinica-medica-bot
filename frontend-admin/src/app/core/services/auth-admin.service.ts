import { Injectable, inject, signal, computed } from '@angular/core';
import { ApiService } from './api.service';
import { firstValueFrom } from 'rxjs';

export interface AdminUser {
  id: number;
  nome: string;
  email: string;
  role: 'RECEPCIONISTA' | 'MEDICO' | 'ADMIN' | 'ADMIN_GLOBAL' | 'ADMIN_ESTABELECIMENTO';
  estabelecimentoId: number | null;
}

@Injectable({ providedIn: 'root' })
export class AuthAdminService {
  private readonly api = inject(ApiService);
  private readonly TOKEN_KEY      = 'admin_token';
  private readonly SUPERADMIN_KEY = 'admin_superadmin_mode';
  private readonly FILTRO_EST_KEY = 'admin_filtro_est_id';

  private readonly _token = signal<string | null>(
    typeof localStorage !== 'undefined' ? localStorage.getItem(this.TOKEN_KEY) : null
  );
  readonly estaAutenticado = signal(this._token() !== null);
  readonly usuario = signal<AdminUser | null>(null);

  /** Flag: ADMIN_GLOBAL optou por não selecionar estabelecimento (modo super admin) */
  private readonly _modoSuperAdmin = signal(
    typeof sessionStorage !== 'undefined'
      ? sessionStorage.getItem(this.SUPERADMIN_KEY) === '1'
      : false
  );
  readonly modoSuperAdmin = this._modoSuperAdmin.asReadonly();

  /**
   * Filtro global de estabelecimento para ADMIN_GLOBAL em modo global.
   * Persiste durante a sessão via sessionStorage.
   * JWT scoped (estabelecimentoId no usuario) tem prioridade sobre este valor.
   */
  private readonly _estabelecimentoFiltroId = signal<number | null>(
    typeof sessionStorage !== 'undefined'
      ? (() => {
          const v = sessionStorage.getItem('admin_filtro_est_id');
          return v ? parseInt(v, 10) : null;
        })()
      : null
  );

  /**
   * ID do estabelecimento ativo:
   *   1. JWT com est_id (scoped token ou ADMIN_ESTABELECIMENTO)
   *   2. Filtro global selecionado no toolbar (ADMIN_GLOBAL modo global)
   *   3. null → nenhum estabelecimento selecionado
   */
  readonly estabelecimentoAtivoId = computed<number | null>(
    () => this.usuario()?.estabelecimentoId ?? this._estabelecimentoFiltroId() ?? null
  );

  /** ADMIN_GLOBAL sem estabelecimento ativo (nem JWT nem filtro global) */
  readonly semEstabelecimento = computed(
    () => this.usuario()?.role === 'ADMIN_GLOBAL' && this.estabelecimentoAtivoId() === null
  );

  /** ADMIN_GLOBAL sem estabelecimento e sem ter optado pelo modo super admin → forçar seleção */
  readonly precisaSelecionarEstabelecimento = computed(() => {
    const u = this.usuario();
    return u?.role === 'ADMIN_GLOBAL'
      && u?.estabelecimentoId === null
      && !this._modoSuperAdmin();
  });

  constructor() {
    // Restaurar usuário do token persistido no localStorage
    const token = this._token();
    if (token) {
      this._aplicarToken(token, null);
    }
  }

  async login(email: string, senha: string): Promise<void> {
    const res = await firstValueFrom(
      this.api.post<{ access_token: string; refresh_token: string; token_type: string }>(
        '/auth/login',
        { email, senha }
      )
    );
    localStorage.setItem(this.TOKEN_KEY, res.access_token);
    this._token.set(res.access_token);
    this.estaAutenticado.set(true);
    this._aplicarToken(res.access_token, email);
  }

  async selecionarEstabelecimento(estabelecimentoId: number): Promise<void> {
    const res = await firstValueFrom(
      this.api.post<{ access_token: string; token_type: string; estabelecimento_id: number }>(
        '/admin/selecionar-estabelecimento',
        { estabelecimento_id: estabelecimentoId }
      )
    );
    localStorage.setItem(this.TOKEN_KEY, res.access_token);
    this._token.set(res.access_token);
    // JWT agora tem est_id — limpar filtro global (redundante)
    this._limparFiltroGlobal();
    this._aplicarToken(res.access_token, null);
  }

  /** ADMIN_GLOBAL seleciona estabelecimento via toolbar (modo global, sem trocar JWT). */
  selecionarFiltroGlobal(id: number | null): void {
    if (id !== null) {
      sessionStorage.setItem(this.FILTRO_EST_KEY, String(id));
    } else {
      sessionStorage.removeItem(this.FILTRO_EST_KEY);
    }
    this._estabelecimentoFiltroId.set(id);
  }

  /** ADMIN_GLOBAL volta ao modo global — emite novo token sem estabelecimento_id. */
  async voltarModoGlobal(): Promise<void> {
    const res = await firstValueFrom(
      this.api.post<{ access_token: string }>('/admin/modo-global', {})
    );
    localStorage.setItem(this.TOKEN_KEY, res.access_token);
    this._token.set(res.access_token);
    this._limparFiltroGlobal();
    this._aplicarToken(res.access_token, null);
    sessionStorage.setItem(this.SUPERADMIN_KEY, '1');
    this._modoSuperAdmin.set(true);
  }

  /** @deprecated Usar voltarModoGlobal() — mantido para retrocompatibilidade. */
  continuarComoSuperAdmin(): void {
    sessionStorage.setItem(this.SUPERADMIN_KEY, '1');
    this._modoSuperAdmin.set(true);
  }

  logout(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    sessionStorage.removeItem(this.SUPERADMIN_KEY);
    this._limparFiltroGlobal();
    this._token.set(null);
    this._modoSuperAdmin.set(false);
    this.estaAutenticado.set(false);
    this.usuario.set(null);
  }

  private _limparFiltroGlobal(): void {
    sessionStorage.removeItem(this.FILTRO_EST_KEY);
    this._estabelecimentoFiltroId.set(null);
  }

  getToken(): string | null {
    return this._token();
  }

  private _aplicarToken(token: string, emailFallback: string | null): void {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      this.usuario.set({
        id: Number(payload.sub),
        nome: payload.nome ?? payload.email?.split('@')[0] ?? 'Admin',
        email: payload.email ?? emailFallback ?? '',
        role: payload.role ?? 'ADMIN',
        estabelecimentoId: payload.estabelecimento_id ?? null,
      });
    } catch {
      this.usuario.set({
        id: 0,
        nome: 'Admin',
        email: emailFallback ?? '',
        role: 'ADMIN',
        estabelecimentoId: null,
      });
    }
  }
}
