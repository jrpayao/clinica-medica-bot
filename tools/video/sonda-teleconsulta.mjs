// Sonda da telemedicina: paciente (portal) e profissional (painel) na mesma teleconsulta.
// Antes: cd backend && uv run python scripts/demo_teleconsulta.py   (imprime token e atendimento_id)
//   node sonda-teleconsulta.mjs <token> <atendimento_id> [pasta-de-prints]
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const [token, atendimentoId, OUT = 'out/sonda'] = process.argv.slice(2)
if (!token || !atendimentoId) {
  console.log('uso: node sonda-teleconsulta.mjs <token> <atendimento_id> [pasta]')
  process.exit(1)
}
const ADMIN = process.env.ADMIN || 'http://localhost:4201'
const PORTAL = process.env.PORTAL || 'http://localhost:4200'
const EMAIL = process.env.EMAIL || 'carlos.mendes@medbot.com'
fs.mkdirSync(OUT, { recursive: true })
// Câmera e microfone simulados pelo navegador, para a chamada acontecer de verdade quando o Jitsi é o próprio
const browser = await chromium.launch({ args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })

async function pagina(nome, largura = 1440) {
  const contexto = await browser.newContext({
    viewport: { width: largura, height: 900 }, permissions: ['camera', 'microphone'], ignoreHTTPSErrors: true,
  })
  // A sonda confere que a sala certa é entregue; a chamada de vídeo em si não é aberta
  await contexto.route(/meet\.jit\.si/, (rota) => rota.abort())
  const page = await contexto.newPage()
  page.on('console', (m) => {
    if (m.type() === 'error' && !/meet\.jit\.si|ERR_FAILED/.test(m.text())) console.log(`  [${nome}] console.error:`, m.text().slice(0, 160))
  })
  page.on('response', (r) => { if (r.status() >= 400) console.log(`  [${nome}] HTTP`, r.status(), r.url().replace(/^https?:\/\/[^/]+/, '')) })
  return page
}
const limpo = (t) => t.replace(/\s+/g, ' ').trim()
const transborda = (page) => page.evaluate(() => document.documentElement.scrollWidth > innerWidth)

