// Sonda: gestor da unidade cria acesso de profissional vinculado à agenda e o novo acesso entra no próprio dia.
import { chromium } from 'playwright'
const ADMIN = process.env.ADMIN || 'http://localhost:4201'
const API = process.env.API || 'http://localhost:8100/v1'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.on('response', (r) => { if (r.status() >= 400) console.log('  HTTP', r.status(), r.url().replace(/^https?:\/\/[^/]+/, '')) })
try {
  await page.goto(`${ADMIN}/login`)
  await page.fill('input[formControlName="email"]', 'admin@clinica-vida.com')
  await page.fill('input[formControlName="senha"]', 'Admin@123')
  await page.click('button[type="submit"]')
  await page.waitForURL(/dashboard/)
  await page.goto(`${ADMIN}/usuarios`)
  await page.waitForSelector('mat-card input')
  console.log('perfis na tabela:', [...new Set(await page.locator('td mat-chip').allInnerTexts())])
  const email = `sonda.${Date.now()}@clinica-vida.com`
  await page.locator('mat-card input').nth(0).fill('Acesso de Sonda')
  await page.locator('mat-card input').nth(1).fill(email)
  await page.locator('mat-card input').nth(2).fill('Sonda@1234')
  await page.locator('mat-card mat-select').first().click()
  await page.locator('mat-option').nth(1).click()
  await page.locator('mat-card button:has-text("Criar")').click()
  await page.waitForTimeout(1200)
  console.log('sem escolher a agenda:', (await page.locator('mat-card-footer').innerText().catch(() => '(sem aviso)')).trim())
  await page.locator('mat-select').nth(1).focus()
  await page.keyboard.press('Enter')
  await page.waitForSelector('mat-option')
  console.log('agendas oferecidas:', await page.locator('mat-option').allInnerTexts())
  await page.locator('mat-option', { hasText: 'Fernando' }).click()
  await page.locator('mat-card button:has-text("Criar")').click()
  await page.waitForTimeout(1200)
  console.log('agenda que já tem acesso:', (await page.locator('mat-card-footer').innerText().catch(() => '(sem aviso)')).trim())
} catch (e) { console.log('FALHOU:', e.message.split('\n')[0]) } finally { await browser.close() }
