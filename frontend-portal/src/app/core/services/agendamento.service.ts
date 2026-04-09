import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from './api.service';
import { firstValueFrom } from 'rxjs';

export interface Consulta {
  id: number;
  slot_id: number;
  cliente_id: number;
  profissional_id: number;
  especialidade_id: number;
  tipo: string;
  status: string;
  triagem_resumo: Record<string, unknown> | null;
  urgencia: string;
  canal_origem: string;
  observacoes: string | null;
  created_at: string;
  updated_at: string;
}

@Injectable({ providedIn: 'root' })
export class AgendamentoService {
  private readonly api = inject(ApiService);

  readonly consultas = signal<Consulta[]>([]);
  readonly carregando = signal(false);

  async listarPorPaciente(pacienteId: number): Promise<void> {
    this.carregando.set(true);
    try {
      const res = await firstValueFrom(
        this.api.get<Consulta[]>(`/agenda/consultas/paciente/${pacienteId}`)
      );
      this.consultas.set(res);
    } finally {
      this.carregando.set(false);
    }
  }

  async cancelar(consultaId: number, motivo: string): Promise<void> {
    await firstValueFrom(
      this.api.patch(`/agenda/consultas/${consultaId}/cancelar`, { motivo })
    );
    this.consultas.update((list) =>
      list.map((c) =>
        c.id === consultaId ? { ...c, status: 'CANCELADA' } : c
      )
    );
  }
}
