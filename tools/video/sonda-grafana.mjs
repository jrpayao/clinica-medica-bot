// Sonda do painel do Grafana: entra, abre "MedBot — visão geral" e lista os painéis sem dados.
//   node sonda-grafana.mjs [pasta-de-prints]   (lê a senha de infra/observabilidade/.env)
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const OUT = process.argv[2] || 'out/sonda'
const GRAFANA = process.env.GRAFANA || 'http://localhost:3000'
const env = fs.readFileSync(new URL('../../infra/observabilidade/.env', import.meta.url), 'utf8')
const senha = env.match(/^GRAFANA_SENHA_ADMIN=(.*)$/m)[1].trim()
fs.mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
try {
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 2600 } })).newPage()
  await page.goto(`${GRAFANA}/login`)
  await page.fill('input[name="user"]', 'admin')
  await page.fill('input[name="password"]', senha)
  await page.click('button[type="submit"]')
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 20000 })
  await page.goto(`${GRAFANA}/d/medbot-visao-geral?orgId=1&from=now-1h&to=now&kiosk`)
  await page.waitForSelector('[data-testid="data-testid panel content"], .panel-content', { timeout: 30000 }).catch(() => {})
  await page.waitForTimeout(8000)
  // estado de cada painel pela própria API do Grafana: roda a consulta de cada um na última hora
  const painel = await (await page.request.get(`${GRAFANA}/api/dashboards/uid/medbot-visao-geral`)).json()
  for (const p of painel.dashboard.panels.filter((x) => x.type !== 'row')) {
    const resposta = await page.request.post(`${GRAFANA}/api/ds/query`, {
      data: { from: 'now-1h', to: 'now', queries: p.targets.map((t) => ({ ...t, intervalMs: 15000, maxDataPoints: 240 })) },
    })
    const corpo = await resposta.json()
    const resultados = Object.values(corpo.results ?? {})
    const erro = resultados.map((r) => r.error).find(Boolean)
    const linhas = resultados.flatMap((r) => r.frames ?? []).reduce((n, f) => n + (f.data?.values?.[0]?.length ?? 0), 0)
    console.log(`${erro ? 'ERRO ' : linhas ? 'dados' : 'vazio'} ${p.title}${erro ? ' -> ' + erro.slice(0, 140) : ''}`)
  }
  await page.screenshot({ path: path.join(OUT, 'grafana.png') })
} catch (e) {
  console.log('FALHOU:', e.message.split('\n')[0])
} finally {
  await browser.close()
}
