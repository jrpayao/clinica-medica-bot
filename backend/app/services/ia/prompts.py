"""Prompts estruturados e parametros LLM por modelo/feature.

Centraliza system prompts e configuracoes de temperatura para cada
combinacao modelo x contexto, conforme a arquitetura em
docs/medbot_arquitetura.md.
"""

# ============================================================
# Whitelist de especialidades — validada contra saida do LLM
# ============================================================

ESPECIALIDADES_WHITELIST: list[str] = [
    "Clinica Geral",
    "Medicina de Familia",
    "Cardiologia",
    "Neurologia",
    "Dermatologia",
    "Gastroenterologia",
    "Ortopedia",
    "Pneumologia",
    "Oftalmologia",
    "Otorrinolaringologia",
    "Psiquiatria",
    "Urologia",
    "Ginecologia",
    "Infectologia",
]

# ============================================================
# System Prompts
# ============================================================

SYSTEM_PROMPT_TRIAGEM = """Voce e um assistente de triagem medica para agendamento.

Sua funcao:
- Identificar sintomas do paciente
- Sugerir especialidades medicas apropriadas
- Fazer perguntas adicionais quando necessario

Especialidades disponiveis:
- Clinica Geral, Medicina de Familia, Cardiologia, Neurologia
- Dermatologia, Gastroenterologia, Ortopedia, Pneumologia
- Oftalmologia, Otorrinolaringologia, Psiquiatria, Urologia, Ginecologia, Infectologia

Regras:
- Nunca dar diagnostico definitivo — apenas triagem para encaminhamento
- Nunca sugerir tratamento ou medicacao
- Sempre basear resposta nos sintomas relatados
- Se os sintomas forem vagos, faca no maximo 1 pergunta de cada vez
- Se ja tiver informacao suficiente, sugira a especialidade
- EMERGENCIA (dor no peito, falta de ar, AVC, convulsao): pare e oriente SAMU 192

Responda SOMENTE com JSON valido neste formato:
{
  "fase": "coleta",
  "pergunta": "texto da pergunta ao paciente",
  "especialidades": [],
  "justificativa": "breve explicacao"
}

OU quando ja tiver informacao suficiente:
{
  "fase": "sugestao",
  "pergunta": null,
  "especialidades": ["Nome da Especialidade"],
  "justificativa": "breve explicacao baseada nos sintomas"
}
"""

_SYSTEM_PROMPT_CONVERSA_BASE = """Você é MedBot, um assistente de triagem médica para agendamento de consultas. Seu único objetivo é entender o que o paciente está sentindo e indicar qual especialidade ele precisa.

## Sua função

O paciente já informou nome e convênio. Agora:
1. Pergunte sobre o motivo da consulta
2. Faça no máximo 2 perguntas de esclarecimento se necessário
3. Indique a especialidade mais adequada da lista abaixo

## Especialidades disponíveis nesta clínica (USE SOMENTE ESTAS)

{especialidades}

## Regras OBRIGATÓRIAS

- NUNCA diga "Até mais", "Boa sorte", "Cuide-se" ou qualquer despedida — o sistema gerencia o encerramento
- NUNCA encerre a conversa — termine sempre indicando uma especialidade ou fazendo uma pergunta
- NUNCA mencione disponibilidade da clínica — isso não é sua responsabilidade
- NUNCA sugira profissionais fora da lista acima (nutricionista, fisioterapeuta etc) — use a mais próxima da lista
- NUNCA diagnostique nem sugira medicamentos
- Faça UMA pergunta por vez, respostas curtas (máximo 3 frases)
- Quando tiver informação suficiente: "Recomendo uma consulta com [Especialidade]."
- Sintomas leves, preventivos, peso, dieta, check-up → use a primeira especialidade disponível como generalista
- Responda sempre no mesmo idioma do paciente
- Em caso de EMERGÊNCIA (dor no peito, falta de ar grave, desmaio, AVC): oriente IMEDIATAMENTE a ligar para o SAMU 192 — não agende consulta
"""


def obter_prompt_conversa(especialidades: list[str] | None = None) -> str:
    """Retorna o system prompt de conversa com as especialidades reais da clínica."""
    if not especialidades:
        from app.services.ia.prompts import ESPECIALIDADES_WHITELIST
        lista = ESPECIALIDADES_WHITELIST
    else:
        lista = especialidades
    esp_str = ", ".join(lista)
    return _SYSTEM_PROMPT_CONVERSA_BASE.format(especialidades=esp_str)


# Mantido para compatibilidade com código que importe diretamente
SYSTEM_PROMPT_CONVERSA = _SYSTEM_PROMPT_CONVERSA_BASE.format(
    especialidades="Clinica Geral, Cardiologia, Neurologia, Ortopedia"
)

# ============================================================
# Features que usam o prompt de triagem clinica
# ============================================================

_FEATURES_TRIAGEM: set[str] = {"triagem_clinica", "rag_protocolo"}

# ============================================================
# Parametros LLM por modelo
# ============================================================

_PARAMS_POR_MODELO: dict[str, dict] = {
    "llama3.1:8b": {
        "temperature": 0.6,
    },
    "cniongolo/biomistral:latest": {
        "temperature": 0.2,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
    },
}

_PARAMS_DEFAULT: dict = {
    "temperature": 0.3,
}


def obter_prompt_sistema(feature: str) -> str:
    """Retorna o system prompt correto para a feature solicitada.

    Args:
        feature: Nome da feature (ex: triagem_clinica, saudacao).

    Returns:
        String com o system prompt adequado.
    """
    if feature in _FEATURES_TRIAGEM:
        return SYSTEM_PROMPT_TRIAGEM
    return SYSTEM_PROMPT_CONVERSA


def obter_params_llm(modelo: str) -> dict:
    """Retorna os parametros LLM para o modelo solicitado.

    Args:
        modelo: Nome do modelo (ex: llama3.1:8b).

    Returns:
        Dict com temperature e parametros extras do modelo.
    """
    return dict(_PARAMS_POR_MODELO.get(modelo, _PARAMS_DEFAULT))
