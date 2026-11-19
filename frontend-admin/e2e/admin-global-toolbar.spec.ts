import { test, expect, type Page } from '@playwright/test'

const ADMIN_EMAIL = 'admin@medbot.com'
const ADMIN_SENHA = 'Admin@123'
const BASE = 'http://localhost:4201'

async function loginAdmin(page: Page) {
  await page.goto(BASE + '/login')
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.reload()
  await page.waitForLoadState('networkidle')

  await page.getByLabel(/e-?mail/i).fill(ADMIN_EMAIL)
  await page.locator('input[type="password"]').fill(ADMIN_SENHA)
  await page.getByRole('button', { name: /entrar/i }).click()
  await page.waitForURL(/\/(dashboard|selecionar-estabelecimento)/, { timeout: 15_000 })
}

async function clicarModoGlobal(page: Page) {
  /** Clica em "Modo Global" na tela de seleção de estabelecimento. */
  const btn = page.getByRole('button', { name: /modo global/i })
  await btn.waitFor({ state: 'visible', timeout: 5_000 })
  await btn.click()
  await page.waitForURL('**/dashboard', { timeout: 10_000 })
  await page.waitForLoadState('networkidle')
}

test.describe('ADMIN_GLOBAL — toolbar e seletor de estabelecimento', () => {

  test('T1 — login ADMIN_GLOBAL vai para tela de seleção', async ({ page }) => {
    await loginAdmin(page)
    await page.screenshot({ path: 'e2e/screenshots/01-pos-login.png', fullPage: true })
    console.log('URL após login:', page.url())
    // Deve ir para seleção ou direto ao dashboard (se sessão persistida)
    expect(page.url()).toMatch(/\/(dashboard|selecionar-estabelecimento)/)
  })

  test('T2 — toolbar tem seletor de estabelecimento em modo global', async ({ page }) => {
    await loginAdmin(page)

    if (page.url().includes('selecionar-estabelecimento')) {
      await clicarModoGlobal(page)
    }

    await page.screenshot({ path: 'e2e/screenshots/02-dashboard-global.png', fullPage: true })

    // Inspecionar JWT
    const token = await page.evaluate(() => localStorage.getItem('admin_token'))
    if (token) {
      const p = JSON.parse(atob(token.split('.')[1]))
      console.log('\n=== JWT (modo global esperado) ===')
      console.log('role:', p.role)
      console.log('estabelecimento_id:', p.estabelecimento_id ?? 'AUSENTE (correto)')
    }

    // Inspecionar toolbar
    const toolbar = page.locator('mat-toolbar')
    await toolbar.waitFor({ state: 'visible', timeout: 5_000 })
    const toolbarHtml = await toolbar.innerHTML()
    console.log('\n=== TOOLBAR HTML ===\n', toolbarHtml)

    // O seletor DEVE estar visível
    const matSelect = toolbar.locator('mat-select')
    const visible = await matSelect.isVisible().catch(() => false)
    console.log('mat-select visível no toolbar:', visible)

    // Empty state na página
    const emptyState = page.locator('app-empty-state')
    const emptyVisible = await emptyState.isVisible().catch(() => false)
    console.log('Empty state visível na página:', emptyVisible)

    await expect(matSelect).toBeVisible({ timeout: 5_000 })
  })

  test('T3 — selecionar clínica no toolbar carrega dados', async ({ page }) => {
    await loginAdmin(page)
    if (page.url().includes('selecionar-estabelecimento')) {
      await clicarModoGlobal(page)
    }

    const toolbar = page.locator('mat-toolbar')
    await toolbar.waitFor({ state: 'visible', timeout: 5_000 })

    // Abrir o mat-select do toolbar
    const matSelect = toolbar.locator('mat-select')
    await expect(matSelect).toBeVisible({ timeout: 5_000 })
    await matSelect.click()
    await page.waitForTimeout(500)

    await page.screenshot({ path: 'e2e/screenshots/03-dropdown-aberto.png', fullPage: true })

    // Verificar opções disponíveis
    const options = page.locator('mat-option')
    const count = await options.count()
    console.log('Opções no dropdown:', count)
    for (let i = 0; i < count; i++) {
      const txt = await options.nth(i).textContent()
      console.log(`  Opção ${i}:`, txt?.trim())
    }

    // Selecionar primeira opção real (não "Todas as clínicas")
    const primeiraClinica = options.filter({ hasNotText: /todas as clínicas/i }).first()
    if (await primeiraClinica.isVisible()) {
      const nomeSelecionado = await primeiraClinica.textContent()
      console.log('Selecionando:', nomeSelecionado?.trim())
      await primeiraClinica.click()
      await page.waitForTimeout(2_000)
      await page.waitForLoadState('networkidle')
    }

    await page.screenshot({ path: 'e2e/screenshots/04-clinica-selecionada.png', fullPage: true })

    // Empty state deve sumir
    const emptyState = page.locator('app-empty-state')
    const emptyDesapareceu = await emptyState.isHidden().catch(() => true)
    console.log('Empty state sumiu após seleção:', emptyDesapareceu)
  })

  test('T4 — fluxo: login → selecionar clínica na tela de seleção → swap → volta global', async ({ page }) => {
    await loginAdmin(page)

    // Deve ir para selecionar-estabelecimento
    expect(page.url()).toContain('selecionar-estabelecimento')
    await page.waitForLoadState('networkidle')
    await page.screenshot({ path: 'e2e/screenshots/05-selecionar-est.png', fullPage: true })

    // Inspecionar botões disponíveis
    const botoesAcessar = page.getByRole('button', { name: /acessar/i })
    const countAcessar = await botoesAcessar.count()
    console.log('Botões "Acessar" (clínicas ativas):', countAcessar)

    if (countAcessar > 0) {
      // Selecionar primeira clínica
      await botoesAcessar.first().click()
      await page.waitForURL('**/dashboard', { timeout: 10_000 })
      await page.waitForLoadState('networkidle')
    } else {
      // Fallback: ir via Modo Global
      await clicarModoGlobal(page)
    }

    await page.screenshot({ path: 'e2e/screenshots/06-modo-escopado-ou-global.png', fullPage: true })

    // Verificar JWT atual
    const tokenInicial = await page.evaluate(() => localStorage.getItem('admin_token'))
    if (tokenInicial) {
      const p = JSON.parse(atob(tokenInicial.split('.')[1]))
      console.log('\n=== JWT INICIAL (escopado?) ===')
      console.log('estabelecimento_id:', p.estabelecimento_id ?? 'AUSENTE')
    }

    // Verificar toolbar
    const toolbar = page.locator('mat-toolbar')
    const toolbarHtml1 = await toolbar.innerHTML()
    console.log('\n=== TOOLBAR INICIAL ===\n', toolbarHtml1.substring(0, 400))

    // Se em modo escopado, clicar no botão de swap
    const swapBtn = toolbar.locator('button.main__toolbar-est')
    const swapVisible = await swapBtn.isVisible({ timeout: 2_000 }).catch(() => false)
    console.log('Botão swap (modo escopado) visível:', swapVisible)

    if (swapVisible) {
      const btnText = await swapBtn.textContent()
      console.log('Texto do botão swap:', btnText?.trim())
      await swapBtn.click()
      await page.waitForTimeout(3_000) // API call + signal update
      await page.waitForLoadState('networkidle')
    }

    await page.screenshot({ path: 'e2e/screenshots/07-apos-swap.png', fullPage: true })

    // Verificar JWT após swap
    const tokenFinal = await page.evaluate(() => localStorage.getItem('admin_token'))
    if (tokenFinal) {
      const p = JSON.parse(atob(tokenFinal.split('.')[1]))
      console.log('\n=== JWT APÓS SWAP ===')
      console.log('estabelecimento_id:', p.estabelecimento_id ?? 'AUSENTE (correto para global)')
    }

    // Verificar toolbar final
    const toolbarHtml2 = await toolbar.innerHTML()
    console.log('\n=== TOOLBAR APÓS SWAP ===\n', toolbarHtml2.substring(0, 400))

    // Verificar estado da página
    const emptyState = page.locator('app-empty-state')
    const emptyVisible = await emptyState.isVisible().catch(() => false)
    console.log('Empty state visível:', emptyVisible)

    const matSelect = toolbar.locator('mat-select')
    const seletorVoltou = await matSelect.isVisible({ timeout: 5_000 }).catch(() => false)
    console.log('Seletor voltou ao toolbar:', seletorVoltou)

    // ASSERTIVA PRINCIPAL: seletor deve estar no toolbar após swap para global
    await expect(matSelect).toBeVisible({ timeout: 5_000 })
  })
})

