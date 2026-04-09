import { Injectable, inject, signal, computed } from '@angular/core';
import { ApiService } from './api.service';
import { firstValueFrom } from 'rxjs';

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface SmsResponse {
  mensagem: string;
  ttl_segundos: number;
  dev_codigo?: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);

  private readonly _token = signal<string | null>(
    typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') : null
  );

  readonly estaAutenticado = computed(() => !!this._token());

  async solicitarSms(cpf: string): Promise<SmsResponse> {
    const res = await firstValueFrom(
      this.api.post<SmsResponse>('/auth/sms/request', { cpf })
    );
    return res;
  }

  async verificarSms(cpf: string, codigo: string): Promise<void> {
    const res = await firstValueFrom(
      this.api.post<TokenResponse>('/auth/sms/verify', { cpf, codigo })
    );
    this._salvarTokens(res);
  }

  async loginInterno(email: string, senha: string): Promise<void> {
    const res = await firstValueFrom(
      this.api.post<TokenResponse>('/auth/login', { email, senha })
    );
    this._salvarTokens(res);
  }

  getToken(): string | null {
    return this._token();
  }

  logout(): void {
    this._token.set(null);
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }

  private _salvarTokens(res: TokenResponse): void {
    this._token.set(res.access_token);
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('access_token', res.access_token);
      localStorage.setItem('refresh_token', res.refresh_token);
    }
  }
}
