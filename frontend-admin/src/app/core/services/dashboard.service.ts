import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from './api.service';
import { firstValueFrom } from 'rxjs';

export interface UsoModelo {
  modelo: string;
  total_tokens: number;
  custo_total: number;
  total_chamadas: number;
}

export interface ProximaConsulta {
  consulta_id: number;
  hora_inicio: string;
  cliente_nome: string;
  profissional_nome: string;
  especialidade_nome: string;
  urgencia: string;
  status: string;
}

export interface TaxaOcupacao {
  slots_ocupados: number;
  total_slots: number;
  percentual: number;
}

export interface Alerta {
  tipo: 'urgencia_alta' | 'pendente_confirmacao' | 'custo_alto' | string;
  mensagem: string;
  contagem: number;
  link: string;
}

export interface AdminDashboard {
  data: string;
  filtro_estabelecimento_id: number | null;
  total_consultas: number;
  consultas_agendadas: number;
  consultas_realizadas: number;
  consultas_canceladas: number;
  taxa_ocupacao: TaxaOcupacao;
  proximas_consultas: ProximaConsulta[];
  alertas: Alerta[];
  custo_ia_total: number;
  limite_diario: number;
  uso_modelos: UsoModelo[];
}

export interface EstabelecimentoResumo {
  id: number;
  nome: string;
  slug: string;
}

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly api = inject(ApiService);

  readonly dados          = signal<AdminDashboard | null>(null);
  readonly estabelecimentos = signal<EstabelecimentoResumo[]>([]);
  readonly carregando     = signal(false);

  kpi()             { return this.dados(); }
  usoModelos()      { return this.dados()?.uso_modelos ?? []; }
  proximas()        { return this.dados()?.proximas_consultas ?? []; }
  alertas()         { return this.dados()?.alertas ?? []; }
  taxaOcupacao()    { return this.dados()?.taxa_ocupacao ?? { slots_ocupados: 0, total_slots: 0, percentual: 0 }; }

  async carregar(data?: string, estabelecimentoId?: number | null): Promise<void> {
    this.carregando.set(true);
    try {
      const params = new URLSearchParams();
      if (data) params.set('data', data);
      if (estabelecimentoId != null) params.set('estabelecimento_id', String(estabelecimentoId));
      const qs = params.toString();
      const res = await firstValueFrom(
        this.api.get<AdminDashboard>(`/admin/dashboard${qs ? '?' + qs : ''}`)
      );
      this.dados.set(res);
    } finally {
      this.carregando.set(false);
    }
  }

  async carregarEstabelecimentos(): Promise<void> {
    try {
      const lista = await firstValueFrom(
        this.api.get<EstabelecimentoResumo[]>('/estabelecimentos/')
      );
      this.estabelecimentos.set(lista);
    } catch {
      // best-effort
    }
  }
}
