// Gravação do vídeo explicativo do MedBot (skill gravando-video-explicativo).
// Textos em roteiro.mjs, cartazes em cartazes.html; gravador.mjs/tts.mjs/comum.mjs são o motor.
//
//   node gravar.mjs            → narração (TTS, com cache) + gravação + montagem
//   node gravar.mjs montar     → só remonta o MP4 a partir de out/timeline.json
//   TTS_FAKE=1 node gravar.mjs → pipeline completa com narração muda (teste sem custo)
//   SEM_CHAT=1 node gravar.mjs → pula a cena do chat (quando os modelos de IA não estão disponíveis)
//
// Pré-requisitos: backend (8100), admin (4201) e portal (4200) no ar, banco com o seed.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { CENAS as TODAS, PROIBIDAS, TROCAS } from './roteiro.mjs'
import { gravarVideo, montar } from './gravador.mjs'

const DIR = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.join(DIR, 'out')
const NOME = 'medbot-apresentacao'
const API = process.env.API || 'http://localhost:8100/v1'
const ADMIN = process.env.ADMIN || 'http://localhost:4201'
const PORTAL = process.env.PORTAL || 'http://localhost:4200'
const LOGIN = { email: 'admin@medbot.com', senha: 'Admin@123' }
const CLINICA = 'Clínica Vida Saúde'
const SEM_CHAT = process.env.SEM_CHAT === '1'
const CENAS = SEM_CHAT ? TODAS.filter((c) => c.id !== '02') : TODAS

// ---------- apoio via API (fora da tela) ----------
async function api(caminho, { token, metodo = 'GET', corpo } = {}) {
  const r = await fetch(API + caminho, {
    method: metodo,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: corpo ? JSON.stringify(corpo) : undefined,
  })
  if (!r.ok) throw new Error(`${metodo} ${caminho}: HTTP ${r.status}`)
  return r.json()
}

async function tokenDaClinica() {
  const { access_token: global } = await api('/auth/login', { metodo: 'POST', corpo: LOGIN })
  const ests = await api('/estabelecimentos/', { token: global })
  const lista = Array.isArray(ests) ? ests : ests.items ?? ests.estabelecimentos ?? []
  const clinica = lista.find((e) => e.nome === CLINICA)
  if (!clinica) throw new Error(`estabelecimento "${CLINICA}" não encontrado — rode o seed`)
  const { access_token } = await api('/admin/selecionar-estabelecimento', {
    token: global, metodo: 'POST', corpo: { estabelecimento_id: clinica.id },
  })
  return access_token
}

// termos padrão antes e depois da gravação (a cena 09 troca o vocabulário ao vivo)
async function restaurarVocabulario() {
  const token = await tokenDaClinica() // também gera um evento de auditoria (acesso à clínica)
  await api('/estabelecimentos/meu/vocabulario', {
    token, metodo: 'PATCH',
    corpo: { label_profissional: 'Médico', label_atendimento: 'Consulta', label_cliente: 'Paciente', label_especialidade: 'Especialidade' },
  })
}