test('T5 — selecionar "Todas as clínicas" exibe empty state e limpa dados', async ({ page }) => {
  await loginAdmin(page)
  if (page.url().includes('selecionar-estabelecimento')) {
    await clicarModoGlobal(page)
  }

  const toolbar = page.locator('mat-toolbar')
  await toolbar.waitFor({ state: 'visible', timeout: 5_000 })

  // Passo 1: selecionar uma clínica para ter dados na tela
  const matSelect = toolbar.locator('mat-select')
  await matSelect.click()
  await page.waitForTimeout(300)

  const clinica = page.locator('mat-option').filter({ hasNotText: /todas as clínicas/i }).first()
  await clinica.click()
  await page.waitForTimeout(2_000)
  await page.waitForLoadState('networkidle')

  // Confirmar que o empty state sumiu (dados carregaram)
  const emptyState = page.locator('app-empty-state')
  const emptyAntes = await emptyState.isVisible().catch(() => false)
  console.log('Empty state visível ANTES de voltar para "Todas as clínicas":', emptyAntes)
  await page.screenshot({ path: 'e2e/screenshots/t5-01-com-clinica.png', fullPage: true })

  // Passo 2: selecionar "Todas as clínicas" (null)
  await matSelect.click()
  await page.waitForTimeout(300)

  const opcaoTodas = page.locator('mat-option').filter({ hasText: /todas as clínicas/i })
  await opcaoTodas.click()
  await page.waitForTimeout(1_500)

  await page.screenshot({ path: 'e2e/screenshots/t5-02-todas-clinicas.png', fullPage: true })

  // Verificar estado do sinal no serviço via localStorage/sessionStorage
  const filtroStorage = await page.evaluate(() => sessionStorage.getItem('admin_filtro_est_id'))
  console.log('Filtro no sessionStorage após "Todas as clínicas":', filtroStorage, '(esperado: null/vazio)')

  // Verificar o que está na página
  const emptyDepois = await emptyState.isVisible({ timeout: 3_000 }).catch(() => false)
  console.log('Empty state visível DEPOIS de "Todas as clínicas":', emptyDepois, '(esperado: true)')

  const pageText = await page.locator('app-dashboard, .dashboard-content, main').first().textContent().catch(() => '')
  console.log('Conteúdo da página:', pageText?.substring(0, 200))

  // ASSERTIVA: empty state deve aparecer
  await expect(emptyState).toBeVisible({ timeout: 5_000 })
})

