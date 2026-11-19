// Sonda do painel do profissional: fila própria, pacientes, agenda, guard de rotas e troca de unidade.
//   node sonda-profissional.mjs [pasta-de-prints]
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const ADMIN = process.env.ADMIN || 'http://localhost:4201'
const OUT = process.argv[2] || 'out/sonda'
fs.mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch()

async function entrar(email) {
  const contexto = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await contexto.newPage()
  page.on('console', (m) => { if (m.type() === 'error') console.log('  console.error:', m.text().slice(0, 200)) })
  page.on('response', (r) => { if (r.status() >= 400) console.log('  HTTP', r.status(), r.url().replace(/^https?:\/\/[^/]+/, '')) })
  await page.goto(`${ADMIN}/login`)
  await page.fill('input[formControlName="email"]', email)
  await page.fill('input[formControlName="senha"]', 'Medico@123')
  await page.click('button[type="submit"]')
  await page.waitForURL(/meu-dia/, { timeout: 15000 })
  await page.waitForSelector('.cartoes')
  await page.waitForTimeout(900)
  return page
}
const fila = (page) => page.locator('.item').evaluateAll((itens) => itens.map((li) =>
  [li.querySelector('.item__hora')?.textContent, li.querySelector('.item__nome')?.textContent,
    li.querySelector('.selo')?.textContent, [...li.querySelectorAll('.item__acoes button')].map((b) => b.textContent.trim()).join('|')]
    .map((t) => (t || '').trim()).join(' · ')))

try {
  console.log('— Dr. Fernando (uma unidade)')
  let page = await entrar('fernando.alves@medbot.com')
  console.log('menu:', await page.locator('a.sidebar__nav-item .sidebar__nav-label').allInnerTexts())
  console.log('perfil:', await page.locator('.sidebar__user-role').innerText(), '| título:', await page.locator('.page-header__title').innerText())
  console.log('troca de unidade visível:', await page.locator('.main__toolbar-est').count())
  console.log('fila:', await fila(page))
  await page.screenshot({ path: path.join(OUT, 'prof-1-meu-dia.png') })
  const concluir = page.locator('.item button:has-text("Concluir")').first()
  if (await concluir.count()) { await concluir.click(); await page.waitForTimeout(1500); console.log('após concluir:', await fila(page)) }

  await page.locator('a.sidebar__nav-item[href="/meus-pacientes"]').click()
  await page.waitForSelector('table tr.mat-mdc-row, app-empty-state')
  await page.waitForTimeout(500)
  console.log('meus pacientes:', await page.locator('tr.mat-mdc-row').count(), 'linhas | título:', await page.locator('.page-header__title').innerText())
  await page.screenshot({ path: path.join(OUT, 'prof-2-pacientes.png') })

  await page.locator('a.sidebar__nav-item[href="/agenda"]').click()
  await page.waitForTimeout(2500)
  console.log('agenda — url:', new URL(page.url()).pathname, '| profissionais exibidos:',
    [...new Set(await page.locator('.slot-chip strong, .slot strong, .agenda strong').allInnerTexts())].slice(0, 5))
  await page.screenshot({ path: path.join(OUT, 'prof-3-agenda.png') })

  for (const rota of ['/recepcao', '/clientes', '/dashboard', '/billing', '/usuarios']) {
    await page.goto(ADMIN + rota)
    await page.waitForTimeout(1000)
    console.log(`abrir ${rota} →`, new URL(page.url()).pathname)
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`${ADMIN}/meu-dia`)
  await page.waitForSelector('.cartoes')
  await page.waitForTimeout(600)
  console.log('rolagem horizontal no celular:', await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
  await page.context().close()

  console.log('— Dr. Carlos (duas unidades)')
  page = await entrar('carlos.mendes@medbot.com')
  console.log('unidade atual:', (await page.locator('.main__toolbar-est-label').innerText()).trim(), '| fila:', (await fila(page)).length, 'itens')
  await page.locator('.main__toolbar-est').click()
  const opcoes = await page.locator('.mat-mdc-menu-item').allInnerTexts()
  console.log('unidades no menu:', opcoes.map((t) => t.replace(/\s+/g, ' ').trim()))
  const atual = (await page.locator('.main__toolbar-est-label').innerText()).trim()
  await page.locator('.mat-mdc-menu-item', { hasNotText: atual }).first().click()
  await page.waitForTimeout(2500)
  console.log('após trocar — unidade:', (await page.locator('.main__toolbar-est-label').innerText()).trim(),
    '| url:', new URL(page.url()).pathname, '| fila:', (await fila(page)).length, 'itens')
  await page.screenshot({ path: path.join(OUT, 'prof-4-outra-unidade.png') })
} catch (e) {
  console.log('FALHOU:', e.message.split('\n')[0])
} finally {
  await browser.close()
}
