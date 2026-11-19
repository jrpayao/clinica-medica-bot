/** Papel timbrado da unidade (G29): contrato de /estabelecimentos/meu/papel-timbrado e regras de tela. */

export interface PapelTimbrado {
  tem_logo: boolean;
  marca_dagua: boolean;
  rodape: string | null;
  atualizado_em: string | null;
}

export const TAMANHO_MAXIMO_BYTES = 2 * 1024 * 1024;
export const TAMANHO_RODAPE = 300;
const TIPOS_ACEITOS = ['image/png', 'image/jpeg'];

/** Motivo para recusar o arquivo antes de enviar, ou null se pode seguir (o servidor confere de novo). */
export function erroDoArquivo(arquivo: { type: string; size: number }): string | null {
  if (!TIPOS_ACEITOS.includes(arquivo.type)) return 'Use uma imagem PNG ou JPEG.';
  if (arquivo.size > TAMANHO_MAXIMO_BYTES) return 'A imagem precisa ter até 2 MB.';
  if (arquivo.size === 0) return 'O arquivo está vazio.';
  return null;
}

/** A marca-d'água é o próprio logo: sem logo, a opção não tem efeito. */
export function marcaDaguaAtiva(p: Pick<PapelTimbrado, 'tem_logo' | 'marca_dagua'>): boolean {
  return p.tem_logo && p.marca_dagua;
}
