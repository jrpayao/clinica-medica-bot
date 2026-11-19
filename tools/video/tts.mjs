// Narração: 1 mp3 por fala via OpenAI TTS, com cache por voz em <out>/narracao/.
// Chave em SECRET_KEY_OPENAI ou OPENAI_API_KEY (só no ambiente; nunca em disco).
// TTS_FAKE=1 gera silêncio com duração estimada (≈ 15 caracteres/s) para testar a pipeline sem custo.
import fs from 'node:fs'
import { ffmpeg, duracao, arquivoFala } from './comum.mjs'

export async function gerarNarracao(CENAS, { narrDir, voz = 'onyx', modelo = 'tts-1', fake = process.env.TTS_FAKE === '1' } = {}) {
  fs.mkdirSync(narrDir, { recursive: true })
  const chave = process.env.SECRET_KEY_OPENAI || process.env.OPENAI_API_KEY
  let chars = 0
  for (const cena of CENAS) {
    for (const [k, fala] of cena.falas.entries()) {
      const arq = arquivoFala(narrDir, voz, cena, k)
      if (fs.existsSync(arq)) continue
      if (fake) {
        const seg = Math.max(1.5, fala.texto.length / 15)
        ffmpeg(['-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', seg.toFixed(2), '-c:a', 'libmp3lame', '-q:a', '9', arq])
        continue
      }
      if (!chave) throw new Error('SECRET_KEY_OPENAI/OPENAI_API_KEY ausente no ambiente (ou use TTS_FAKE=1 para testar)')
      const r = await fetch('https://api.openai.com/v1/audio/speech', {
        method: 'POST',
        headers: { Authorization: `Bearer ${chave}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelo, voice: voz, input: fala.texto, response_format: 'mp3' }),
      })
      if (!r.ok) throw new Error(`TTS ${cena.id}-${k}: HTTP ${r.status} ${(await r.text()).slice(0, 200)}`)
      fs.writeFileSync(arq, Buffer.from(await r.arrayBuffer()))
      chars += fala.texto.length
      console.log(`  narração ${cena.id}-${k} gerada`)
    }
  }
  const duracoes = CENAS.map((c) => c.falas.map((_, k) => duracao(arquivoFala(narrDir, voz, c, k))))
  return { duracoes, chars }
}
