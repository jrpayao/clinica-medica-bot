// Sonda do Jitsi próprio: chamada real entre dois participantes (câmera e microfone simulados pelo navegador)
// e recusa de quem chega sem acesso assinado ou com acesso de outra sala.
//   node sonda-jitsi.mjs <arquivo.json com {medico, paciente, outra}> [pasta-de-prints]
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const [arquivo, OUT = 'out/sonda'] = process.argv.slice(2)
const urls = JSON.parse(fs.readFileSync(arquivo, 'utf8'))
fs.mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch({
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
})

async function entrar(url) {
  const contexto = await browser.newContext({ viewport: { width: 1000, height: 700 }, permissions: ['camera', 'microphone'], ignoreHTTPSErrors: true })
  const page = await contexto.newPage()
  await page.goto(url)
  return page
}
// Estado da conferência lido da própria aplicação do Jitsi
const estado = (page) => page.evaluate(() => {
  const c = globalThis.APP?.conference
  const sala = c?._room
  return {
    entrou: !!c?.isJoined?.(),
    participantes: sala ? sala.getParticipants().length + 1 : 0,
    nome: globalThis.APP?.conference?.getLocalDisplayName?.() ?? null,
    moderador: sala?.isModerator?.() ?? null,
    papel: sala?.getRole?.() ?? null,
    papelDoOutro: sala?.getParticipants?.().map((p) => p.getRole?.()).join(',') ?? null,
    midia: sala?.getConnectionState?.() ?? null,
    cameraLigada: c?.isLocalVideoMuted ? !c.isLocalVideoMuted() : null,
    videoRecebido: sala ? sala.getParticipants().filter((p) => p.getTracksByMediaType('video').some((t) => !t.isMuted())).length : 0,
    videoRemoto: [...document.querySelectorAll('video')].filter((v) => v.id !== 'localVideo_container' && v.videoWidth > 0).length,
  }
}).catch((e) => ({ erro: e.message.split('\n')[0] }))

try {
  const medico = await entrar(urls.medico)
  const paciente = await entrar(urls.paciente)
  await medico.waitForFunction(() => {
    try { return globalThis.APP?.conference?._room?.getParticipants?.().length === 1 } catch { return false }
  }, null, { timeout: 60000 })
  await medico.waitForTimeout(8000) // tempo para a mídia entre os dois se estabelecer
  // no navegador sem tela a câmera simulada começa desligada: liga nos dois lados e espera a imagem chegar
  for (const p of [medico, paciente]) await p.evaluate(() => globalThis.APP.conference.muteVideo(false))
  await medico.waitForTimeout(8000)
  console.log('médico:  ', JSON.stringify(await estado(medico)))
  console.log('paciente:', JSON.stringify(await estado(paciente)))
  await medico.screenshot({ path: path.join(OUT, 'jitsi-chamada.png') })

  const semAcesso = await entrar(urls.medico.split('?')[0])
  await semAcesso.waitForTimeout(10000)
  console.log('sem acesso assinado:', JSON.stringify(await estado(semAcesso)))
  await semAcesso.screenshot({ path: path.join(OUT, 'jitsi-sem-acesso.png') })

  // acesso assinado para outra sala, usado na sala da consulta
  const jwtDeOutraSala = urls.outra.split('?')[1].split('#')[0]
  const trocado = await entrar(`${urls.medico.split('?')[0]}?${jwtDeOutraSala}`)
  await trocado.waitForTimeout(10000)
  console.log('acesso de outra sala:', JSON.stringify(await estado(trocado)))
  console.log('participantes na sala ao final:', (await estado(medico)).participantes)
} catch (e) {
  console.log('FALHOU:', e.message.split('\n').slice(0, 4).join(' | '))
  for (const [i, c] of browser.contexts().entries()) for (const p of c.pages()) await p.screenshot({ path: path.join(OUT, `jitsi-falha-${i}.png`) }).catch(() => {})
} finally {
  await browser.close()
}
