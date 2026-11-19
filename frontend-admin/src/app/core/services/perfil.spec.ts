import { describe, expect, it } from 'vitest';
import { rotaInicial, rotaPermitida, rotuloPerfil } from './perfil';

describe('rotuloPerfil', () => {
  it.each([
    ['ADMIN_GLOBAL', 'Administrador da plataforma'],
    ['ADMIN_ESTABELECIMENTO', 'Gestor da unidade'],
    ['RECEPCIONISTA', 'Recepção'],
    ['MEDICO', 'Profissional'],
  ])('%s → %s', (role, rotulo) => {
    expect(rotuloPerfil(role)).toBe(rotulo);
  });

  it('não expõe o identificador interno de um perfil desconhecido', () => {
    expect(rotuloPerfil('OUTRO_PERFIL')).toBe('Usuário');
    expect(rotuloPerfil(undefined)).toBe('');
  });
});

describe('rotaPermitida — RECEPCIONISTA', () => {
  it.each(['/recepcao', '/agenda', '/atendimentos', '/clientes', '/profissionais'])(
    'acessa %s',
    (rota) => expect(rotaPermitida('RECEPCIONISTA', rota)).toBe(true),
  );

  it.each([
    '/dashboard', '/billing', '/billing/config', '/usuarios', '/minha-licenca', '/auditoria',
    '/vocabulario', '/catalogo', '/convenios', '/documentos', '/especialidades',
    '/estabelecimentos', '/licencas', '/platform-dashboard',
  ])('não acessa %s', (rota) => expect(rotaPermitida('RECEPCIONISTA', rota)).toBe(false));

  it('ignora query string e subcaminho', () => {
    expect(rotaPermitida('RECEPCIONISTA', '/atendimentos?data=2026-11-19&status=AGENDADA')).toBe(true);
    expect(rotaPermitida('RECEPCIONISTA', '/billing/config?x=1')).toBe(false);
  });
});

describe('rotaPermitida — administradores', () => {
  it('não restringe ADMIN_GLOBAL nem ADMIN_ESTABELECIMENTO', () => {
    expect(rotaPermitida('ADMIN_GLOBAL', '/auditoria')).toBe(true);
    expect(rotaPermitida('ADMIN_ESTABELECIMENTO', '/billing')).toBe(true);
    expect(rotaPermitida('ADMIN_ESTABELECIMENTO', '/recepcao')).toBe(true);
  });
});

describe('rotaPermitida — MEDICO', () => {
  it.each(['/meu-dia', '/agenda', '/meus-pacientes'])('acessa %s', (rota) =>
    expect(rotaPermitida('MEDICO', rota)).toBe(true),
  );

  it.each(['/recepcao', '/clientes', '/atendimentos', '/profissionais', '/dashboard', '/billing', '/usuarios'])(
    'não acessa %s',
    (rota) => expect(rotaPermitida('MEDICO', rota)).toBe(false),
  );
});

describe('rotaInicial', () => {
  it('profissional cai no próprio dia', () => {
    expect(rotaInicial('MEDICO')).toBe('/meu-dia');
  });

  it('recepcionista cai no painel da recepção', () => {
    expect(rotaInicial('RECEPCIONISTA')).toBe('/recepcao');
  });

  it('administradores caem no dashboard', () => {
    expect(rotaInicial('ADMIN_ESTABELECIMENTO')).toBe('/dashboard');
    expect(rotaInicial('ADMIN_GLOBAL')).toBe('/dashboard');
  });
});
