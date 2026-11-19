import { describe, expect, it } from 'vitest';
import { VOCABULARIO_PADRAO, normalizarVocabulario, pluralizar } from './vocabulario.service';

describe('pluralizar', () => {
  it.each([
    ['Médico', 'Médicos'],
    ['Paciente', 'Pacientes'],
    ['Consulta', 'Consultas'],
    ['Sessão', 'Sessões'],
    ['Profissional', 'Profissionais'],
    ['Doutor', 'Doutores'],
    ['Esteticista', 'Esteticistas'],
    ['Aluno', 'Alunos'],
    ['Instrutor', 'Instrutores'],
    ['Atendimento', 'Atendimentos'],
    ['Exame', 'Exames'],
  ])('%s → %s', (singular, plural) => {
    expect(pluralizar(singular)).toBe(plural);
  });

  it('mantém termos que já terminam em s', () => {
    expect(pluralizar('Pilates')).toBe('Pilates');
  });
});

describe('normalizarVocabulario', () => {
  it('usa o termo padrão quando o rótulo vem vazio ou ausente', () => {
    const vocab = normalizarVocabulario({ label_profissional: '  ', label_cliente: 'Aluno' });

    expect(vocab.label_profissional).toBe(VOCABULARIO_PADRAO.label_profissional);
    expect(vocab.label_cliente).toBe('Aluno');
    expect(vocab.label_atendimento).toBe(VOCABULARIO_PADRAO.label_atendimento);
  });

  it('remove espaços nas pontas', () => {
    expect(normalizarVocabulario({ label_atendimento: ' Sessão ' }).label_atendimento).toBe('Sessão');
  });
});
