// Sonda da identidade visual da sala de vídeo (T157): marca do MedBot, botões enxutos, nada do Jitsi à vista.
//   node sonda-jitsi-marca.mjs <arquivo.json com {medico, paciente}> [pasta-de-prints]
// O arquivo vem de: cd backend && uv run python -c "from app.services.telemedicina_service import url_da_sala as u; ..."
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const [arquivo, OUT = 'out/sonda'] = process.argv.slice(2)
const urls = JSON.parse(fs.readFileSync(arquivo, 'utf8'))
fs.mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch({ args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })

// Botões que a teleconsulta usa. Tudo o mais deve sumir da barra.
const ESPERADOS = ['microphone', 'camera', 'desktop', 'chat', 'select-background', 'tileview', 'fullscreen', 'settings', 'hangup']
const PROIBIDOS = ['invite', 'recording', 'livestreaming', 'security', 'raisehand', 'participants-pane', 'shareaudio', 'sharedvideo', 'whiteboard', 'embedmeeting', 'feedback', 'shortcuts', 'help', 'closedcaptions', 'etherpad']

let falhas = 0
const transborda = (page) => page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
const conferir = (ok, texto) => { console.log(`${ok ? 'OK   ' : 'FALHA'} ${texto}`); if (!ok) falhas++ }

async function entrar(url, largura = 1280) {
  const contexto = await browser.newContext({
    viewport: { width: largura, height: 760 }, permissions: ['camera', 'microphone'], ignoreHTTPSErrors: true,
  })
  const page = await contexto.newPage()
  await page.goto(url)
  await page.waitForFunction(() => { try { return globalThis.APP.conference.isJoined() } catch { return false } }, null, { timeout: 60000 })
  await page.waitForTimeout(4000) // marca dinâmica e barra de botões carregam depois de entrar
  return page
}

