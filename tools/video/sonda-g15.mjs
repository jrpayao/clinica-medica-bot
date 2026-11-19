// Sonda das telas do G15: relatórios, lista de espera, cancelamento com motivo e triagem no Meu dia.
//   node sonda-g15.mjs [pasta-de-prints]
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const ADMIN = process.env.ADMIN || 'http://localhost:4201'
const OUT = process.argv[2] || 'out/sonda'
fs.mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch()

async function entrar(email, senha, destino) {
  const contexto = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await contexto.newPage()
  page.on('console', (m) => { if (m.type() === 'error') console.log('  console.error:', m.text().slice(0, 200)) })
  page.on('response', (r) => { if (r.status() >= 400) console.log('  HTTP', r.status(), r.url().replace(/^https?:\/\/[^/]+/, '')) })
  await page.goto(`${ADMIN}/login`)
  await page.fill('input[formControlName="email"]', email)
  await page.fill('input[formControlName="senha"]', senha)
  await page.click('button[type="submit"]')
  await page.waitForURL(destino, { timeout: 15000 })
  await page.waitForTimeout(800)
  return page
}
const transborda = (page) => page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
const foto = (page, nome) => page.screenshot({ path: path.join(OUT, nome), fullPage: true })

try {
  console.log('— Gestor da unidade')
  let page = await entrar('admin@clinica-vida.com', 'Admin@123', /dashboard/)
  console.log('menu:', (await page.locator('a.sidebar__nav-item .sidebar__nav-label').allInnerTexts()).join(' | '))

  await page.goto(`${ADMIN}/relatorios`)
  await page.waitForSelector('.indicadores')
  await page.waitForTimeout(600)
  console.log('indicadores:', (await page.locator('.indicador').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ')).join(' || '))
  console.log('painéis:', (await page.locator('.painel h2').allInnerTexts()).join(' | '))
  console.log('ocupação:', (await page.locator('#t-ocupacao ~ .barras .barra').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ')).join(' || '))
  console.log('NPS:', (await page.locator('.nps__placar').innerText()).replace(/\s+/g, ' '))
  await foto(page, 'g15-1-relatorios.png')
  await page.locator('mat-button-toggle', { hasText: '7 dias' }).click()
  await page.waitForTimeout(1200)
  console.log('7 dias → ocupação:', (await page.locator('.indicador').first().innerText()).replace(/\s+/g, ' '))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForTimeout(400)
  console.log('relatórios — rolagem horizontal no celular:', await transborda(page))
  await foto(page, 'g15-2-relatorios-celular.png')
  await page.setViewportSize({ width: 1440, height: 900 })

  await page.goto(`${ADMIN}/fila-espera`)
  await page.waitForSelector('.bloco')
  await page.waitForTimeout(500)
  console.log('pendências:', (await page.locator('.linha--pendencia').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ')))
  console.log('fila:', (await page.locator('.linha:not(.linha--pendencia)').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ')))
  await foto(page, 'g15-3-fila.png')
  await page.getByRole('button', { name: 'Incluir na lista' }).click()
  await page.waitForSelector('.inclusao input')
  await page.fill('.inclusao input', 'a')
  await page.fill('.inclusao input', 'ma')
  await page.waitForTimeout(500)
  const sugestoes = await page.locator('.sugestoes button').allInnerTexts()
  console.log('sugestões para "ma":', sugestoes.map((t) => t.replace(/\s+/g, ' ')))
  if (sugestoes.length) {
    await page.locator('.sugestoes button').last().click()
    await page.getByRole('button', { name: 'Incluir', exact: true }).click()
    await page.waitForTimeout(1200)
    console.log('fila após incluir:', await page.locator('.linha:not(.linha--pendencia)').count(), 'pessoas')
  }
  await page.locator('.linha:not(.linha--pendencia) button').last().click()
  await page.getByRole('button', { name: 'Tirar da lista' }).click()
  await page.waitForTimeout(1000)
  console.log('fila após tirar:', await page.locator('.linha:not(.linha--pendencia)').count(), 'pessoas')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForTimeout(300)
  console.log('lista de espera — rolagem horizontal no celular:', await transborda(page))
  await page.setViewportSize({ width: 1440, height: 900 })

  await page.goto(`${ADMIN}/atendimentos`)
  await page.waitForTimeout(2000)
  const paineis = page.locator('mat-expansion-panel', { hasText: /AGENDADA|CONFIRMADA/ })
  console.log('atendimentos canceláveis na tela:', await paineis.count())
  if (await paineis.count()) {
    await paineis.first().locator('mat-expansion-panel-header').click()
    await page.waitForTimeout(500)
    console.log('triagem no detalhe:', (await paineis.first().locator('.triagem-list').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ')))
    const cancelar = paineis.first().locator('.detail-actions button', { hasText: 'Cancelar' })
    await cancelar.click()
    await page.waitForSelector('app-cancelar-dialog')
    console.log('diálogo:', (await page.locator('app-cancelar-dialog h2').innerText()).trim(),
      '| opções:', (await page.locator('app-cancelar-dialog mat-radio-button').allInnerTexts()).map((t) => t.trim()).join(' / '),
      '| confirmar desabilitado:', await page.getByRole('button', { name: 'Cancelar horário' }).isDisabled())
    await page.locator('app-cancelar-dialog mat-radio-button').nth(1).click()
    console.log('efeito:', (await page.locator('app-cancelar-dialog .efeito').innerText()).trim())
    await foto(page, 'g15-4-cancelar.png')
    await page.getByRole('button', { name: 'Voltar' }).click()
  }
  await page.context().close()

  console.log('— Recepção')
  page = await entrar('bruno@clinica-vida.com', 'Bruno@123', /recepcao/)
  console.log('menu:', (await page.locator('a.sidebar__nav-item .sidebar__nav-label').allInnerTexts()).join(' | '))
  await page.goto(`${ADMIN}/relatorios`)
  await page.waitForTimeout(1000)
  console.log('abrir /relatorios →', new URL(page.url()).pathname)
  await page.context().close()

  console.log('— Profissional')
  page = await entrar('carlos.mendes@medbot.com', 'Medico@123', /meu-dia/)
  await page.waitForSelector('.cartoes')
  const triagens = page.locator('details.triagem')
  console.log('atendimentos com triagem:', await triagens.count(), 'de', await page.locator('.item').count())
  if (await triagens.count()) {
    await triagens.first().locator('summary').click()
    console.log('triagem:', (await triagens.first().innerText()).replace(/\s+/g, ' ').slice(0, 260))
  }
  await foto(page, 'g15-5-meu-dia.png')
  await page.goto(`${ADMIN}/fila-espera`)
  await page.waitForTimeout(1000)
  console.log('abrir /fila-espera →', new URL(page.url()).pathname)
} catch (e) {
  console.log('FALHOU:', e.message.split('\n')[0])
} finally {
  await browser.close()
}
