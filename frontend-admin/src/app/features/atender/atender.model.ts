/** Tela de atendimento do profissional (G29): contrato de /profissional/atendimentos/{id}/sala e regras de tela. */

import { TriagemResumo } from '../recepcao/recepcao.model';

export interface ItemReceita { medicamento: string; posologia: string; }

export interface DocumentoEmitido {
  id: number;
  tipo: 'RECEITA' | 'ATESTADO';
  emitido_em: string | null;
  codigo: string;
  conteudo: { itens?: ItemReceita[]; dias?: number; cid?: string | null; motivo?: string | null };
}

export interface TeleconsultaProfissional {
  sala_url: string;
  link_paciente: string;
  consentimento: boolean;
  paciente_na_sala: boolean;
  paciente_entrou_em: string | null;
  link_enviado_em: string | null;
}

export interface Registro {
  queixa: string | null;
  evolucao: string | null;
  conduta: string | null;
  atualizado_em: string | null;
}

export interface SalaAtendimento {
  atendimento_id: number;
  status: string;
  acoes: string[];
  modalidade: 'PRESENCIAL' | 'ONLINE';
  data: string;
  hora_inicio: string;
  hora_fim: string;
  especialidade_nome: string;
  cliente_id: number;
  cliente_nome: string;
  cliente_telefone: string | null;
  cliente_nascimento: string | null;
  observacoes: string | null;
  triagem: TriagemResumo | null;
  teleconsulta: TeleconsultaProfissional | null;
  registro: Registro;
  documentos: DocumentoEmitido[];
}

const COM_DOCUMENTO = new Set(['EM_ATENDIMENTO', 'REALIZADA']);
const SEM_REGISTRO = new Set(['CANCELADA', 'FALTA']);

/** Receita e atestado só saem com o atendimento iniciado (a API recusa antes disso). */
export function podeEmitirDocumento(status: string): boolean {
  return COM_DOCUMENTO.has(status);
}

export function podeRegistrar(status: string): boolean {
  return !SEM_REGISTRO.has(status);
}

export type SituacaoPaciente = 'na_sala' | 'saiu' | 'falta_termo' | 'nao_entrou';

/** Onde está o paciente da teleconsulta, do ponto de vista do profissional. */
export function situacaoDoPaciente(t: TeleconsultaProfissional): SituacaoPaciente {
  if (t.paciente_na_sala) return 'na_sala';
  if (t.paciente_entrou_em) return 'saiu';
  return t.consentimento ? 'nao_entrou' : 'falta_termo';
}

export const ROTULO_SITUACAO_PACIENTE: Record<SituacaoPaciente, string> = {
  na_sala: 'Paciente na sala de espera',
  saiu: 'Paciente entrou e saiu da página',
  falta_termo: 'Paciente ainda não abriu o link',
  nao_entrou: 'Paciente aceitou o termo, mas não está na sala',
};

/** Itens preenchidos da receita; linhas totalmente em branco são ignoradas. */
export function itensValidos(itens: ItemReceita[]): ItemReceita[] {
  return itens
    .map((i) => ({ medicamento: i.medicamento.trim(), posologia: i.posologia.trim() }))
    .filter((i) => i.medicamento || i.posologia);
}

/** Mensagem do que falta para emitir a receita, ou null se está pronta. */
export function erroDaReceita(itens: ItemReceita[]): string | null {
  const preenchidos = itensValidos(itens);
  if (!preenchidos.length) return 'Informe pelo menos um medicamento.';
  if (preenchidos.some((i) => !i.medicamento)) return 'Há um item sem o nome do medicamento.';
  if (preenchidos.some((i) => !i.posologia)) return 'Há um item sem a forma de uso.';
  return null;
}

export function erroDoAtestado(dias: number | null): string | null {
  if (dias === null || !Number.isInteger(dias) || dias < 1 || dias > 90) return 'Informe de 1 a 90 dias.';
  return null;
}

export function resumoDoDocumento(d: DocumentoEmitido): string {
  if (d.tipo === 'ATESTADO') {
    const dias = d.conteudo.dias ?? 0;
    return `Atestado de ${dias} ${dias === 1 ? 'dia' : 'dias'}`;
  }
  const itens = d.conteudo.itens ?? [];
  const primeiro = itens[0]?.medicamento ?? '';
  return itens.length > 1 ? `Receita: ${primeiro} e mais ${itens.length - 1}` : `Receita: ${primeiro}`;
}

/** Idade em anos completos a partir de 'AAAA-MM-DD'. */
export function idade(nascimento: string | null, hoje: Date = new Date()): number | null {
  if (!nascimento) return null;
  const [ano, mes, dia] = nascimento.split('-').map(Number);
  if (!ano || !mes || !dia) return null;
  const fezAniversario = hoje.getMonth() + 1 > mes || (hoje.getMonth() + 1 === mes && hoje.getDate() >= dia);
  return hoje.getFullYear() - ano - (fezAniversario ? 0 : 1);
}
