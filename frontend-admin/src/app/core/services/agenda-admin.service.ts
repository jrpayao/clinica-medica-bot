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
  aceita_online?: boolean;
  atendimento?: ConsultaAdmin;
}

export interface ConsultaAdmin {
  id: number;
  cliente_nome: string;
  cliente_cpf_mascarado: string;
  urgencia: string;
  status: string;
  triagem_resumo: Record<string, unknown> | null;
  observacoes: string | null;
  canal_origem: string;
  created_at: string;
  modalidade?: 'PRESENCIAL' | 'ONLINE';
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

  /** Marca (ou desmarca) os horários livres do dia do profissional como "aceita online". */
  async definirOnline(data: string, aceita: boolean, profissionalId: number | null): Promise<number> {
    const r = await firstValueFrom(
      this.api.patch<{ alterados: number }>('/agenda/slots/online', {
        data, aceita_online: aceita, profissional_id: profissionalId,
      }),
    );
    await this.carregarPorData(data);
    return r.alterados;
  }

  selecionarSlot(slot: SlotAdmin): void {
    this.slotSelecionado.set(slot);
  }

  fecharModal(): void {
    this.slotSelecionado.set(null);
  }
}
