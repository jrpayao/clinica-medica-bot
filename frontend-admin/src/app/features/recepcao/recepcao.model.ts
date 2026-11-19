/** Painel da recepção (G23): contrato de GET /recepcao/painel e regras de apresentação. */

export interface AtendimentoRecepcao {
  atendimento_id: number;
  hora_inicio: string;
  hora_fim: string;
  cliente_nome: string;
  cliente_cpf_mascarado: string;
  cliente_telefone: string | null;
  profissional_nome: string;
  especialidade_nome: string;
  status: string;
  urgencia: string;
  canal_origem: string;
  convenio_nome: string | null;
  observacoes?: string | null;
  modalidade?: 'PRESENCIAL' | 'ONLINE';
  /** Só no painel do profissional: o que o paciente relatou no chat antes do atendimento. */
  triagem?: TriagemResumo | null;
  /** Status para os quais a recepção pode levar este atendimento (definido pela API). */
  acoes: string[];
}

export interface TriagemResumo {
  texto: string;
  origem: 'ia' | 'regra' | null;
  categorias: string[];
  historico: { data: string | null; especialidade: string | null; resumo: string | null }[];
}

export interface ResumoRecepcao {
  total: number;
  a_chegar: number;
  na_recepcao: number;
  em_atendimento: number;
  realizados: number;
  faltas: number;
  cancelados: number;
  urgentes: number;
}

export interface PainelRecepcao {
  data: string;
  resumo: ResumoRecepcao;
  atendimentos: AtendimentoRecepcao[];
}

export type Etapa = 'a_chegar' | 'na_recepcao' | 'em_atendimento' | 'encerrados';
export type FiltroEtapa = Etapa | 'todos';

export const RESUMO_VAZIO: ResumoRecepcao = {
  total: 0, a_chegar: 0, na_recepcao: 0, em_atendimento: 0, realizados: 0, faltas: 0, cancelados: 0, urgentes: 0,
};

export const ROTULO_STATUS: Record<string, string> = {
  AGENDADA: 'Agendado',
  CONFIRMADA: 'Confirmado',
  PRESENTE: 'Na recepção',
  AGUARDANDO_ANAMNESE: 'Aguardando anamnese',
  ANAMNESE_PREENCHIDA: 'Anamnese preenchida',
  FICHA_CONCLUIDA: 'Ficha concluída',
  AGUARDANDO_PAGAMENTO: 'Aguardando pagamento',
  PAGO: 'Pago',
  AGUARDANDO_PROFISSIONAL: 'Aguardando o profissional',
  EM_ATENDIMENTO: 'Em atendimento',
  REALIZADA: 'Realizado',
  FALTA: 'Faltou',
  CANCELADA: 'Cancelado',
};

export const ROTULO_URGENCIA: Record<string, string> = {
  BAIXA: 'Baixa', MEDIA: 'Média', ALTA: 'Alta', EMERGENCIA: 'Emergência',
};

/** Botão de cada ação que a API pode oferecer. `principal` destaca o passo esperado do fluxo. */
export const ROTULO_ACAO: Record<string, { texto: string; icone: string; principal: boolean }> = {
  PRESENTE:       { texto: 'Registrar chegada', icone: 'how_to_reg',   principal: true },
  CONFIRMADA:     { texto: 'Confirmar',         icone: 'done',         principal: false },
  FALTA:          { texto: 'Marcar falta',      icone: 'person_off',   principal: false },
  EM_ATENDIMENTO: { texto: 'Chamar',            icone: 'campaign',     principal: true },
  REALIZADA:      { texto: 'Concluir',          icone: 'check_circle', principal: true },
};

export type ModoPainel = 'recepcao' | 'profissional';

/** No painel do profissional, levar a EM_ATENDIMENTO é começar a atender, não chamar da sala de espera. */
export function rotuloDaAcao(acao: string, modo: ModoPainel): { texto: string; icone: string; principal: boolean } {
  if (modo === 'profissional' && acao === 'EM_ATENDIMENTO') {
    return { texto: 'Iniciar atendimento', icone: 'play_arrow', principal: true };
  }
  return ROTULO_ACAO[acao];
}

const A_CHEGAR = new Set(['AGENDADA', 'CONFIRMADA']);
const ENCERRADOS = new Set(['REALIZADA', 'FALTA', 'CANCELADA']);

export function etapaDoStatus(status: string): Etapa {
  if (A_CHEGAR.has(status)) return 'a_chegar';
  if (status === 'EM_ATENDIMENTO') return 'em_atendimento';
  if (ENCERRADOS.has(status)) return 'encerrados';
  return 'na_recepcao';
}

export function filtrarPorEtapa(lista: AtendimentoRecepcao[], filtro: FiltroEtapa): AtendimentoRecepcao[] {
  return filtro === 'todos' ? lista : lista.filter((a) => etapaDoStatus(a.status) === filtro);
}

/** Primeiro atendimento ainda não chegado com horário a partir de `agora` ('HH:mm'). */
export function proximoAChegar(lista: AtendimentoRecepcao[], agora: string): AtendimentoRecepcao | null {
  return lista.find((a) => A_CHEGAR.has(a.status) && a.hora_inicio >= agora) ?? null;
}