test('T6 — após swap escopado→global, clicar "Todas as clínicas" deve manter/exibir empty state', async ({ page }) => {
  // Cenário: scoped JWT → swap → dropdown desincronizado (ctrl=2, filtro=null) → clica "Todas as clínicas"
  await loginAdmin(page)

  // Ir para seleção e clicar em "Acessar" (obtém JWT escopado)
  if (!page.url().includes('selecionar-estabelecimento')) {
    await page.goto(`${BASE}/selecionar-estabelecimento`)
    await page.waitForLoadState('networkidle')
  }

  const btnAcessar = page.getByRole('button', { name: /acessar/i }).first()
  await btnAcessar.waitFor({ state: 'visible', timeout: 5_000 })
  await btnAcessar.click()
  await page.waitForURL('**/dashboard', { timeout: 10_000 })
  await page.waitForLoadState('networkidle')

  // Agora em modo escopado — clicar no swap button do toolbar
  const swapBtn = page.locator('mat-toolbar button.main__toolbar-est')
  await swapBtn.waitFor({ state: 'visible', timeout: 5_000 })
  await swapBtn.click()
  await page.waitForTimeout(2_000)

  // Verificar estado imediatamente após swap
  const matSelect = page.locator('mat-toolbar mat-select')
  await matSelect.waitFor({ state: 'visible', timeout: 5_000 })

  const selectValue = await page.evaluate(() => {
    // Pegar o texto visível no mat-select
    const el = document.querySelector('mat-toolbar mat-select .mat-mdc-select-value-text')
    return el?.textContent ?? null
  })
  const selectPlaceholder = await page.evaluate(() => {
    const el = document.querySelector('mat-toolbar mat-select .mat-mdc-select-placeholder')
    return el?.textContent ?? null
  })
  console.log('Select value após swap:', selectValue)
  console.log('Select placeholder após swap:', selectPlaceholder)
  console.log('(se value for o nome de uma clínica, filtroEstCtrl está desincronizado)')

  await page.screenshot({ path: 'e2e/screenshots/t6-01-apos-swap.png', fullPage: true })

  // Tentar clicar em "Todas as clínicas"
  await matSelect.click()
  await page.waitForTimeout(300)

  const opcaoTodas = page.locator('mat-option').filter({ hasText: /todas as clínicas/i })
  const opcaoTodasVisible = await opcaoTodas.isVisible({ timeout: 2_000 }).catch(() => false)
  console.log('"Todas as clínicas" opção visível:', opcaoTodasVisible)

  if (opcaoTodasVisible) {
    await opcaoTodas.click()
    await page.waitForTimeout(1_500)
  } else {
    await page.keyboard.press('Escape')
  }

  await page.screenshot({ path: 'e2e/screenshots/t6-02-apos-todas-clinicas.png', fullPage: true })

  // O empty state deve estar visível (seja já estava antes, ou apareceu agora)
  const emptyState = page.locator('app-empty-state')
  await expect(emptyState).toBeVisible({ timeout: 5_000 })

  // O select deve mostrar placeholder (vazio), não nome de clínica
  const selectValueFinal = await page.evaluate(() => {
    const el = document.querySelector('mat-toolbar mat-select .mat-mdc-select-value-text')
    return el?.textContent ?? null
  })
  console.log('Select value final (esperado null/""):', selectValueFinal)
  expect(selectValueFinal).toBeNull() // placeholder, não um valor selecionado
})
