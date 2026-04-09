import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';

export interface PlataformaDashboard {
  data: string;
  estabelecimentos: { total: number; ativos: number; inativos: number };
  licencas_por_status: Record<string, number>;
  usuarios_por_role: Record<string, number>;
  consultas_hoje: { agendadas: number; realizadas: number; canceladas: number };
  alertas: Array<{ tipo: string; mensagem: string; contagem: number; link: string }>;
}

@Injectable({ providedIn: 'root' })
export class PlataformaService {
  private readonly api = inject(ApiService);

  readonly kpi     = signal<PlataformaDashboard | null>(null);
  readonly loading = signal(false);
  readonly erro    = signal<string | null>(null);

  async carregar(): Promise<void> {
    this.loading.set(true);
    this.erro.set(null);
    try {
      const data = await firstValueFrom(
        this.api.get<PlataformaDashboard>('/admin/plataforma/dashboard')
      );
      this.kpi.set(data);
    } catch (e: unknown) {
      this.erro.set('Erro ao carregar dashboard');
    } finally {
      this.loading.set(false);
    }
  }
}
