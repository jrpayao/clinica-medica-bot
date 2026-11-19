// Sonda do painel da recepção: entra como recepcionista, fotografa a fila, registra uma chegada e testa o guard.
//   node sonda-recepcao.mjs [pasta-de-prints]
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const ADMIN = process.env.ADMIN || 'http://localhost:4201'
const OUT = process.argv[2] || 'out/sonda'
fs.mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.on('console', (m) => { if (m.type() === 'error') console.log('console.error:', m.text().slice(0, 220)) })
page.on('response', (r) => { if (r.status() >= 400) console.log('HTTP', r.status(), r.url().replace(/^https?:\/\/[^/]+/, '')) })
try {
  await page.goto(`${ADMIN}/login`)
  await page.fill('input[formControlName="email"]', 'bruno@clinica-vida.com')
  await page.fill('input[formControlName="senha"]', 'Bruno@123')
  await page.click('button[type="submit"]')
  await page.waitForURL(/recepcao/, { timeout: 15000 })
  await page.waitForSelector('.cartoes')
  await page.waitForTimeout(800)
  console.log('url após login:', new URL(page.url()).pathname)
  console.log('menu:', await page.locator('a.sidebar__nav-item .sidebar__nav-label').allInnerTexts())
  console.log('perfil no rodapé:', await page.locator('.sidebar__user-role').innerText())
  console.log('cartões:', (await page.locator('.cartao').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ')))
  console.log('itens na fila:', await page.locator('.item').count())
  await page.screenshot({ path: path.join(OUT, 'recepcao-1.png') })
  const chegada = page.locator('.item button:has-text("Registrar chegada")').first()
  if (await chegada.count()) {
    const nome = await chegada.locator('xpath=ancestor::li').locator('.item__nome').innerText()
    await chegada.click()
    await page.waitForTimeout(1500)
    console.log('chegada registrada de:', nome)
    console.log('cartões depois:', (await page.locator('.cartao').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ')))
    await page.locator('.cartao', { hasText: 'Na recepção' }).click()
    await page.waitForTimeout(500)
    await page.screenshot({ path: path.join(OUT, 'recepcao-2.png') })
  }
  for (const rota of ['/billing', '/dashboard', '/usuarios', '/profissionais']) {
    await page.goto(ADMIN + rota)
    await page.waitForTimeout(1200)
    console.log(`abrir ${rota} →`, new URL(page.url()).pathname)
  }
  console.log('botão de adicionar em profissionais:', await page.locator('app-page-header button').count())
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`${ADMIN}/recepcao`)
  await page.waitForSelector('.cartoes')
  await page.waitForTimeout(800)
  console.log('rolagem horizontal no celular:', await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
  await page.screenshot({ path: path.join(OUT, 'recepcao-celular.png') })
} catch (e) {
  console.log('FALHOU:', e.message.split('\n')[0], '| url:', page.url())
  await page.screenshot({ path: path.join(OUT, 'recepcao-falha.png') })
} finally {
  await browser.close()
}
