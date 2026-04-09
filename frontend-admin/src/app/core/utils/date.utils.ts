/**
 * Retorna a data LOCAL no formato YYYY-MM-DD.
 *
 * `new Date().toISOString().slice(0, 10)` retorna a data UTC, que no
 * fuso Brasil (UTC-3) pode ser um dia atrás após 21h. Esta função usa
 * os getters locais para evitar a troca de dia.
 */
export function localDateString(date: Date = new Date()): string {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
}
