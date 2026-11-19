/** Lista de espera e remarcações pendentes (G15): contratos de /fila-espera e /reagendamentos. */

export interface EntradaFila {
  id: number;
  posicao: number;
  cliente_id: number;
  cliente_nome: string;
  cliente_cpf_mascarado: string;
  cliente_telefone: string | null;
  especialidade_id: number | null;
  especialidade_nome: string | null;
  convenio_nome: string | null;
  status: 'AGUARDANDO' | 'NOTIFICADO';
  tentativas: number;
  notificado_em: string | null;
  created_at: string | null;
}

export interface RemarcacaoPendente {
  id: number;
  status: 'RECUSADA' | 'EXPIRADA' | 'SEM_HORARIO' | 'SEM_CONTATO';
  motivo: string;
  cliente_id: number;
  cliente_nome: string;
  cliente_telefone: string | null;
  atendimento_id: number;
  data_original: string;
  hora_original: string;
  profissional_nome: string;
  especialidade_nome: string;
  created_at: string | null;
}

export const ROTULO_STATUS_FILA: Record<string, string> = {
  AGUARDANDO: 'Aguardando vaga',
  NOTIFICADO: 'Horário oferecido',
};

export const ROTULO_PENDENCIA: Record<string, string> = {
  RECUSADA: 'Recusou os horários',
  EXPIRADA: 'Não respondeu',
  SEM_HORARIO: 'Sem horário para oferecer',
  SEM_CONTATO: 'Não foi avisado',
};

/** 'há 3 dias', 'há 5 h', 'há 12 min', 'agora' — tempo decorrido desde `iso` até `agora`. */
export function tempoDeEspera(iso: string | null, agora: Date = new Date()): string {
  if (!iso) return '—';
  const minutos = Math.floor((agora.getTime() - new Date(iso).getTime()) / 60_000);
  if (Number.isNaN(minutos)) return '—';
  if (minutos < 1) return 'agora';
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `há ${horas} h`;
  const dias = Math.floor(horas / 24);
  return `há ${dias} ${dias === 1 ? 'dia' : 'dias'}`;
}

/** Quem não tem telefone não pode ser avisado quando a vaga abrir. */
export function semComoAvisar(entrada: Pick<EntradaFila, 'cliente_telefone'>): boolean {
  return !entrada.cliente_telefone?.trim();
}

/** Filtra clientes pelo nome (sem diferenciar maiúsculas e acentos), até `limite` resultados. */
export function buscarClientes<T extends { nome: string }>(clientes: T[], termo: string, limite = 8): T[] {
  const plano = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  const alvo = plano(termo);
  if (alvo.length < 2) return [];
  return clientes.filter((c) => plano(c.nome).includes(alvo)).slice(0, limite);
}
