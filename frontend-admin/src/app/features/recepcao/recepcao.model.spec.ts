import { describe, expect, it } from 'vitest';
import {
  AtendimentoRecepcao, ROTULO_ACAO, ROTULO_STATUS, filtrarPorEtapa, etapaDoStatus, proximoAChegar, rotuloDaAcao,
} from './recepcao.model';

const item = (p: Partial<AtendimentoRecepcao>): AtendimentoRecepcao => ({
  atendimento_id: 1, hora_inicio: '09:00', hora_fim: '09:30',
  cliente_nome: 'Ana', cliente_cpf_mascarado: '123.***.***-01', cliente_telefone: null,
  profissional_nome: 'Dr. Carlos', especialidade_nome: 'Cardiologia',
  status: 'AGENDADA', urgencia: 'BAIXA', canal_origem: 'PORTAL', convenio_nome: null,
  acoes: ['PRESENTE', 'CONFIRMADA', 'FALTA'],
  ...p,
});

describe('rótulos', () => {
  it('toda ação oferecida pela API tem texto de botão', () => {
    for (const acao of ['PRESENTE', 'CONFIRMADA', 'FALTA', 'EM_ATENDIMENTO', 'REALIZADA']) {
      expect(ROTULO_ACAO[acao]?.texto).toBeTruthy();
    }
    expect(ROTULO_ACAO['PRESENTE'].texto).toBe('Registrar chegada');
  });

  it('status não aparece como identificador interno', () => {
    expect(ROTULO_STATUS['EM_ATENDIMENTO']).toBe('Em atendimento');
    expect(ROTULO_STATUS['AGUARDANDO_PROFISSIONAL']).toBe('Aguardando o profissional');
    expect(ROTULO_STATUS['FALTA']).toBe('Faltou');
  });
});

describe('rotuloDaAcao', () => {
  it('a recepção chama o paciente; o profissional inicia o atendimento', () => {
    expect(rotuloDaAcao('EM_ATENDIMENTO', 'recepcao').texto).toBe('Chamar');
    expect(rotuloDaAcao('EM_ATENDIMENTO', 'profissional').texto).toBe('Iniciar atendimento');
  });

  it('as demais ações têm o mesmo texto nos dois painéis', () => {
    expect(rotuloDaAcao('REALIZADA', 'profissional')).toEqual(rotuloDaAcao('REALIZADA', 'recepcao'));
  });
});

describe('etapaDoStatus', () => {
  it.each([
    ['AGENDADA', 'a_chegar'], ['CONFIRMADA', 'a_chegar'],
    ['PRESENTE', 'na_recepcao'], ['AGUARDANDO_PAGAMENTO', 'na_recepcao'], ['AGUARDANDO_PROFISSIONAL', 'na_recepcao'],
    ['EM_ATENDIMENTO', 'em_atendimento'],
    ['REALIZADA', 'encerrados'], ['FALTA', 'encerrados'], ['CANCELADA', 'encerrados'],
  ])('%s → %s', (status, etapa) => {
    expect(etapaDoStatus(status)).toBe(etapa);
  });
});

describe('filtrarPorEtapa', () => {
  const lista = [
    item({ atendimento_id: 1, status: 'AGENDADA' }),
    item({ atendimento_id: 2, status: 'PRESENTE' }),
    item({ atendimento_id: 3, status: 'REALIZADA' }),
  ];

  it('"todos" devolve a lista inteira', () => {
    expect(filtrarPorEtapa(lista, 'todos')).toHaveLength(3);
  });

  it('filtra pela etapa escolhida', () => {
    expect(filtrarPorEtapa(lista, 'na_recepcao').map((i) => i.atendimento_id)).toEqual([2]);
  });
});

describe('proximoAChegar', () => {
  it('é o primeiro ainda não chegado a partir do horário atual', () => {
    const lista = [
      item({ atendimento_id: 1, hora_inicio: '08:00', status: 'AGENDADA' }), // já passou
      item({ atendimento_id: 2, hora_inicio: '10:00', status: 'PRESENTE' }), // já chegou
      item({ atendimento_id: 3, hora_inicio: '10:30', status: 'CONFIRMADA' }),
      item({ atendimento_id: 4, hora_inicio: '11:00', status: 'AGENDADA' }),
    ];

    expect(proximoAChegar(lista, '09:15')?.atendimento_id).toBe(3);
  });

  it('é nulo quando ninguém mais é esperado', () => {
    expect(proximoAChegar([item({ status: 'REALIZADA' })], '09:15')).toBeNull();
  });
});
