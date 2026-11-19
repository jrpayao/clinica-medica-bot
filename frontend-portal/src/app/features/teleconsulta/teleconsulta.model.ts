/** Página do paciente na teleconsulta (G29): contrato de /teleconsulta/{token} e regras de tela. */

export type Situacao =
  | 'AGUARDANDO_CONSENTIMENTO'
  | 'CEDO'
  | 'SALA_DE_ESPERA'
  | 'EM_ANDAMENTO'
  | 'ENCERRADA'
  | 'CANCELADA';

export interface DocumentoPaciente {
  id: number;
  tipo: 'RECEITA' | 'ATESTADO';
  emitido_em: string | null;
}

export interface TeleconsultaPaciente {
  situacao: Situacao;
  paciente_nome: string;
  profissional_nome: string;
  especialidade_nome: string;
  unidade_nome: string;
  unidade_telefone: string | null;
  data: string;
  hora: string;
  abre_as: string;
  termo: { versao: string; texto: string } | null;
  sala_url: string | null;
  documentos: DocumentoPaciente[];
}

/** A página consulta o servidor enquanto algo ainda pode mudar. */
export function deveAcompanhar(situacao: Situacao): boolean {
  return situacao === 'CEDO' || situacao === 'SALA_DE_ESPERA' || situacao === 'EM_ANDAMENTO';
}

/** Intervalo entre consultas: curto perto da chamada, longo quando ainda falta muito. */
export function intervaloMs(situacao: Situacao): number {
  return situacao === 'CEDO' ? 30_000 : 5_000;
}

export const ROTULO_DOCUMENTO: Record<DocumentoPaciente['tipo'], string> = {
  RECEITA: 'Receita',
  ATESTADO: 'Atestado',
};

/** Parágrafos e itens numerados do termo, para exibição. */
export function blocosDoTermo(texto: string): { itens: string[]; paragrafos: string[] } {
  const linhas = texto.split('\n').map((l) => l.trim()).filter(Boolean);
  return {
    paragrafos: linhas.filter((l) => !/^\d+\./.test(l)),
    itens: linhas.filter((l) => /^\d+\./.test(l)).map((l) => l.replace(/^\d+\.\s*/, '')),
  };
}
