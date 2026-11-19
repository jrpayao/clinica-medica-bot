import { describe, expect, it } from 'vitest';
import {
  DocumentoEmitido, TeleconsultaProfissional, erroDaReceita, erroDoAtestado, idade, itensValidos,
  podeEmitirDocumento, podeRegistrar, resumoDoDocumento, situacaoDoPaciente,
} from './atender.model';

const tele = (p: Partial<TeleconsultaProfissional>): TeleconsultaProfissional => ({
  sala_url: 'https://meet.jit.si/medbot-x', link_paciente: 'http://localhost:4200/teleconsulta/t',
  consentimento: false, paciente_na_sala: false, paciente_entrou_em: null, link_enviado_em: null, ...p,
});

describe('podeEmitirDocumento / podeRegistrar', () => {
  it('documento só com o atendimento em andamento ou realizado', () => {
    expect(podeEmitirDocumento('EM_ATENDIMENTO')).toBe(true);
    expect(podeEmitirDocumento('REALIZADA')).toBe(true);
    expect(podeEmitirDocumento('PRESENTE')).toBe(false);
    expect(podeEmitirDocumento('AGENDADA')).toBe(false);
  });

  it('registro não é aceito em cancelado ou falta', () => {
    expect(podeRegistrar('PRESENTE')).toBe(true);
    expect(podeRegistrar('CANCELADA')).toBe(false);
    expect(podeRegistrar('FALTA')).toBe(false);
  });
});

describe('situacaoDoPaciente', () => {
  it.each([
    [{ paciente_na_sala: true, consentimento: true, paciente_entrou_em: 'x' }, 'na_sala'],
    [{ consentimento: true, paciente_entrou_em: 'x' }, 'saiu'],
    [{ consentimento: true }, 'nao_entrou'],
    [{}, 'falta_termo'],
  ] as const)('%o → %s', (parcial, esperado) => {
    expect(situacaoDoPaciente(tele(parcial))).toBe(esperado);
  });
});

describe('receita', () => {
  it('ignora linhas em branco e apara os textos', () => {
    expect(itensValidos([
      { medicamento: ' Dipirona 500 mg ', posologia: ' 1 cp ' }, { medicamento: '  ', posologia: '' },
    ])).toEqual([{ medicamento: 'Dipirona 500 mg', posologia: '1 cp' }]);
  });

  it('aponta o que falta', () => {
    expect(erroDaReceita([{ medicamento: '', posologia: '' }])).toBe('Informe pelo menos um medicamento.');
    expect(erroDaReceita([{ medicamento: '', posologia: '1x ao dia' }])).toBe('Há um item sem o nome do medicamento.');
    expect(erroDaReceita([{ medicamento: 'Dipirona', posologia: '' }])).toBe('Há um item sem a forma de uso.');
    expect(erroDaReceita([{ medicamento: 'Dipirona', posologia: '1x ao dia' }])).toBeNull();
  });
});

describe('erroDoAtestado', () => {
  it.each([[1, null], [90, null], [0, 'x'], [91, 'x'], [1.5, 'x'], [null, 'x']] as const)('%s dias', (dias, erro) => {
    expect(erroDoAtestado(dias) === null).toBe(erro === null);
  });
});

describe('resumoDoDocumento', () => {
  const doc = (p: Partial<DocumentoEmitido>): DocumentoEmitido => ({
    id: 1, tipo: 'RECEITA', emitido_em: null, codigo: 'AB', conteudo: {}, ...p,
  });

  it('descreve atestado e receita', () => {
    expect(resumoDoDocumento(doc({ tipo: 'ATESTADO', conteudo: { dias: 1 } }))).toBe('Atestado de 1 dia');
    expect(resumoDoDocumento(doc({ tipo: 'ATESTADO', conteudo: { dias: 3 } }))).toBe('Atestado de 3 dias');
    expect(resumoDoDocumento(doc({ conteudo: { itens: [{ medicamento: 'Dipirona', posologia: 'x' }] } })))
      .toBe('Receita: Dipirona');
    expect(resumoDoDocumento(doc({
      conteudo: { itens: [{ medicamento: 'Dipirona', posologia: 'x' }, { medicamento: 'Soro', posologia: 'y' }] },
    }))).toBe('Receita: Dipirona e mais 1');
  });
});

describe('idade', () => {
  const hoje = new Date(2026, 10, 19);

  it('conta anos completos', () => {
    expect(idade('1990-11-19', hoje)).toBe(36);
    expect(idade('1990-11-20', hoje)).toBe(35);
    expect(idade('2026-01-01', hoje)).toBe(0);
  });

  it('sem data não inventa idade', () => {
    expect(idade(null, hoje)).toBeNull();
    expect(idade('data', hoje)).toBeNull();
  });
});
