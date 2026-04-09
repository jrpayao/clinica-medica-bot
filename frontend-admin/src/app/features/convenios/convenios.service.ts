import { Injectable, inject } from '@angular/core';
import { ApiService } from '../../core/services/api.service';

export interface Convenio {
  id: number;
  nome: string;
  codigo_ans: string | null;
  cnpj: string | null;
  telefone_autorizacao: string | null;
  email: string | null;
  website: string | null;
  ativo: boolean;
}

export interface ConvenioPlano {
  id: number;
  convenio_id: number;
  nome: string;
  ativo: boolean;
}

@Injectable({ providedIn: 'root' })
export class ConveniosService {
  private api = inject(ApiService);

  listar() {
    return this.api.get<Convenio[]>('/convenios');
  }

  criar(dados: Partial<Convenio>) {
    return this.api.post<Convenio>('/convenios', dados);
  }

  atualizar(id: number, dados: Partial<Convenio>) {
    return this.api.patch<Convenio>(`/convenios/${id}`, dados);
  }

  listarPlanos(convenioId: number) {
    return this.api.get<ConvenioPlano[]>(`/convenios/${convenioId}/planos`);
  }

  criarPlano(convenioId: number, dados: { nome: string }) {
    return this.api.post<ConvenioPlano>(`/convenios/${convenioId}/planos`, dados);
  }

  atualizarPlano(convenioId: number, planoId: number, dados: Partial<ConvenioPlano>) {
    return this.api.patch<ConvenioPlano>(`/convenios/${convenioId}/planos/${planoId}`, dados);
  }
}
