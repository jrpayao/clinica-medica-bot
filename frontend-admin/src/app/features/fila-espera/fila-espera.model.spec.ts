import { describe, expect, it } from 'vitest';
import { buscarClientes, semComoAvisar, tempoDeEspera } from './fila-espera.model';

describe('tempoDeEspera', () => {
  const agora = new Date('2026-11-19T15:00:00Z');

  it.each([
    ['2026-11-19T14:59:40Z', 'agora'],
    ['2026-11-19T14:48:00Z', 'há 12 min'],
    ['2026-11-19T10:00:00Z', 'há 5 h'],
    ['2026-11-18T14:00:00Z', 'há 1 dia'],
    ['2026-11-16T15:00:00Z', 'há 3 dias'],
  ])('%s → %s', (iso, esperado) => expect(tempoDeEspera(iso, agora)).toBe(esperado));

  it('mostra travessão sem data ou com data inválida', () => {
    expect(tempoDeEspera(null, agora)).toBe('—');
    expect(tempoDeEspera('xyz', agora)).toBe('—');
  });
});

describe('semComoAvisar', () => {
  it('acusa telefone ausente ou em branco', () => {
    expect(semComoAvisar({ cliente_telefone: null })).toBe(true);
    expect(semComoAvisar({ cliente_telefone: '  ' })).toBe(true);
    expect(semComoAvisar({ cliente_telefone: '11988887777' })).toBe(false);
  });
});

describe('buscarClientes', () => {
  const clientes = [{ nome: 'José Antônio' }, { nome: 'Joana Lima' }, { nome: 'Carlos Souza' }];

  it('ignora acentos e maiúsculas', () => {
    expect(buscarClientes(clientes, 'jose antonio')).toEqual([{ nome: 'José Antônio' }]);
    expect(buscarClientes(clientes, 'JO').map((c) => c.nome)).toEqual(['José Antônio', 'Joana Lima']);
  });

  it('só busca a partir de duas letras', () => {
    expect(buscarClientes(clientes, 'j')).toEqual([]);
    expect(buscarClientes(clientes, '  ')).toEqual([]);
  });

  it('respeita o limite de resultados', () => {
    const muitos = Array.from({ length: 20 }, (_, i) => ({ nome: `Maria ${i}` }));
    expect(buscarClientes(muitos, 'maria', 5)).toHaveLength(5);
  });
});
