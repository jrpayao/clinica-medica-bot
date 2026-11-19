// Utilitários compartilhados: ffmpeg (ffmpeg-static), duração de áudio, caminhos.
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import ffmpegPath from 'ffmpeg-static'

export const FFMPEG = ffmpegPath

export function ffmpeg(args, { quiet = true } = {}) {
  const r = spawnSync(FFMPEG, ['-hide_banner', ...(quiet ? ['-loglevel', 'error'] : []), ...args], { encoding: 'utf8', maxBuffer: 1 << 28 })
  if (r.status !== 0 && quiet) throw new Error(`ffmpeg falhou: ${args.join(' ')}\n${r.stderr}`)
  return r
}

// Duração (s) lida do stderr do ffmpeg ("Duration: 00:00:12.34"). Dispensa ffprobe.
export function duracao(arquivo) {
  const r = spawnSync(FFMPEG, ['-hide_banner', '-i', arquivo], { encoding: 'utf8' })
  const m = /Duration: (\d+):(\d+):(\d+(?:\.\d+)?)/.exec(r.stderr)
  if (!m) throw new Error(`sem duração: ${arquivo}`)
  return Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3])
}

import { createHash } from 'node:crypto'
// nome inclui um hash do texto: editar a fala invalida o cache sozinho
export const arquivoFala = (narrDir, voz, cena, k) => path.join(narrDir, `${cena.id}-${k}-${voz}-${createHash('sha1').update(cena.falas[k].texto).digest('hex').slice(0, 8)}.mp3`)
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
