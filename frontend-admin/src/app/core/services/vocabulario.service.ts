/**
 * VocabularioService — termos do negócio configurados por estabelecimento (G27).
 *
 * Uma clínica de estética chama "Médico" de "Esteticista" e "Consulta" de "Sessão".
 * As telas leem os termos daqui em vez de escrevê-los fixos no template.
 */
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';

export interface Vocabulario {
  label_profissional: string;
  label_atendimento: string;
  label_cliente: string;
  label_especialidade: string;
}

export const VOCABULARIO_PADRAO: Vocabulario = {
  label_profissional: 'Médico',
  label_atendimento: 'Consulta',
  label_cliente: 'Paciente',
  label_especialidade: 'Especialidade',
};

/** Plural em português para os termos configurados (regra geral, última palavra). */
export function pluralizar(termo: string): string {
  const texto = termo.trim();
  if (!texto) return texto;

  const lower = texto.toLowerCase();
  if (/[sx]$/.test(lower)) return texto;
  if (lower.endsWith('ão')) return texto.slice(0, -2) + 'ões';
  if (/[aeou]l$/.test(lower)) return texto.slice(0, -1) + 'is';
  if (lower.endsWith('il')) return texto.slice(0, -1) + 's';
  if (lower.endsWith('m')) return texto.slice(0, -1) + 'ns';
  if (/[rz]$/.test(lower)) return texto + 'es';
  return texto + 's';
}

/** Preenche rótulos vazios ou ausentes com o termo padrão. */
export function normalizarVocabulario(parcial: Partial<Vocabulario> | null | undefined): Vocabulario {
  const resultado = { ...VOCABULARIO_PADRAO };
  for (const chave of Object.keys(VOCABULARIO_PADRAO) as Array<keyof Vocabulario>) {
    const valor = parcial?.[chave]?.trim();
    if (valor) resultado[chave] = valor;
  }
  return resultado;
}

@Injectable({ providedIn: 'root' })
export class VocabularioService {
  private readonly api = inject(ApiService);

  readonly termos = signal<Vocabulario>(VOCABULARIO_PADRAO);

  readonly profissional = computed(() => this.termos().label_profissional);
  readonly profissionais = computed(() => pluralizar(this.profissional()));
  readonly atendimento = computed(() => this.termos().label_atendimento);
  readonly atendimentos = computed(() => pluralizar(this.atendimento()));
  readonly cliente = computed(() => this.termos().label_cliente);
  readonly clientes = computed(() => pluralizar(this.cliente()));
  readonly especialidade = computed(() => this.termos().label_especialidade);
  readonly especialidades = computed(() => pluralizar(this.especialidade()));

  /** Carrega os termos do estabelecimento ativo; em falha mantém o padrão. */
  async carregar(): Promise<void> {
    try {
      const vocab = await firstValueFrom(
        this.api.get<Vocabulario>('/estabelecimentos/meu/vocabulario'),
      );
      this.termos.set(normalizarVocabulario(vocab));
    } catch {
      this.termos.set(VOCABULARIO_PADRAO);
    }
  }

  definir(vocab: Partial<Vocabulario>): void {
    this.termos.set(normalizarVocabulario(vocab));
  }

  restaurarPadrao(): void {
    this.termos.set(VOCABULARIO_PADRAO);
  }
}
