import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from '../../core/services/api.service';
import { environment } from '../../environments/environment';
import { firstValueFrom } from 'rxjs';

export interface ResumoModelo {
  modelo: string;
  total_chamadas: number;
  total_tokens: number;
  custo_total: number;
}

export interface ResumoFeature {
  feature: string;
  total_chamadas: number;
  total_tokens: number;
  custo_total: number;
}

export interface LimitesInfo {
  diario_usd: number;
  mensal_usd: number;
  custo_atual_usd: number;
  percentual_usado: number;
}

export interface BillingDashboard {
  resumo: Record<string, unknown>;
  por_modelo: ResumoModelo[];
  por_feature: ResumoFeature[];
  limites: LimitesInfo;
  filtro_estabelecimento_id: number | null;
}

export interface RankingEstabelecimento {
  estabelecimento_id: number;
  nome: string;
  total_chamadas: number;
  total_tokens: number;
  custo_total: number;
}

@Injectable({ providedIn: 'root' })
export class BillingService {
  private readonly api = inject(ApiService);

  readonly dashboard   = signal<BillingDashboard | null>(null);
  readonly ranking     = signal<RankingEstabelecimento[]>([]);
  readonly carregando  = signal(false);
  readonly carregandoRanking = signal(false);
  readonly erro        = signal<string | null>(null);

  async carregar(data?: string, estabelecimentoId?: number | null): Promise<void> {
    this.carregando.set(true);
    this.erro.set(null);
    try {
      const params = new URLSearchParams();
      if (data) params.set('data', data);
      if (estabelecimentoId != null) params.set('estabelecimento_id', String(estabelecimentoId));
      const qs = params.toString();
      const res = await firstValueFrom(
        this.api.get<BillingDashboard>(`/billing/dashboard${qs ? '?' + qs : ''}`)
      );
      this.dashboard.set(res);
    } catch {
      this.erro.set('Erro ao carregar dados de billing.');
    } finally {
      this.carregando.set(false);
    }
  }

  async carregarRanking(data?: string): Promise<void> {
    this.carregandoRanking.set(true);
    try {
      const params = data ? `?data=${data}` : '';
      const res = await firstValueFrom(
        this.api.get<RankingEstabelecimento[]>(`/billing/por-estabelecimento${params}`)
      );
      this.ranking.set(res);
    } catch {
      // ranking é best-effort — não bloqueia o dashboard
    } finally {
      this.carregandoRanking.set(false);
    }
  }

  exportarCsvUrl(inicio?: string, fim?: string, estabelecimentoId?: number | null): string {
    const params = new URLSearchParams();
    if (inicio) params.set('inicio', inicio);
    if (fim)    params.set('fim', fim);
    if (estabelecimentoId != null) params.set('estabelecimento_id', String(estabelecimentoId));
    const qs = params.toString();
    return `${environment.apiUrl}/billing/export${qs ? '?' + qs : ''}`;
  }
}
