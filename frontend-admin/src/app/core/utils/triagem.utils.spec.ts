import { describe, expect, it } from 'vitest';
import { itensDaTriagem } from './triagem.utils';

describe('itensDaTriagem', () => {
  it('mostra o relato e as queixas do resumo gravado pelo chat', () => {
    const resumo = {
      texto: ' Paciente relata tosse seca. ', origem: 'ia', sintomas: ['tosse seca'],
      categorias: ['Tosse', 'Febre'], historico: [{ data: '01/11/2026' }], urgencia: 'BAIXA',
    };
    expect(itensDaTriagem(resumo)).toEqual([
      { chave: 'Relato', valor: 'Paciente relata tosse seca.' },
      { chave: 'Queixas', valor: 'Tosse, Febre' },
    ]);
  });

  it('omite as queixas quando nenhuma foi reconhecida', () => {
    expect(itensDaTriagem({ texto: 'Relato.', categorias: [] })).toEqual([{ chave: 'Relato', valor: 'Relato.' }]);
  });

  it('mantem registros antigos, juntando listas e sem exibir objetos', () => {
    expect(itensDaTriagem({ sintomas: ['dor', 'febre'], interno: { a: 1 }, vazio: null })).toEqual([
      { chave: 'Sintomas', valor: 'dor, febre' },
    ]);
  });

  it('devolve lista vazia sem triagem', () => {
    expect(itensDaTriagem(null)).toEqual([]);
    expect(itensDaTriagem('x')).toEqual([]);
  });
});