try {
  const medico = await entrar(urls.medico)
  const paciente = await entrar(urls.paciente, 390)
  await medico.mouse.move(640, 600) // a barra de botões só aparece com o mouse sobre o vídeo
  await medico.waitForTimeout(800)

  const info = await medico.evaluate(() => {
    const estado = globalThis.APP.store.getState()
    const config = estado['features/base/config']
    const marca = estado['features/dynamic-branding'] ?? {}
    const icone = document.querySelector('link[rel~="icon"]')?.getAttribute('href') ?? ''
    const logos = [...document.querySelectorAll('.watermark, .leftwatermark, [class*="watermark"]')]
      .map((el) => getComputedStyle(el).backgroundImage + ' ' + (el.querySelector('img')?.src ?? ''))
    const caixa = document.querySelector('.leftwatermark')?.getBoundingClientRect()
    return {
      idioma: globalThis.APP.translation?.getCurrentLanguage?.() ?? document.documentElement.lang,
      titulo: document.title,
      icone,
      botoes: config.toolbarButtons ?? null,
      assunto: config.hideConferenceSubject ?? false,
      marcaPronta: marca.customizationReady ?? false,
      fundo: marca.backgroundColor ?? null,
      logoMarca: marca.logoImageUrl ?? null,
      logos,
      larguraLogo: caixa ? Math.round(caixa.width) : 0,
      texto: document.body.innerText,
      terceiros: config.disableThirdPartyRequests ?? false,
    }
  })
  // o arquivo do ícone mantém o nome padrão; o que importa é o conteúdo
  const conteudoIcone = await medico.evaluate(async (href) => (await fetch(href)).text(), info.icone)

  conferir(/MedBot/.test(info.titulo) && !/Jitsi/i.test(info.titulo), `título da aba: "${info.titulo}"`)
  conferir(/medbot/i.test(conteudoIcone), `ícone da aba é o do MedBot (${info.icone})`)
  conferir(/^pt/i.test(info.idioma ?? ''), `idioma da interface: ${info.idioma}`)
  conferir(info.marcaPronta, 'identidade carregada do arquivo de marca')
  conferir(info.fundo?.toLowerCase() === '#0f172a', `cor de fundo: ${info.fundo}`)
  if (urls.logoUnidade) {
    // sala de uma unidade com logo no Receituário: o logo vem da API, num selo branco
    conferir(/\/v1\/salas\/[^/]+\/logo\.png$/.test(info.logoMarca ?? ''), `logo da unidade na sala: ${info.logoMarca}`)
    // carrega como a sala carrega (imagem), e não por fetch: o service worker do Jitsi recusa fetch para outra origem
    const imagem = await medico.evaluate((url) => new Promise((ok) => {
      const img = new Image()
      img.onload = () => ok(`${img.naturalWidth}x${img.naturalHeight}`)
      img.onerror = () => ok('erro')
      img.src = url
    }), info.logoMarca)
    conferir(/^\d+x86$/.test(imagem), `logo da unidade carregado (${imagem})`)
    conferir(info.logos.some((l) => l.includes(info.logoMarca)), `logo exibido: ${info.logos.join(' | ').slice(0, 160)}`)
  } else {
    conferir(info.logoMarca === '/images/medbot-logo.svg', `logo da sala: ${info.logoMarca}`)
    conferir(info.logos.some((l) => /medbot-logo/i.test(l)) && !info.logos.some((l) => /watermark\.svg|jitsilogo/i.test(l)), `logo exibido: ${info.logos.join(' | ').slice(0, 160)}`)
  }
  conferir(info.larguraLogo >= 120, `largura do logo no computador: ${info.larguraLogo}px`)
  const botoes = info.botoes ?? []
  conferir(ESPERADOS.every((b) => botoes.includes(b)), `botões presentes: ${botoes.join(', ')}`)
  conferir(botoes.length > 0 && !PROIBIDOS.some((b) => botoes.includes(b)), `botões removidos: ${PROIBIDOS.filter((b) => botoes.includes(b)).join(', ') || 'nenhum sobrando'}`)
  conferir(info.assunto, 'nome técnico da sala escondido')
  conferir(info.terceiros, 'sem chamadas a serviços de terceiros (avatar, etc.)')
  conferir(!/jitsi/i.test(info.texto), `nenhum "Jitsi" visível na tela do profissional`)

  const textoPaciente = await paciente.evaluate(() => document.body.innerText)
  conferir(!/jitsi/i.test(textoPaciente), 'nenhum "Jitsi" visível na tela do paciente (celular)')

  await medico.screenshot({ path: path.join(OUT, 'marca-profissional.png') })
  await paciente.screenshot({ path: path.join(OUT, 'marca-paciente.png') })

  // o que aparece depois de sair da chamada
  await paciente.evaluate(() => globalThis.APP.conference.hangup())
  await paciente.waitForURL(/\/static\/close/, { timeout: 15000 }).catch(() => {})
  await paciente.waitForTimeout(1500)
  const depois = await paciente.evaluate(() => ({
    url: location.pathname,
    texto: document.body.innerText,
    logo: [...document.images].some((i) => /medbot/i.test(i.src) && i.naturalWidth > 0),
    titulo: document.title,
  }))
  await paciente.screenshot({ path: path.join(OUT, 'marca-saida.png') })
  conferir(/\/static\/close/.test(depois.url), `tela de encerramento aberta (${depois.url})`)
  conferir(/Você saiu da chamada/.test(depois.texto), `texto da tela: "${depois.texto.replace(/\s+/g, ' ').slice(0, 140)}"`)
  conferir(depois.logo && /MedBot/.test(depois.titulo) && !/jitsi/i.test(depois.texto + depois.titulo), 'tela de encerramento com a marca do MedBot e sem Jitsi')
  conferir((await transborda(paciente)) === false, 'tela de encerramento cabe no celular')

  // saiu sem querer: o botão leva de volta para a mesma chamada
  const voltar = paciente.getByRole('button', { name: 'Voltar para a chamada' })
  conferir(await voltar.isVisible().catch(() => false), 'botão "Voltar para a chamada" visível')
  if (await voltar.isVisible().catch(() => false)) {
    await voltar.click()
    const voltou = await paciente.waitForFunction(() => { try { return globalThis.APP.conference.isJoined() } catch { return false } }, null, { timeout: 60000 })
      .then(() => true).catch(() => false)
    // confere pelo identificador da conexão: sobras de execuções anteriores na mesma sala não atrapalham
    const meuId = voltou ? await paciente.evaluate(() => globalThis.APP.conference._room.myUserId()) : null
    await medico.waitForTimeout(2000)
    const medicoVe = await medico.evaluate((id) => globalThis.APP.conference._room.getParticipants().some((p) => p.getId() === id), meuId)
    conferir(voltou && medicoVe, `paciente voltou para a mesma chamada e o profissional o vê (${meuId})`)
  }
} catch (e) {
  console.log('ERRO:', e.message.split('\n').slice(0, 4).join(' | '))
  falhas++
} finally {
  await browser.close()
  console.log(falhas ? `\n${falhas} verificação(ões) falharam` : '\nTudo certo')
  process.exitCode = falhas ? 1 : 0
}
