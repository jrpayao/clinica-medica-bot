// Sonda do Receituário: envio de logo, opções, exemplo em PDF e bloqueio para outros perfis.
//   node sonda-receituario.mjs <logo.png> [pasta-de-prints]
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const [logo, OUT = 'out/sonda'] = process.argv.slice(2)
if (!logo) { console.log('uso: node sonda-receituario.mjs <logo.png> [pasta]'); process.exit(1) }
const ADMIN = process.env.ADMIN || 'http://localhost:4201'
fs.mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch()
const limpo = (t) => t.replace(/\s+/g, ' ').trim()

async function entrar(email, senha, destino) {
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
  page.on('response', (r) => { if (r.status() >= 400) console.log('  HTTP', r.status(), r.url().replace(/^https?:\/\/[^/]+/, '')) })
  await page.goto(`${ADMIN}/login`)
  await page.fill('input[formControlName="email"]', email)
  await page.fill('input[formControlName="senha"]', senha)
  await page.click('button[type="submit"]')
  await page.waitForURL(destino, { timeout: 15000 })
  await page.waitForTimeout(600)
  return page
}

try {
  const page = await entrar('admin@clinica-vida.com', 'Admin@123', /dashboard/)
  await page.goto(`${ADMIN}/receituario`)
  await page.waitForSelector('.cartao')
  console.log('antes:', limpo(await page.locator('.logo').innerText()), '| salvar habilitado:', await page.getByRole('button', { name: 'Salvar opções' }).isEnabled())

  await page.locator('input[type=file]').setInputFiles({ name: 'nota.txt', mimeType: 'text/plain', buffer: Buffer.from('x') })
  console.log('arquivo de texto:', limpo(await page.locator('.erro').innerText()))

  await page.locator('input[type=file]').setInputFiles(logo)
  await page.waitForSelector('.logo img', { timeout: 10000 })
  console.log('logo enviado: prévia na tela =', await page.locator('.logo img').count(), '| nota:', limpo(await page.locator('#t-opcoes ~ .nota').first().innerText()))

  await page.locator('input[matInput]').fill('Atendimento de segunda a sexta, das 8h às 18h')
  await page.getByRole('button', { name: 'Salvar opções' }).click()
  await page.waitForTimeout(1000)
  console.log('depois de salvar: botão habilitado =', await page.getByRole('button', { name: 'Salvar opções' }).isEnabled())

  const [aba] = await Promise.all([
    page.context().waitForEvent('page', { timeout: 10000 }).catch(() => null),
    page.getByRole('button', { name: 'Ver exemplo' }).click(),
  ])
  console.log('exemplo abriu em nova aba:', !!aba)
  await page.screenshot({ path: path.join(OUT, 'receituario.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForTimeout(300)
  console.log('rolagem horizontal no celular:', await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))

  await page.reload()
  await page.waitForSelector('.logo img', { timeout: 10000 })
  console.log('após recarregar: rodapé =', await page.locator('input[matInput]').inputValue())

  const medico = await entrar('fernando.alves@medbot.com', 'Medico@123', /meu-dia/)
  await medico.goto(`${ADMIN}/receituario`)
  await medico.waitForTimeout(1000)
  console.log('profissional abrindo /receituario →', new URL(medico.url()).pathname)
} catch (e) {
  console.log('FALHOU:', e.message.split('\n').slice(0, 6).join(' | '))
} finally {
  await browser.close()
}
