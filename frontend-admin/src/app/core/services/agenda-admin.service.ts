import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from './api.service';
import { firstValueFrom } from 'rxjs';

export interface SlotAdmin {
  id: number;
  profissional_id: number;
  profissional_nome: string;
  especialidade_nome: string;
  data: string;
  hora_inicio: string;
  hora_fim: string;
  status: 'DISPONIVEL' | 'AGENDADO' | 'BLOQUEADO';
  consulta?: ConsultaAdmin;
}

export interface ConsultaAdmin {
  id: number;
  cliente_nome: string;
  paciente_cpf_mascarado: string;
  urgencia: string;
  status: string;
  triagem_resumo: Record<string, unknown> | null;
  observacoes: string | null;
  canal_origem: string;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class AgendaAdminService {
  private readonly api = inject(ApiService);

  readonly slots = signal<SlotAdmin[]>([]);
  readonly carregando = signal(false);
  readonly slotSelecionado = signal<SlotAdmin | null>(null);
  readonly filtroMedicoId = signal<number | null>(null);

  async carregarPorData(data: string): Promise<void> {
    this.carregando.set(true);
    try {
      const medicoId = this.filtroMedicoId();
      const params = medicoId ? `?profissional_id=${medicoId}` : '';
      const res = await firstValueFrom(
        this.api.get<SlotAdmin[]>(`/agenda/slots/dia/${data}${params}`)
      );
      this.slots.set(res);
    } finally {
      this.carregando.set(false);
    }
  }

  selecionarSlot(slot: SlotAdmin): void {
    this.slotSelecionado.set(slot);
  }

  fecharModal(): void {
    this.slotSelecionado.set(null);
  }
}
