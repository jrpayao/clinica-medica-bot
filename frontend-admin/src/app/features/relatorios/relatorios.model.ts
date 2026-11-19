/** Relatórios gerenciais (G15): contratos de /relatorios/* e /admin/avaliacoes*, e regras de apresentação. */

import { localDateString } from '../../core/utils/date.utils';

export interface Periodo { inicio: string; fim: string; }

export interface OcupacaoProfissional {
  profissional_id: number;
  profissional_nome: string;
  total_slots: number;
  ocupados: number;
  taxa: number;
}
export interface Ocupacao {
  geral: { total_slots: number; ocupados: number; taxa: number };
  profissionais: OcupacaoProfissional[];
}

export interface Confirmacao {
  total: number;
  realizados: number;
  faltas: number;
  cancelados: number;
  em_aberto: number;
  taxa_comparecimento: number | null;
  taxa_cancelamento: number | null;
  cancelamentos_por_motivo: Record<string, number>;
}

export interface Sintomas {
  total_triagens: number;
  sintomas: { rotulo: string; total: number }[];
  especialidades: { nome: string; total: number }[];
}

export interface Custo {
  custo_total_usd: number;
  total_tokens: number;
  chamadas: number;
  agendamentos_chat: number;
  custo_por_agendamento_usd: number | null;
}

export interface FilaRelatorio {
  entradas: number;
  aguardando: number;
  notificados: number;
  agendados: number;
  cancelados: number;
  taxa_conversao: number | null;
  espera_media_horas: number | null;
}

export interface Nps {
  total: number;
  promotores: number;
  neutros: number;
  detratores: number;
  nps: number | null;
  media: number | null;
}
export interface NpsProfissional extends Nps { profissional_id: number; profissional_nome: string; }
export interface ResumoNps {
  geral: Nps;
  distribuicao: Record<string, number>;
  profissionais: NpsProfissional[];
}

export interface AvaliacaoItem {
  id: number;
  nota: number;
  comentario: string | null;
  canal: string;
  cliente_nome: string;
  profissional_nome: string;
  created_at: string | null;
}

export const PERIODOS_RAPIDOS = [
  { dias: 7, rotulo: '7 dias' },
  { dias: 30, rotulo: '30 dias' },
  { dias: 90, rotulo: '90 dias' },
] as const;

/** Período de `dias` dias que termina em `hoje` (inclusive), em datas locais. */
export function periodoDosUltimosDias(dias: number, hoje: Date = new Date()): Periodo {
  const inicio = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() - (dias - 1));
  return { inicio: localDateString(inicio), fim: localDateString(hoje) };
}

export function periodoValido(p: Periodo): boolean {
  return !!p.inicio && !!p.fim && p.inicio <= p.fim;
}

/** '75,5%' — ou travessão quando ainda não há base para calcular. */
export function formatarTaxa(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return `${valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`;
}

/** Largura (0–100) de uma barra em relação ao maior valor da série. */
export function larguraBarra(valor: number, maximo: number): number {
  if (maximo <= 0 || valor <= 0) return 0;
  return Math.min(100, Math.round((valor / maximo) * 100));
}

export type FaixaNps = 'sem_dados' | 'critico' | 'razoavel' | 'bom' | 'excelente';

/** Leitura usual do NPS: abaixo de 0 crítico, até 49 razoável, até 74 bom, 75 ou mais excelente. */
export function faixaNps(nps: number | null | undefined): FaixaNps {
  if (nps === null || nps === undefined) return 'sem_dados';
  if (nps < 0) return 'critico';
  if (nps < 50) return 'razoavel';
  if (nps < 75) return 'bom';
  return 'excelente';
}

export const ROTULO_FAIXA_NPS: Record<FaixaNps, string> = {
  sem_dados: 'Sem avaliações no período',
  critico: 'Zona crítica',
  razoavel: 'Zona de aperfeiçoamento',
  bom: 'Zona de qualidade',
  excelente: 'Zona de excelência',
};

export const ROTULO_MOTIVO_CANCELAMENTO: Record<string, string> = {
  PACIENTE: 'A pedido do cliente',
  MEDICO: 'Pelo profissional',
  ESTABELECIMENTO: 'Pela unidade',
  SISTEMA: 'Automático',
  NAO_INFORMADO: 'Não informado',
};

/** Notas de 5 a 1 com a quantidade de cada uma, para o gráfico de distribuição. */
export function distribuicaoOrdenada(distribuicao: Record<string, number>): { nota: number; total: number }[] {
  return [5, 4, 3, 2, 1].map((nota) => ({ nota, total: distribuicao[String(nota)] ?? 0 }));
}

export function formatarUsd(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return `US$ ${valor.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
}
