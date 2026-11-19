// Motor de gravação: Playwright percorre a aplicação; a narração (mp3 por fala) entra nos
// instantes REAIS medidos durante a gravação; o ffmpeg corta pela marca de sincronismo e monta o MP4.
//
// Uso (ver templates/gravar.mjs):
//   const tl = await gravarVideo({ CENAS, roteiro, out, ...opções })
//   montar(tl, { out, nome })
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { chromium } from 'playwright'
import { spawnSync } from 'node:child_process'
import { FFMPEG, ffmpeg, duracao, arquivoFala, sleep } from './comum.mjs'
import { gerarNarracao } from './tts.mjs'

// ---------- overlay injetado em toda página: legenda, cursor falso, realce, marca, filtro de texto ----------
function overlay({ trocas }) {
  const CSS = `
    #vid-leg { position: fixed; bottom: 38px; left: 50%; transform: translateX(-50%); max-width: 70%; z-index: 2147483646;
      background: rgba(10,30,50,.85); color: #fff; font: 500 24px/1.35 Inter, Arial, sans-serif; padding: 11px 21px;
      border-radius: 10px; text-align: center; pointer-events: none; transition: opacity .25s; width: max-content; }
    #vid-leg:empty { opacity: 0; }
    #vid-cur { position: fixed; left: 0; top: 0; width: 22px; height: 22px; margin: -11px 0 0 -11px; border-radius: 50%;
      background: rgba(255,200,0,.45); border: 2px solid rgba(20,20,20,.75); box-shadow: 0 0 0 2px rgba(255,255,255,.7);
      z-index: 2147483647; pointer-events: none; transition: transform .12s; }
    #vid-cur.down { transform: scale(.7); background: rgba(255,140,0,.7); }
    .vid-realce { outline: 3px solid #12a37a !important; outline-offset: 5px; border-radius: 6px; animation: vidPulso 1.1s ease-in-out infinite; }
    @keyframes vidPulso { 0%,100% { box-shadow: 0 0 0 0 rgba(18,163,122,0); } 50% { box-shadow: 0 0 0 12px rgba(18,163,122,.28); } }
    #vid-marca { position: fixed; inset: 0; background: #ff0000; z-index: 2147483647; }
  `
  // trocas chegam serializadas ({s, f, por}): um RegExp vira {} no JSON e /(?:)/g inflaria o texto em loop até derrubar a página
  const TROCAS = trocas.filter((x) => x.s).map((x) => [new RegExp(x.s, x.f.includes('g') ? x.f : x.f + 'g'), x.por])
  const limpar = (no) => {
    if (!TROCAS.length || !no) return
    const w = document.createTreeWalker(no, NodeFilter.SHOW_TEXT)
    for (let t = w.nextNode(); t; t = w.nextNode()) {
      let v = t.nodeValue
      for (const [re, por] of TROCAS) v = v.replace(re, por)
      if (v !== t.nodeValue) t.nodeValue = v
    }
  }
  const montar = () => {
    if (document.getElementById('vid-leg')) return
    const st = document.createElement('style'); st.textContent = CSS; document.head.append(st)
    const leg = document.createElement('div'); leg.id = 'vid-leg'; document.body.append(leg)
    const cur = document.createElement('div'); cur.id = 'vid-cur'; document.body.append(cur)
    addEventListener('mousemove', (e) => { cur.style.left = e.clientX + 'px'; cur.style.top = e.clientY + 'px' }, true)
    addEventListener('mousedown', () => cur.classList.add('down'), true)
    addEventListener('mouseup', () => cur.classList.remove('down'), true)
    limpar(document.body)
    if (TROCAS.length) new MutationObserver((ms) => {
      for (const m of ms) {
        if (m.type === 'characterData') limpar(m.target.parentNode || m.target)
        else for (const n of m.addedNodes) limpar(n.nodeType === 3 ? n.parentNode : n)
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true })
  }
  window.__vid = {
    legenda(t) { montar(); document.getElementById('vid-leg').textContent = t || '' },
    cursor(x, y) { montar(); const c = document.getElementById('vid-cur'); c.style.left = x + 'px'; c.style.top = y + 'px' },
    legendaPos(p) { // null = rodapé centralizado; ou {left, bottom, maxWidth} em px CSS
      montar()
      const l = document.getElementById('vid-leg')
      l.style.left = p ? p.left + 'px' : ''; l.style.bottom = p ? p.bottom + 'px' : ''; l.style.maxWidth = p ? p.maxWidth + 'px' : ''
    },
    realce(sel, on = true) { for (const e of document.querySelectorAll(sel)) e.classList.toggle('vid-realce', on) },
    marca(on) {
      montar()
      let m = document.getElementById('vid-marca')
      if (on && !m) { m = document.createElement('div'); m.id = 'vid-marca'; document.body.append(m) }
      if (!on && m) m.remove()
    },
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', montar)
  else montar()
}

// ---------- gravação ----------
export async function gravarVideo({
  CENAS, roteiro, out,
  cartazes,                 // caminho do HTML de cartazes (abre como file://…#id)
  preparar,                 // async ({page, ctx}) => login etc., antes do zero
  voz = process.env.VOZ || 'onyx',
  trocas = [],              // [[RegExp, 'texto'], …] aplicados ao texto da página gravada
  proibidas = null,         // RegExp conferida no innerText ao fim de cada cena
  vw = 1536, vh = 864, dsf = 1.25, // 1536×864 × 1,25 = 1920×1080 nítido com a interface 25% maior
  respiro = 0.8, fim = 3,   // s entre cenas / ao final
  locale = 'pt-BR', timezoneId = 'America/Cuiaba',
}) {
  const narrDir = path.join(out, 'narracao')
  const { duracoes } = await gerarNarracao(CENAS, { narrDir, voz })
  const browser = await chromium.launch({
    args: [`--force-device-scale-factor=${dsf}`], // o deviceScaleFactor do contexto NÃO afeta o screencast
    ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
  })
  const dirVideo = path.join(out, 'bruto')
  fs.rmSync(dirVideo, { recursive: true, force: true })
  const ctx = await browser.newContext({
    viewport: { width: vw, height: vh }, deviceScaleFactor: dsf, locale, timezoneId,
    recordVideo: { dir: dirVideo, size: { width: Math.round(vw * dsf), height: Math.round(vh * dsf) } },
  })
  await ctx.addInitScript(overlay, { trocas: trocas.map(([re, por]) => ({ s: re.source, f: re.flags, por })) })
  const page = await ctx.newPage()
  page.on('crash', () => console.log('PÁGINA TRAVOU (crash do renderer): veja a última ação do roteiro'))
  page.on('pageerror', (e) => console.log('erro na página:', String(e.message).split(/\r?\n/)[0]))

  let zero = 0
  const t = () => (zero ? (Date.now() - zero) / 1000 : 0)
  const log = (...a) => console.log(`[${t().toFixed(1).padStart(6)}]`, ...a)
  const timeline = { falas: [], legendas: [], cenas: [], avisos: [], voz }

  // legenda e cursor sobrevivem a navegações
  let legAtual = ''
  const cur = { x: vw / 2, y: vh / 2 }
  const reaplicar = async () => { try { await page.evaluate(([l, x, y]) => { __vid.legenda(l); __vid.cursor(x, y) }, [legAtual, cur.x, cur.y]) } catch {} }
  page.on('domcontentloaded', reaplicar)
  const legenda = async (txt) => { legAtual = txt; try { await page.evaluate((l) => __vid.legenda(l), txt) } catch {} }

  const cena = (id) => { const c = CENAS.find((c) => c.id === id); if (!c) throw new Error(`cena ${id} não existe`); return c }
  // fala k da cena: registra o instante real, troca legendas proporcionalmente ao texto, espera o áudio acabar
  const falar = async (id, k = 0, { segurar = false } = {}) => {
    const c = cena(id), fala = c.falas[k]
    const dur = duracoes[CENAS.indexOf(c)][k]
    const inicio = t()
    timeline.falas.push({ arquivo: path.relative(out, arquivoFala(narrDir, voz, c, k)), inicio, dur })
    log(`fala ${id}-${k} (${dur.toFixed(1)} s)`)
    const total = fala.legendas.reduce((a, l) => a + l.length, 0)
    let acc = 0
    for (const l of fala.legendas) {
      await sleep(Math.max(0, (inicio + (acc / total) * dur - t()) * 1000))
      timeline.legendas.push({ texto: l, inicio: t(), cena: id })
      await legenda(l)
      acc += l.length
    }
    await sleep(Math.max(0, (inicio + dur - t()) * 1000))
    if (!segurar) await legenda('')
  }
  const marcarCena = (id) => { cena(id); timeline.cenas.push({ id, inicio: t() }); log(`— cena ${id}`) }
  const aos = async (inicio, s) => sleep(Math.max(0, (inicio + s - t()) * 1000))
  const mover = async (x, y, ms = 700) => { await page.mouse.move(x, y, { steps: Math.max(8, Math.round(ms / 16)) }); cur.x = x; cur.y = y }
  const caixa = async (sel) => { const b = await page.locator(sel).first().boundingBox(); if (!b) throw new Error(`sem caixa: ${sel}`); return b }
  const centro = async (sel) => { const b = await caixa(sel); return { x: b.x + b.width / 2, y: b.y + b.height / 2 } }
  const sobre = async (sel, ms = 700) => { const c = await centro(sel); await mover(c.x, c.y, ms); return c }
  const clicar = async (sel, ms = 700) => { const c = await sobre(sel, ms); await sleep(180); await page.mouse.click(c.x, c.y); await sleep(150) }
  const rolarPara = async (sel, y = 90, espera = 900) => {
    await page.evaluate(([s, y]) => { const e = document.querySelector(s); window.scrollTo({ top: e.getBoundingClientRect().top + window.scrollY - y, behavior: 'smooth' }) }, [sel, y])
    await sleep(espera)
  }
  const realce = (sel, on = true) => page.evaluate(([s, on]) => __vid.realce(s, on), [sel, on]).catch(() => {})
  const legendaPos = (p) => page.evaluate((p) => __vid.legendaPos(p), p).catch(() => {})
  const cartaz = async (id) => {
    const url = `${pathToFileURL(cartazes).href}#${id}`
    if (page.url().startsWith(pathToFileURL(cartazes).href)) await page.evaluate((h) => { location.hash = h }, `#${id}`)
    else { await page.goto(url); await page.evaluate(() => document.fonts.ready) }
    await mover(vw - 30, vh - 30, 200)
    await sleep(300)
  }
  const conferirTela = async (id) => {
    if (!proibidas) return
    const txt = await page.evaluate(() => document.body.innerText).catch(() => '')
    const m = proibidas.exec(txt)
    if (m) { timeline.avisos.push(`cena ${id}: palavra proibida na tela: "${m[0]}"`); log('ATENÇÃO palavra proibida na tela:', m[0]) }
  }
  const pausa = (s = respiro) => sleep(s * 1000)

  const video = page.video()
  try {
    if (preparar) await preparar({ page, ctx })

    // marca de sincronismo: tela vermelha sobre a 1ª tela; o instante em que some é o zero
    await page.evaluate(() => __vid.marca(true)).catch(async () => { await page.goto('about:blank'); await page.evaluate(() => __vid.marca(true)) })
    await mover(vw - 40, vh - 40, 50)
    await sleep(1500)
    await page.evaluate(() => __vid.marca(false))
    zero = Date.now()

    await roteiro({ page, t, log, falar, marcarCena, aos, mover, caixa, centro, sobre, clicar, rolarPara, realce, legenda, legendaPos, cartaz, conferirTela, pausa, sleep, vw, vh })

    await sleep(fim * 1000)
    timeline.total = t()
    log('fim')
  } catch (e) {
    log('ERRO na gravação:', e.message)
    throw e
  } finally {
    await ctx.close().catch(() => {}) // fecha sempre: sem isto o processo fica pendurado após um erro
    await browser.close().catch(() => {})
  }
  timeline.bruto = path.relative(out, await video.path())
  fs.mkdirSync(out, { recursive: true })
  fs.writeFileSync(path.join(out, 'timeline.json'), JSON.stringify(timeline, null, 2))
  for (const a of timeline.avisos) console.log('AVISO:', a)
  return timeline
}

// ---------- montagem ----------
// instante (s) do webm bruto em que a marca vermelha some (= zero da linha do tempo). Varia a cada gravação: sempre medir.
export function offsetDaMarca(bruto) {
  const fps = 50
  const r = spawnSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-t', '30', '-i', bruto, '-vf', `fps=${fps},crop=64:64:16:16,scale=1:1`, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 1 << 26 })
  const b = r.stdout
  let viuVermelho = false
  for (let i = 0; i + 2 < b.length; i += 3) {
    const vermelho = b[i] > 200 && b[i + 1] < 60 && b[i + 2] < 60
    if (vermelho) viuVermelho = true
    else if (viuVermelho) return i / 3 / fps
  }
  throw new Error('marca vermelha não encontrada no vídeo bruto')
}

export function montar(timeline, { out, nome = 'video', crf = 20 }) {
  const bruto = path.join(out, timeline.bruto)
  const off = offsetDaMarca(bruto)
  const total = timeline.total
  console.log(`offset da marca: ${off.toFixed(3)} s · duração final: ${total.toFixed(1)} s`)

  // cada mp3 no seu instante real (adelay) e mixados sem normalizar (normalize=0 evita queda de volume)
  const entradas = timeline.falas.flatMap((f) => ['-i', path.join(out, f.arquivo)])
  const filtros = timeline.falas.map((f, i) => `[${i}:a]adelay=${Math.round(f.inicio * 1000)}:all=1[a${i}]`)
  const mix = `${timeline.falas.map((_, i) => `[a${i}]`).join('')}amix=inputs=${timeline.falas.length}:normalize=0:dropout_transition=0,apad,atrim=0:${total.toFixed(3)}[out]`
  const narr = path.join(out, 'narracao.m4a')
  ffmpeg(['-y', ...entradas, '-filter_complex', [...filtros, mix].join(';'), '-map', '[out]', '-c:a', 'aac', '-b:a', '160k', narr])

  const mp4 = path.join(out, `${nome}.mp4`)
  ffmpeg(['-y', '-ss', off.toFixed(3), '-i', bruto, '-i', narr, '-t', total.toFixed(3),
    '-map', '0:v', '-map', '1:a', '-r', '30', '-c:v', 'libx264', '-preset', 'slow', '-crf', String(crf), '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-shortest', mp4])

  // quadros de conferência: 1 por cena (2 s após o início) e 1 por legenda (1,2 s após entrar)
  const frames = path.join(out, 'frames')
  fs.rmSync(frames, { recursive: true, force: true })
  fs.mkdirSync(frames, { recursive: true })
  for (const c of timeline.cenas) ffmpeg(['-y', '-ss', (c.inicio + 2).toFixed(2), '-i', mp4, '-frames:v', '1', path.join(frames, `${c.id}.png`)])
  timeline.legendas.forEach((l, i) => ffmpeg(['-y', '-ss', (l.inicio + 1.2).toFixed(2), '-i', mp4, '-frames:v', '1', path.join(frames, `leg-${String(i + 1).padStart(2, '0')}-c${l.cena}.png`)]))
  console.log('MP4:', mp4, `(${duracao(mp4).toFixed(1)} s)`)
  return { mp4, off, frames }
}
