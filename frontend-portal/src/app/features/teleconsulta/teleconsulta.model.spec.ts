import { describe, expect, it } from 'vitest';
import { blocosDoTermo, deveAcompanhar, intervaloMs } from './teleconsulta.model';

describe('deveAcompanhar', () => {
  it('acompanha enquanto a situação ainda pode mudar', () => {
    expect(deveAcompanhar('CEDO')).toBe(true);
    expect(deveAcompanhar('SALA_DE_ESPERA')).toBe(true);
    expect(deveAcompanhar('EM_ANDAMENTO')).toBe(true);
  });

  it('para quando depende do paciente ou já terminou', () => {
    expect(deveAcompanhar('AGUARDANDO_CONSENTIMENTO')).toBe(false);
    expect(deveAcompanhar('ENCERRADA')).toBe(false);
    expect(deveAcompanhar('CANCELADA')).toBe(false);
  });
});

describe('intervaloMs', () => {
  it('consulta devagar quando ainda é cedo e rápido na sala de espera', () => {
    expect(intervaloMs('CEDO')).toBe(30_000);
    expect(intervaloMs('SALA_DE_ESPERA')).toBe(5_000);
    expect(intervaloMs('EM_ANDAMENTO')).toBe(5_000);
  });
});

describe('blocosDoTermo', () => {
  it('separa a introdução dos itens numerados', () => {
    const termo = 'Atendimento por vídeo.\n\nVocê declara que:\n1. Concorda.\n2. Está em local reservado.';
    expect(blocosDoTermo(termo)).toEqual({
      paragrafos: ['Atendimento por vídeo.', 'Você declara que:'],
      itens: ['Concorda.', 'Está em local reservado.'],
    });
  });
});