try {
  console.log('— Paciente abre o link')
  const paciente = await pagina('paciente', 390)
  await paciente.goto(`${PORTAL}/teleconsulta/${token}`)
  await paciente.waitForSelector('.resumo')
  console.log('cabeçalho:', limpo(await paciente.locator('.resumo').innerText()))
  if (await paciente.locator('.termo').count()) {
    console.log('termo:', await paciente.locator('.termo li').count(), 'itens | botão desabilitado:', await paciente.locator('.botao').isDisabled())
    await paciente.screenshot({ path: path.join(OUT, 'tele-1-termo.png'), fullPage: true })
    await paciente.locator('.aceite input').check()
    await paciente.locator('.botao').click()
  } else {
    console.log('termo: já aceito em uma visita anterior')
  }
  await paciente.waitForSelector('.pulso', { timeout: 10000 })
  console.log('depois do aceite:', limpo(await paciente.locator('.cartao--centro h3').innerText()))
  console.log('paciente — rolagem horizontal no celular:', await transborda(paciente))
  await paciente.screenshot({ path: path.join(OUT, 'tele-2-espera.png'), fullPage: true })

  console.log('— Profissional')
  const medico = await pagina('medico')
  await medico.goto(`${ADMIN}/login`)
  await medico.fill('input[formControlName="email"]', EMAIL)
  await medico.fill('input[formControlName="senha"]', 'Medico@123')
  await medico.click('button[type="submit"]')
  await medico.waitForURL(/meu-dia/, { timeout: 15000 })
  await medico.waitForSelector('.cartoes')
  await medico.waitForTimeout(800)
  const linha = medico.locator('.item', { has: medico.locator('.selo--online') }).first()
  console.log('Meu dia — atendimentos online:', await medico.locator('.selo--online').count(),
    '| ações da linha:', limpo(await linha.locator('.item__acoes').innerText()))
  await medico.screenshot({ path: path.join(OUT, 'tele-3-meu-dia.png'), fullPage: true })

  await medico.goto(`${ADMIN}/atender/${atendimentoId}`)
  await medico.waitForSelector('.topo')
  await medico.waitForTimeout(1000)
  console.log('topo:', limpo(await medico.locator('.topo').innerText()))
  console.log('presença:', limpo(await medico.locator('.presenca').innerText()))
  console.log('triagem:', limpo(await medico.locator('#t-triagem ~ .cartao__texto').innerText()).slice(0, 120))
  console.log('documentos antes de iniciar:', limpo(await medico.locator('#t-docs ~ .cartao__nota').first().innerText()))
  await medico.getByRole('button', { name: 'Entrar na sala' }).click()
  console.log('quadro do profissional:', (await medico.locator('iframe.video__quadro').getAttribute('src')).split(/[?#]/)[0])
  await medico.screenshot({ path: path.join(OUT, 'tele-4-atender.png'), fullPage: true })

  await medico.getByRole('button', { name: 'Iniciar atendimento' }).click()
  await medico.waitForSelector('button:has-text("Concluir")', { timeout: 10000 })
  await paciente.waitForSelector('iframe.video', { timeout: 15000 })
  const salaPaciente = (await paciente.locator('iframe.video').getAttribute('src')).split('#')[0]
  const salaMedico = (await medico.locator('iframe.video__quadro').getAttribute('src')).split('#')[0]
  console.log('paciente recebeu a sala:', salaPaciente.split('?')[0], '| mesma do profissional:', salaPaciente.split('?')[0] === salaMedico.split('?')[0],
    '| acesso assinado:', salaPaciente.includes('jwt='), salaMedico.includes('jwt='))
  if (!/meet\.jit\.si/.test(salaMedico)) {
    // Jitsi próprio: confere a chamada dentro dos dois quadros
    const naChamada = async (page, seletor) => {
      const quadro = await (await page.locator(seletor).elementHandle()).contentFrame()
      await quadro.waitForFunction(() => { try { return globalThis.APP?.conference?._room?.getParticipants?.().length === 1 } catch { return false } }, null, { timeout: 60000 })
      return quadro.evaluate(() => ({ entrou: globalThis.APP.conference.isJoined(), papel: globalThis.APP.conference._room.getRole(), midia: globalThis.APP.conference._room.getConnectionState() }))
    }
    console.log('chamada — profissional:', JSON.stringify(await naChamada(medico, 'iframe.video__quadro')))
    console.log('chamada — paciente:    ', JSON.stringify(await naChamada(paciente, 'iframe.video')))
    await medico.waitForTimeout(4000)
    await medico.screenshot({ path: path.join(OUT, 'tele-4b-chamada.png') })
  }

  await medico.locator('textarea').nth(0).fill('Tosse seca há cinco dias')
  await medico.locator('textarea').nth(1).fill('Sem febre. Piora noturna.')
  await medico.locator('textarea').nth(2).fill('Hidratação e retorno em 7 dias.')
  await medico.waitForFunction(() => document.querySelector('.salvamento')?.textContent?.trim() === 'Salvo', null, { timeout: 10000 })
  console.log('registro:', limpo(await medico.locator('.salvamento').innerText()))

  await medico.getByRole('button', { name: 'Nova receita' }).click()
  await medico.getByRole('button', { name: 'Emitir receita' }).click()
  console.log('receita vazia:', limpo(await medico.locator('.erro').innerText()))
  await medico.locator('.item input').nth(0).fill('Xarope de guaco')
  await medico.locator('.item input').nth(1).fill('10 ml a cada 8 horas por 5 dias')
  const [aba] = await Promise.all([
    medico.context().waitForEvent('page', { timeout: 10000 }).catch(() => null),
    medico.getByRole('button', { name: 'Emitir receita' }).click(),
  ])
  console.log('PDF abriu em nova aba:', !!aba)
  await medico.waitForSelector('.documentos li')
  console.log('documentos:', (await medico.locator('.documentos li span').allInnerTexts()).map(limpo))

  await medico.getByRole('button', { name: 'Novo atestado' }).click()
  await medico.locator('input[name="dias"]').fill('2')
  await medico.getByRole('button', { name: 'Emitir atestado' }).click()
  await medico.waitForFunction(() => document.querySelectorAll('.documentos li').length === 2, null, { timeout: 10000 })
  console.log('documentos:', (await medico.locator('.documentos li span').allInnerTexts()).map(limpo))
  await medico.screenshot({ path: path.join(OUT, 'tele-5-documentos.png'), fullPage: true })

  await medico.getByRole('button', { name: 'Concluir' }).click()
  await paciente.waitForSelector('text=Atendimento encerrado', { timeout: 15000 })
  console.log('paciente:', limpo(await paciente.locator('.cartao--centro h3').innerText()),
    '| documentos:', (await paciente.locator('.documentos li span').allInnerTexts()).join(', '),
    '| vídeo ainda na tela:', await paciente.locator('iframe.video').count())
  const pdf = await paciente.request.get(await paciente.locator('.documentos a').first().getAttribute('href'))
  console.log('PDF do paciente:', pdf.status(), pdf.headers()['content-type'], (await pdf.body()).subarray(0, 5).toString())
  await paciente.screenshot({ path: path.join(OUT, 'tele-6-encerrada.png'), fullPage: true })
  console.log('profissional — status final:', limpo(await medico.locator('.selo--status').innerText()),
    '| sala:', limpo(await medico.locator('.video__espera p').innerText()))

  console.log('— Agenda do profissional')
  await medico.goto(`${ADMIN}/agenda`)
  await medico.waitForTimeout(2500)
  await medico.locator('button[aria-label="Próximo dia"]').click()
  await medico.waitForTimeout(2000)
  const barra = medico.locator('.online-bar')
  console.log('barra online:', (await barra.count()) ? limpo(await barra.innerText()) : '(sem horários livres neste dia)')

  console.log('— Link inválido')
  await paciente.goto(`${PORTAL}/teleconsulta/token-errado`)
  await paciente.waitForSelector('.cartao--centro')
  console.log(limpo(await paciente.locator('.cartao--centro').innerText()).slice(0, 80))
} catch (e) {
  console.log('FALHOU:', e.message.split('\n')[0])
} finally {
  await browser.close()
}
