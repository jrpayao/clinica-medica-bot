// Varredura das telas: entra com cada perfil, visita cada rota e registra
// erros de console, respostas HTTP >= 400 e um print de página inteira.
// Uso: node varredura.mjs [pasta-de-saida]
import { chromium } from 'playwright'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const SAIDA = process.argv[2] || 'out/varredura'
const ADMIN = 'http://localhost:4201'
const PORTAL = 'http://localhost:4200'
mkdirSync(SAIDA, { recursive: true })

const PERFIS = [
  {
    id: 'global', email: 'admin@medbot.com', senha: 'Admin@123',
    rotas: ['platform-dashboard', 'estabelecimentos', 'licencas', 'usuarios', 'billing', 'auditoria'],
  },
  {
    id: 'clinica', email: 'admin@clinica-vida.com', senha: 'Admin@123',
    rotas: ['dashboard', 'agenda', 'atendimentos', 'clientes', 'profissionais', 'especialidades',
      'convenios', 'catalogo', 'vocabulario', 'billing', 'billing/config', 'documentos', 'usuarios', 'minha-licenca'],
  },
  {
    id: 'recepcao', email: 'bruno@clinica-vida.com', senha: 'Bruno@123',
    rotas: ['dashboard', 'agenda', 'atendimentos', 'clientes', 'profissionais', 'billing', 'usuarios'],
  },
]

const relatorio = []
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined })

async function visitar(page, perfil, base, rota, eventos) {
  eventos.length = 0
  const url = `${base}/${rota}`
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {})
  await page.waitForTimeout(700)
  const arquivo = `${perfil}-${rota.replace(/\//g, '_') || 'raiz'}.png`
  await page.screenshot({ path: join(SAIDA, arquivo), fullPage: true })
  const texto = (await page.locator('body').innerText()).replace(/\s+/g, ' ').trim()
  relatorio.push({
    perfil, rota, urlFinal: page.url().replace(base, ''), arquivo,
    eventos: [...new Set(eventos)], chars: texto.length, texto: texto.slice(0, 900),
  })
}

function observar(page, eventos) {
  page.on('console', (m) => { if (m.type() === 'error') eventos.push(`console: ${m.text().slice(0, 240)}`) })
  page.on('pageerror', (e) => eventos.push(`pageerror: ${String(e).slice(0, 240)}`))
  page.on('response', (r) => {
    if (r.status() >= 400) eventos.push(`http ${r.status()} ${r.request().method()} ${r.url().replace(/^https?:\/\/[^/]+/, '')}`)
  })
  page.on('requestfailed', (r) => eventos.push(`falhou ${r.method()} ${r.url().replace(/^https?:\/\/[^/]+/, '')}`))
}

try {
  for (const perfil of PERFIS) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'pt-BR' })
    const page = await ctx.newPage()
    const eventos = []
    observar(page, eventos)

    await page.goto(`${ADMIN}/login`, { waitUntil: 'domcontentloaded' })
    await page.fill('input[formControlName="email"]', perfil.email)
    await page.fill('input[formControlName="senha"]', perfil.senha)
    await page.click('button[type="submit"]')
    await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 10000 }).catch(() => {})
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {})
    await page.screenshot({ path: join(SAIDA, `${perfil.id}-00-pos-login.png`), fullPage: true })
    relatorio.push({ perfil: perfil.id, rota: '(pós-login)', urlFinal: page.url().replace(ADMIN, ''), eventos: [...new Set(eventos)] })

    for (const rota of perfil.rotas) await visitar(page, perfil.id, ADMIN, rota, eventos)
    await ctx.close()
  }

  // Portal do paciente (sem login)
  const ctx = await browser.newContext({ viewport: { width: 420, height: 860 }, locale: 'pt-BR' })
  const page = await ctx.newPage()
  const eventos = []
  observar(page, eventos)
  for (const rota of ['auth', 'chat', 'agendamentos']) await visitar(page, 'portal', PORTAL, rota, eventos)
  await ctx.close()
} finally {
  await browser.close()
  writeFileSync(join(SAIDA, 'relatorio.json'), JSON.stringify(relatorio, null, 2))
}

for (const r of relatorio) {
  const desvio = r.rota !== '(pós-login)' && r.urlFinal !== `/${r.rota}` ? `  → redirecionou para ${r.urlFinal}` : ''
  console.log(`\n[${r.perfil}] /${r.rota}${desvio}${r.rota === '(pós-login)' ? ` → ${r.urlFinal}` : ''}`)
  for (const e of r.eventos) console.log(`   ! ${e}`)
}
