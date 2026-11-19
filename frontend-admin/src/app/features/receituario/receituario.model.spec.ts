import { describe, expect, it } from 'vitest';
import { TAMANHO_MAXIMO_BYTES, erroDoArquivo, marcaDaguaAtiva } from './receituario.model';

describe('erroDoArquivo', () => {
  it('aceita PNG e JPEG dentro do limite', () => {
    expect(erroDoArquivo({ type: 'image/png', size: 50_000 })).toBeNull();
    expect(erroDoArquivo({ type: 'image/jpeg', size: TAMANHO_MAXIMO_BYTES })).toBeNull();
  });

  it('recusa outros formatos, arquivo grande e arquivo vazio', () => {
    expect(erroDoArquivo({ type: 'image/svg+xml', size: 1000 })).toBe('Use uma imagem PNG ou JPEG.');
    expect(erroDoArquivo({ type: 'application/pdf', size: 1000 })).toBe('Use uma imagem PNG ou JPEG.');
    expect(erroDoArquivo({ type: 'image/png', size: TAMANHO_MAXIMO_BYTES + 1 })).toBe('A imagem precisa ter até 2 MB.');
    expect(erroDoArquivo({ type: 'image/png', size: 0 })).toBe('O arquivo está vazio.');
  });
});

describe('marcaDaguaAtiva', () => {
  it('só vale quando há logo', () => {
    expect(marcaDaguaAtiva({ tem_logo: true, marca_dagua: true })).toBe(true);
    expect(marcaDaguaAtiva({ tem_logo: false, marca_dagua: true })).toBe(false);
    expect(marcaDaguaAtiva({ tem_logo: true, marca_dagua: false })).toBe(false);
  });
});
