import { Injectable, inject } from '@angular/core';
import { ApiService } from '../../core/services/api.service';

export interface TipoAtendimento {
  id: number;
  nome: string;
  descricao: string | null;
  duracao_min: number;
  preco: number | null;
  ativo: boolean;
}

@Injectable({ providedIn: 'root' })
export class CatalogoService {
  private api = inject(ApiService);

  listar() {
    return this.api.get<TipoAtendimento[]>('/tipo-atendimentos');
  }

  criar(dados: Partial<TipoAtendimento>) {
    return this.api.post<TipoAtendimento>('/tipo-atendimentos', dados);
  }

  atualizar(id: number, dados: Partial<TipoAtendimento>) {
    return this.api.patch<TipoAtendimento>(`/tipo-atendimentos/${id}`, dados);
  }
}
