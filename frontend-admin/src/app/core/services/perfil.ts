/** Perfis de acesso do painel: rótulos para exibição e rotas liberadas por perfil. */

const ROTULOS: Record<string, string> = {
  ADMIN_GLOBAL: 'Administrador da plataforma',
  ADMIN_ESTABELECIMENTO: 'Gestor da unidade',
  ADMIN: 'Administrador',
  RECEPCIONISTA: 'Recepção',
  MEDICO: 'Profissional',
};

/** Rotas do painel liberadas para perfis operacionais. Perfil ausente daqui não é restringido pelo guard. */
const ROTAS_POR_PERFIL: Record<string, readonly string[]> = {
  RECEPCIONISTA: ['/recepcao', '/fila-espera', '/agenda', '/atendimentos', '/clientes', '/profissionais'],
  MEDICO: ['/meu-dia', '/atender', '/agenda', '/meus-pacientes'],
};

const ROTA_INICIAL: Record<string, string> = {
  RECEPCIONISTA: '/recepcao',
  MEDICO: '/meu-dia',
};

export function rotuloPerfil(role: string | null | undefined): string {
  if (!role) return '';
  return ROTULOS[role] ?? 'Usuário';
}

/** Primeiro segmento da URL, sem query string: '/billing/config?x=1' → '/billing'. */
function segmentoPrincipal(url: string): string {
  return '/' + (url.split('?')[0].split('/')[1] ?? '');
}

export function rotaPermitida(role: string | null | undefined, url: string): boolean {
  const liberadas = role ? ROTAS_POR_PERFIL[role] : undefined;
  if (!liberadas) return true;
  return liberadas.includes(segmentoPrincipal(url));
}

export function rotaInicial(role: string | null | undefined): string {
  return (role && ROTA_INICIAL[role]) || '/dashboard';
}

export function perfilSomenteLeituraDeCadastros(role: string | null | undefined): boolean {
  return role === 'RECEPCIONISTA' || role === 'MEDICO';
}