// ---------- o percurso pela aplicação (uma seção por cena) ----------
async function roteiro(h) {
  const { page, t, falar, marcarCena, aos, sobre, clicar, realce, cartaz, conferirTela, pausa, sleep } = h

  const assentar = async (ms = 900) => { await page.waitForLoadState('networkidle', { timeout: 6000 }).catch(() => {}); await sleep(ms) }
  const menu = async (rota) => { await clicar(`a.sidebar__nav-item[href="/${rota}"]`, 600); await assentar() }
  const digitar = async (sel, texto, atraso = 30) => { await clicar(sel, 500); await page.keyboard.type(texto, { delay: atraso }) }
  const substituir = async (sel, texto) => { await clicar(sel, 500); await page.keyboard.press('Control+A'); await page.keyboard.type(texto, { delay: 70 }) }
  const destacar = async (sel, ms) => { await realce(sel); await sleep(ms); await realce(sel, false) }
  // a área rolável do admin é o conteúdo do sidenav, não a janela: rola o próprio elemento
  const rolar = async (sel, bloco = 'start', ms = 900) => {
    await page.locator(sel).first().evaluate((e, bloco) => e.scrollIntoView({ behavior: 'smooth', block: bloco }), bloco)
    await sleep(ms)
  }
  const respostasDoBot = (n) => page.waitForFunction(
    (n) => document.querySelectorAll('.message.assistant:not(.typing)').length >= n, n, { timeout: 120000 })
  const enviarNoChat = async (texto, respostas) => {
    await digitar('.chat-input input', texto)
    await page.keyboard.press('Enter')
    await respostasDoBot(respostas)
    await sleep(700)
  }

  // 01 — abertura (cartaz)
  await cartaz('c1')
  marcarCena('01')
  await falar('01')
  await pausa()

  // 02 — o paciente agenda pelo chat (IA de verdade: a 2ª fala espera os horários aparecerem)
  if (!SEM_CHAT) {
    await page.goto(`${PORTAL}/chat`)
    await page.waitForSelector('.status.online', { timeout: 20000 })
    await assentar(600)
    // a conversa ocupa a coluna central e o campo de digitação fica no rodapé: legenda na lateral esquerda
    const legendaAoLado = () => h.legendaPos({ left: 224, bottom: 330, maxWidth: 390 })
    await legendaAoLado()
    marcarCena('02')
    {
      // fala 0 — nome, convênio, sintomas. A IA decide quantas perguntas faz antes de indicar a especialidade.
      const voz = falar('02', 0, { segurar: true })
      await enviarNoChat('Olá, quero marcar uma consulta', 1)
      await enviarNoChat('Pedro Henrique Oliveira', 2)
      // convênio e plano pelos botões que a unidade cadastrou
      await sleep(500)
      await clicar('.chip-convenio:has-text("Unimed")', 700)
      await respostasDoBot(3)
      await sleep(700)
      await clicar('.chip-reply', 700)
      await respostasDoBot(4)
      await sleep(500)
      const sintomas = [
        'Estou com dor no joelho ao subir escadas, faz duas semanas',
        'É uma dor nova, sem queda nem pancada. Incha um pouco no fim do dia.',
        'Não tenho febre nem outros sintomas. Qual especialista devo procurar?',
        'Pode indicar a especialidade e os horários, por favor.',
      ]
      const temHorarios = async () => (await page.locator('.slot-card').count()) > 0
      for (const fala of sintomas) {
        const n = await page.locator('.message.assistant:not(.typing)').count()
        await enviarNoChat(fala, n + 1)
        if (await temHorarios()) break
      }
      if (!(await temHorarios())) throw new Error('cena 02: a IA não chegou a mostrar horários')
      await voz

      // fala 1 — especialidade indicada e horários livres
      const voz1 = falar('02', 1, { segurar: true })
      await page.locator('.slot-card').last().scrollIntoViewIfNeeded()
      await sleep(500)
      await realce('.slots-sugeridos')
      await sobre('.slot-card', 1200)
      await voz1
      await realce('.slots-sugeridos', false)

      // fala 2 — escolhe o horário, informa contato e confirma
      const voz2 = falar('02', 2, { segurar: true })
      let n = await page.locator('.message.assistant:not(.typing)').count()
      await clicar('.slot-card', 400)
      await respostasDoBot(n + 1)
      await sleep(900)
      await enviarNoChat('529.982.247-25', n + 2) // CPF de exemplo (dígitos verificadores válidos)
      await enviarNoChat('01234567890123', n + 3) // carteirinha do convênio
      await enviarNoChat('(11) 98765-4321', n + 4)
      await enviarNoChat('pedro.oliveira@exemplo.com.br', n + 5)
      await sleep(1200) // tempo de ler o resumo antes de confirmar
      await enviarNoChat('Sim', n + 6)
      await voz2
      await sleep(1500)
      await conferirTela('02')

      // fala 3 — nova conversa: emergência não agenda, orienta o SAMU
      await page.goto(`${PORTAL}/chat`)
      await page.waitForSelector('.status.online', { timeout: 20000 })
      await legendaAoLado()
      await assentar(400)
      const voz3 = falar('02', 3)
      await digitar('.chat-input input', 'Estou com uma dor muito forte no peito e falta de ar')
      await page.keyboard.press('Enter')
      await page.waitForSelector('.banner-emergencia', { timeout: 30000 })
      await voz3
      await sleep(600)
    }
    await h.legendaPos(null)
    await pausa()
  }

  // 03 — painel da plataforma: login, visão geral, estabelecimentos e licenças
  await page.goto(`${ADMIN}/login`)
  await page.waitForSelector('input[formControlName="email"]')
  await assentar(500)
  marcarCena('03')
  {
    const i0 = t()
    const voz = falar('03')
    await digitar('input[formControlName="email"]', LOGIN.email, 28)
    await digitar('input[formControlName="senha"]', LOGIN.senha, 28)
    await clicar('button[type="submit"]', 400)
    await page.waitForURL(/selecionar-estabelecimento|dashboard/, { timeout: 15000 })
    await assentar(700)
    if (page.url().includes('selecionar-estabelecimento')) {
      await clicar('.superadmin-bar button', 700)
      await page.waitForURL(/dashboard/, { timeout: 15000 })
      await assentar(600)
    }
    await menu('platform-dashboard')
    await aos(i0, 6.2)
    await menu('estabelecimentos')
    await destacar('table', 1100)
    await aos(i0, 8.5)
    await menu('licencas')
    await realce('table')
    await voz
    await realce('table', false)
  }
  await conferirTela('03')
  await pausa()

  // 04 — controle: usuários, custo da IA e auditoria
  marcarCena('04')
  {
    const i0 = t()
    const voz = falar('04')
    await menu('usuarios')
    await aos(i0, 2.5)
    await menu('billing')
    await aos(i0, 7.6)
    await menu('auditoria')
    await realce('table')
    await voz
    await realce('table', false)
  }
  await conferirTela('04')
  await pausa()

  // 05 — entrar em uma clínica: dia a dia e agenda
  marcarCena('05')
  {
    const i0 = t()
    const voz = falar('05')
    await clicar('.sidebar button', 600) // "Entrar como clínica"
    await page.waitForURL(/selecionar-estabelecimento/, { timeout: 15000 })
    await assentar(500)
    const cartao = page.locator('.est-card', { hasText: CLINICA }).locator('.btn-acessar')
    const b = await cartao.boundingBox()
    await h.mover(b.x + b.width / 2, b.y + b.height / 2, 800)
    await sleep(250)
    await cartao.click()
    await page.waitForURL(/dashboard/, { timeout: 15000 })
    await assentar(700)
    await destacar('.kpi-grid', 2000)
    await aos(i0, 7.7)
    await menu('agenda')
    await sobre('.filtro-especialidade', 900)
    await voz
  }
  await conferirTela('05')
  await pausa()

  // 06 — convênios e planos
  await menu('convenios')
  await rolar('mat-expansion-panel', 'start', 700) // lista de operadoras no topo, formulário fora do quadro
  marcarCena('06')
  {
    const i0 = t()
    const voz = falar('06')
    await aos(i0, 1.2)
    await clicar('mat-expansion-panel-header:has-text("Unimed")', 800)
    await sleep(600)
    await rolar('mat-expansion-panel-header:has-text("Unimed")', 'center')
    await voz
  }
  await conferirTela('06')
  await pausa()

  // 07 — catálogo de serviços
  await menu('catalogo')
  marcarCena('07')
  {
    const voz = falar('07')
    await rolar('table', 'start')
    await realce('table')
    await voz
    await realce('table', false)
  }
  await conferirTela('07')
  await pausa()

  // 08 — cadastros por unidade
  marcarCena('08')
  {
    const i0 = t()
    const voz = falar('08')
    await menu('clientes')
    await aos(i0, 2.2)
    await menu('profissionais')
    await aos(i0, 4.2)
    await menu('atendimentos')
    await aos(i0, 8.0)
    await menu('clientes')
    await realce('.mat-column-cpf')
    await voz
    await realce('.mat-column-cpf', false)
  }
  await conferirTela('08')
  await pausa()

  // 09 — vocabulário: troca ao vivo e o menu acompanha
  await menu('vocabulario')
  await page.waitForSelector('input[formControlName="label_profissional"]')
  marcarCena('09')
  {
    const i0 = t()
    const voz = falar('09')
    await aos(i0, 2.3)
    await substituir('input[formControlName="label_profissional"]', 'Esteticista')
    await substituir('input[formControlName="label_atendimento"]', 'Sessão')
    await clicar('form button[type="submit"]', 500)
    await sleep(600)
    await realce('.sidebar__nav')
    await aos(i0, 9.0)
    await realce('.sidebar__nav', false)
    await menu('profissionais')
    await voz
  }
  await conferirTela('09')
  await pausa()

  // 10 — encerramento (cartaz)
  await cartaz('c2')
  marcarCena('10')
  await falar('10', 0, { segurar: true })
}

// ---------- principal ----------
fs.mkdirSync(OUT, { recursive: true })
if ((process.argv[2] || 'tudo') === 'montar') {
  montar(JSON.parse(fs.readFileSync(path.join(OUT, 'timeline.json'), 'utf8')), { out: OUT, nome: NOME })
} else {
  await restaurarVocabulario()
  try {
    const tl = await gravarVideo({
      CENAS, roteiro, out: OUT,
      cartazes: path.join(DIR, 'cartazes.html'),
      trocas: TROCAS, proibidas: PROIBIDAS,
      timezoneId: 'America/Sao_Paulo',
    })
    montar(tl, { out: OUT, nome: NOME })
  } finally {
    await restaurarVocabulario().catch((e) => console.log('AVISO: vocabulário não restaurado:', e.message))
  }
}
