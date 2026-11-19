import { describe, expect, it } from 'vitest';
import {
  distribuicaoOrdenada, faixaNps, formatarTaxa, formatarUsd, larguraBarra, periodoDosUltimosDias, periodoValido,
} from './relatorios.model';

describe('periodoDosUltimosDias', () => {
  it('inclui o dia de hoje na contagem', () => {
    expect(periodoDosUltimosDias(7, new Date(2026, 10, 19))).toEqual({ inicio: '2026-11-13', fim: '2026-11-19' });
  });

  it('atravessa a virada do mês', () => {
    expect(periodoDosUltimosDias(30, new Date(2026, 2, 5))).toEqual({ inicio: '2026-02-04', fim: '2026-03-05' });
  });

  it('usa a data local mesmo tarde da noite', () => {
    expect(periodoDosUltimosDias(1, new Date(2026, 10, 19, 23, 30)).fim).toBe('2026-11-19');
  });
});

describe('periodoValido', () => {
  it('aceita início igual ou anterior ao fim', () => {
    expect(periodoValido({ inicio: '2026-11-01', fim: '2026-11-01' })).toBe(true);
    expect(periodoValido({ inicio: '2026-11-01', fim: '2026-11-19' })).toBe(true);
  });

  it('recusa período invertido ou incompleto', () => {
    expect(periodoValido({ inicio: '2026-11-20', fim: '2026-11-19' })).toBe(false);
    expect(periodoValido({ inicio: '', fim: '2026-11-19' })).toBe(false);
  });
});

describe('formatarTaxa', () => {
  it('formata com vírgula decimal', () => {
    expect(formatarTaxa(75.5)).toBe('75,5%');
    expect(formatarTaxa(100)).toBe('100%');
    expect(formatarTaxa(0)).toBe('0%');
  });

  it('mostra travessão quando não há base de cálculo', () => {
    expect(formatarTaxa(null)).toBe('—');
    expect(formatarTaxa(undefined)).toBe('—');
  });
});

describe('larguraBarra', () => {
  it('é proporcional ao maior valor', () => {
    expect(larguraBarra(5, 10)).toBe(50);
    expect(larguraBarra(10, 10)).toBe(100);
  });

  it('não quebra com série vazia ou zerada', () => {
    expect(larguraBarra(0, 10)).toBe(0);
    expect(larguraBarra(3, 0)).toBe(0);
  });
});

describe('faixaNps', () => {
  it.each([
    [null, 'sem_dados'], [-100, 'critico'], [-1, 'critico'], [0, 'razoavel'], [49, 'razoavel'],
    [50, 'bom'], [74, 'bom'], [75, 'excelente'], [100, 'excelente'],
  ] as const)('%s → %s', (nps, faixa) => expect(faixaNps(nps)).toBe(faixa));
});

describe('distribuicaoOrdenada', () => {
  it('lista de 5 a 1 e preenche notas sem voto com zero', () => {
    expect(distribuicaoOrdenada({ '5': 3, '2': 1 })).toEqual([
      { nota: 5, total: 3 }, { nota: 4, total: 0 }, { nota: 3, total: 0 }, { nota: 2, total: 1 }, { nota: 1, total: 0 },
    ]);
  });
});

describe('formatarUsd', () => {
  it('mostra centavos e frações de centavo', () => {
    expect(formatarUsd(0.02)).toBe('US$ 0,02');
    expect(formatarUsd(0.0031)).toBe('US$ 0,0031');
    expect(formatarUsd(null)).toBe('—');
  });
});
