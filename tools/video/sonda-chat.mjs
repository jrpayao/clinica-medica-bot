// Sonda do agendamento pelo chat, de ponta a ponta, sem gravar: imprime cada resposta do assistente.
//   node sonda-chat.mjs [pasta-de-prints]
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const PORTAL = process.env.PORTAL || 'http://localhost:4200'
const OUT = process.argv[2] || 'out/sonda'
fs.mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1536, height: 864 } })
page.on('console', (m) => { if (m.type() === 'error') console.log('console.error:', m.text().slice(0, 200)) })
const t0 = Date.now()
const seg = () => ((Date.now() - t0) / 1000).toFixed(1).padStart(6)
const respostas = () => page.locator('.message.assistant:not(.typing)')
const ultima = async () => (await respostas().last().innerText()).replace(/\s+/g, ' ').slice(0, 420)
const aguardarNova = async (antes, ms = 180000) => {
  await page.waitForFunction(
    (n) => document.querySelectorAll('.message.assistant:not(.typing)').length > n, antes, { timeout: ms })
  await page.waitForTimeout(500)
}
const enviar = async (texto) => {
  const antes = await respostas().count()
  await page.fill('.chat-input input', texto)
  await page.keyboard.press('Enter')
  await aguardarNova(antes)
  console.log(`[${seg()}s] > ${texto}\n          < ${await ultima()}`)
}
const tocar = async (seletor, rotulo) => {
  const antes = await respostas().count()
  await page.locator(seletor, { hasText: rotulo }).first().click()
  await aguardarNova(antes)
  console.log(`[${seg()}s] [botão ${rotulo}]\n          < ${await ultima()}`)
}

try {
  await page.goto(`${PORTAL}/chat`)
  await page.waitForSelector('.status.online', { timeout: 20000 })
  await enviar('Olá, quero marcar uma consulta')
  await enviar('Pedro Henrique Oliveira')
  console.log('botões de convênio:', await page.locator('.chip-convenio').allInnerTexts())
  await page.screenshot({ path: path.join(OUT, '1-convenios.png') })
  await enviar('Cassi') // não aceito: deve listar os aceitos e manter os botões
  console.log('botões após convênio não aceito:', await page.locator('.chip-convenio').allInnerTexts())
  await tocar('.chip-convenio', 'Unimed')
  const planos = await page.locator('.chip-reply').allInnerTexts()
  console.log('botões de plano:', planos)
  await page.screenshot({ path: path.join(OUT, '2-planos.png') })
  if (planos.length) await tocar('.chip-reply', planos[0].trim())
  console.log('botões restantes:', await page.locator('.chip').allInnerTexts())

  for (const fala of [
    'Estou com dor no joelho ao subir escadas, faz duas semanas',
    'É uma dor nova, sem queda nem pancada. Incha um pouco no fim do dia.',
    'Não tenho febre nem outros sintomas. Qual especialista devo procurar?',
    'Pode indicar a especialidade e os horários, por favor.',
  ]) {
    await enviar(fala)
    if (await page.locator('.slot-card').count()) break
  }
  console.log(`[${seg()}s] horários:`, (await page.locator('.slot-card').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ')))

  const antes = await respostas().count()
  await page.locator('.slot-card').first().click()
  await aguardarNova(antes)
  console.log(`[${seg()}s] [horário escolhido]\n          < ${await ultima()}`)
  await enviar('111.111.111-11') // inválido: deve pedir de novo
  await enviar('529.982.247-25')
  console.log('resposta rápida da carteirinha:', await page.locator('.chip-reply').allInnerTexts())
  await enviar('0 123 456789012-3')
  await enviar('(11) 98765-4321')
  await enviar('pedro.oliveira@exemplo.com.br')
  await page.screenshot({ path: path.join(OUT, '3-resumo.png') })
  await enviar('Sim')
  await page.screenshot({ path: path.join(OUT, '4-confirmado.png') })
} catch (e) {
  console.log(`[${seg()}s] FALHOU: ${e.message.split('\n')[0]}`)
  await page.screenshot({ path: path.join(OUT, 'falha.png') })
  for (const t of await respostas().allInnerTexts()) console.log('   <', t.replace(/\s+/g, ' ').slice(0, 260))
} finally {
  await browser.close()
}
