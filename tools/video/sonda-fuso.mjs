// Sonda: ADMIN_GLOBAL edita o fuso horário de uma unidade e a alteração persiste.
import { chromium } from 'playwright'
const ADMIN = process.env.ADMIN || 'http://localhost:4201'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.on('response', (r) => { if (r.status() >= 400) console.log('HTTP', r.status(), r.url().replace(/^https?:\/\/[^/]+/, '')) })
try {
  await page.goto(`${ADMIN}/login`)
  await page.fill('input[formControlName="email"]', 'admin@medbot.com')
  await page.fill('input[formControlName="senha"]', 'Admin@123')
  await page.click('button[type="submit"]')
  await page.waitForURL(/selecionar-estabelecimento|dashboard/)
  await page.goto(`${ADMIN}/estabelecimentos`)
  await page.waitForSelector('table tr.mat-mdc-row')
  const editar = async (rotulo) => {
    await page.locator('tr.mat-mdc-row', { hasText: 'Clínica Vida Saúde' }).locator('button').first().click()
    await page.waitForSelector('mat-select[formControlName="timezone"]')
    console.log('fuso ao abrir:', (await page.locator('mat-select[formControlName="timezone"]').innerText()).trim())
    await page.locator('mat-select[formControlName="timezone"]').click()
    await page.locator('mat-option', { hasText: rotulo }).click()
    const resposta = page.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().includes('/estabelecimentos/'), { timeout: 8000 })
    await page.locator('form button[type="submit"]').click()
    const r = await resposta
    console.log('PATCH', r.status(), 'timezone salvo:', (await r.json()).timezone)
    await page.waitForTimeout(600)
  }
  await editar('Amazonas')
  await editar('Horário de Brasília')
} catch (e) {
  console.log('FALHOU:', e.message.split('\n')[0])
  await page.screenshot({ path: 'out/fuso-falha.png' })
} finally { await browser.close() }
