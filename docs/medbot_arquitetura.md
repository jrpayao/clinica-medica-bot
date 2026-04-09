# 🤖 MedBot — Arquitetura de Conversação e Triagem Médica

## 📌 Visão Geral

Este documento descreve a arquitetura e o fluxo conversacional de um chatbot médico para:

- Triagem de sintomas
- Sugestão de especialidade
- Agendamento de consultas

A solução utiliza dois modelos LLM:

- LLaMA 3.1 (8B) → Conversação geral e controle de fluxo
- BioMistral → Triagem médica especializada

---

# 🧠 Arquitetura Geral

User Input
   ↓
Classificação de Intenção (LLaMA)
   ↓
Router
   ├── Emergência (Regras fixas)
   ├── Triagem (BioMistral)
   └── Conversa / Agendamento (LLaMA)
   ↓
State Manager
   ↓
Sistema de Agendamento (API)

---

# 🔀 Classificação de Intenção

## Objetivo

Identificar o tipo de mensagem do usuário:

{
  "tipo": "saude" | "agendamento" | "geral"
}

## Prompt sugerido

Classifique a intenção da mensagem:

Categorias:
- saude (sintomas, dor, febre, etc)
- agendamento (marcar consulta)
- geral (outros assuntos)

Responda apenas:
{ "tipo": "..." }

---

# 🚨 Camada de Emergência (CRÍTICA)

## Sintomas de alto risco (hardcoded)

- rigidez no pescoço
- convulsão
- desmaio
- confusão mental
- dor no peito intensa
- falta de ar grave
- fraqueza em um lado do corpo
- visão turva súbita
- dor de cabeça súbita e muito intensa

## Regra

- Se detectar qualquer sintoma acima:
  → NÃO chamar LLM
  → Interromper fluxo normal

## Resposta padrão de emergência

⚠️ Atenção: os sintomas informados podem indicar uma condição médica grave.

Recomendamos que você procure atendimento de emergência imediatamente.

Se possível, dirija-se ao pronto atendimento mais próximo ou ligue para um serviço de emergência.

Deseja que eu te ajude a encontrar uma unidade próxima?

---

# 🧪 Triagem com BioMistral

## Função

- Coletar sintomas
- Refinar contexto
- Sugerir especialidade

---

## Prompt estruturado

Você é um assistente de triagem médica para agendamento.

Sua função:
- Identificar sintomas
- Sugerir especialidades médicas apropriadas
- Fazer perguntas adicionais quando necessário

Especialidades disponíveis:
- clinico_geral
- medico_familia
- neurologia
- cardiologia
- infectologia

Regras:
- Nunca dar diagnóstico definitivo
- Nunca sugerir tratamento
- Sempre basear resposta em sintomas
- Se os sintomas forem vagos, peça mais detalhes
- Se já tiver informação suficiente, sugira especialidade

Formato da resposta:

{
  "fase": "coleta" | "sugestao",
  "pergunta": "texto",
  "especialidades": [],
  "justificativa": "texto curto"
}

---

# 💬 Conversação (LLaMA 3.1)

## Responsabilidades

- Interação natural com usuário
- Condução do fluxo
- Perguntas administrativas
- Confirmação de agendamento

---

## Exemplo de fluxo

Olá! Eu sou o MedBot.

Para começar, me diga qual sintoma você está sentindo.

---

Com base nos sintomas, o mais indicado é:

- Clínico Geral

Deseja agendar com essa especialidade?

---

Você tem preferência por algum médico?
Ou deseja ver os primeiros horários disponíveis?

---

Temos disponíveis:

1. Dr. João – hoje às 14:00
2. Dra. Ana – amanhã às 09:00

Qual deseja?

---

Confirmando:

Especialidade: Clínico Geral  
Médico: Dra. Ana  
Data: 10/04 às 09:00  

Deseja confirmar?

---

# 🔄 Máquina de Estados

START
→ COLETANDO_SINTOMAS
→ TRIAGEM
→ SUGESTAO_ESPECIALIDADE
→ ESCOLHA_ESPECIALIDADE
→ ESCOLHA_MEDICO
→ ESCOLHA_HORARIO
→ CONFIRMACAO
→ FINALIZADO

---

# 🧩 State Manager

{
  "modo": "chat" | "triagem" | "agendamento",
  "sintomas": [],
  "especialidade": null,
  "medico": null,
  "horario": null
}

---

# ⚙️ Parâmetros recomendados

## LLaMA 3.1
temperature: 0.6

## BioMistral
temperature: 0.2
top_p: 0.9
repeat_penalty: 1.1

---

# 🛡️ Validações obrigatórias

- JSON válido (retry automático)
- Especialidade dentro da whitelist
- Limite de perguntas (máx. 3)
- Fallback em caso de erro

---

# 🚫 Problemas comuns

- Loop de perguntas → limitar interações
- Respostas fora do escopo → roteamento correto
- JSON inválido → retry automático
- Alucinação → validação backend

---

# ✅ Regras de Ouro

- Nunca deixar LLM decidir emergência
- Nunca misturar modelos na mesma resposta
- Sempre validar saída no backend
- LLM decide, backend controla

---

# 🚀 Conclusão

Arquitetura final:

- LLaMA 3.1 → experiência conversacional
- BioMistral → triagem médica
- Regras simples → segurança
- Backend → controle total

Sistema leve, escalável e pronto para produção.
