/** Como o resumo de triagem gravado no atendimento aparece nas telas de agenda e de atendimentos. */

export interface ItemTriagem { chave: string; valor: string; }

const ROTULOS: Record<string, string> = {
  sintomas: 'Sintomas',
  especialidade: 'Especialidade indicada',
  urgencia: 'Urgência',
};

function texto(valor: unknown): string {
  if (Array.isArray(valor)) return valor.filter((v) => typeof v !== 'object').join(', ');
  return typeof valor === 'object' ? '' : String(valor ?? '');
}

/**
 * Itens a exibir. O resumo gravado pelo chat traz `texto` (mostrado como relato) e `categorias`;
 * registros antigos traziam so campos soltos, que continuam aparecendo um a um.
 */
export function itensDaTriagem(resumo: unknown): ItemTriagem[] {
  if (!resumo || typeof resumo !== 'object') return [];
  const dados = resumo as Record<string, unknown>;

  if (typeof dados['texto'] === 'string' && dados['texto'].trim()) {
    const itens: ItemTriagem[] = [{ chave: 'Relato', valor: dados['texto'].trim() }];
    const queixas = texto(dados['categorias']);
    if (queixas) itens.push({ chave: 'Queixas', valor: queixas });
    return itens;
  }

  return Object.entries(dados)
    .map(([chave, valor]) => ({ chave: ROTULOS[chave] ?? chave, valor: texto(valor) }))
    .filter((item) => item.valor !== '');
}
