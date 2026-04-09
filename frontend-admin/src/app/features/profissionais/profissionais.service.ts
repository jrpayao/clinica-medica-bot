import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from '../../core/services/api.service';
import { firstValueFrom } from 'rxjs';

export interface Especialidade {
  id: number;
  nome: string;
  descricao: string | null;
  cor_hex: string | null;
  icone: string | null;
  ativo: boolean;
}

export interface Medico {
  id: number;
  crm: string;
  nome: string;
  especialidade_id: number;
  email: string | null;
  telefone: string | null;
  duracao_consulta_min: number;
  ativo: boolean;
  created_at: string;
}

export interface MedicoCreate {
  crm: string;
  nome: string;
  especialidade_id: number;
  email?: string;
  telefone?: string;
  duracao_consulta_min?: number;
}

export interface MedicoUpdate {
  nome?: string;
  email?: string;
  telefone?: string;
  duracao_consulta_min?: number;
  ativo?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ProfissionaisService {
  private readonly api = inject(ApiService);

  readonly medicos = signal<Medico[]>([]);
  readonly especialidades = signal<Especialidade[]>([]);
  readonly carregando = signal(false);
  readonly salvando = signal(false);
  readonly erro = signal<string | null>(null);

  async listar(): Promise<void> {
    this.carregando.set(true);
    this.erro.set(null);
    try {
      const [medicos, especialidades] = await Promise.all([
        firstValueFrom(this.api.get<Medico[]>('/profissionais/')),
        firstValueFrom(this.api.get<Especialidade[]>('/especialidades/')),
      ]);
      this.medicos.set(medicos);
      this.especialidades.set(especialidades);
    } catch {
      this.erro.set('Erro ao carregar profissionais.');
    } finally {
      this.carregando.set(false);
    }
  }

  async criar(dados: MedicoCreate): Promise<Medico> {
    this.salvando.set(true);
    try {
      const novo = await firstValueFrom(this.api.post<Medico>('/profissionais/', dados));
      this.medicos.update((list) => [...list, novo]);
      return novo;
    } finally {
      this.salvando.set(false);
    }
  }

  async atualizar(id: number, dados: MedicoUpdate): Promise<void> {
    this.salvando.set(true);
    try {
      const atualizado = await firstValueFrom(
        this.api.patch<Medico>(`/profissionais/${id}`, dados)
      );
      this.medicos.update((list) => list.map((m) => (m.id === id ? atualizado : m)));
    } finally {
      this.salvando.set(false);
    }
  }

  async desativar(id: number): Promise<void> {
    await this.atualizar(id, { ativo: false });
  }

  nomeEspecialidade(id: number): string {
    return this.especialidades().find((e) => e.id === id)?.nome ?? '—';
  }
}
