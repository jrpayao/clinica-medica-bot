"""Classificador de intencao pre-LLM.

Classifica a mensagem do usuario antes do roteamento de modelos,
sem chamada LLM — baseado em palavras-chave para zero latencia/custo.

Retorna: {"tipo": TipoIntencao, "confianca": float}
"""

from enum import StrEnum

import structlog

log = structlog.get_logger(__name__)

# Palavras-chave por categoria — peso 1.0 por match
_KEYWORDS_SAUDE: list[str] = [
    "dor", "febre", "nausea", "tontura", "tosse", "cansaco",
    "falta de ar", "vomito", "enjoo", "sangue", "inchaço",
    "coceira", "mancha", "alergia", "pressao", "palpitacao",
    "formigamento", "fraqueza", "tremor", "desmaio", "convulsao",
    "sintoma", "sinto", "estou sentindo", "me doi", "dói",
    "dor de cabeca", "dor no peito", "dor nas costas",
    "dor de estomago", "dor no joelho", "mal estar",
    "nao estou bem", "estou mal", "emagrecer", "engordar",
    "insonia", "ansiedade", "depressao",
]

_KEYWORDS_AGENDAMENTO: list[str] = [
    "agendar", "marcar", "consulta", "horario", "horarios",
    "disponivel", "disponibilidade", "medico", "especialista",
    "cardiologista", "neurologista", "dermatologista",
    "cancelar", "cancelamento", "remarcar", "reagendar",
    "proximo horario", "primeira consulta", "nova consulta",
    "quero uma consulta", "preciso de consulta", "ver horarios",
]

_KEYWORDS_GERAL: list[str] = [
    "ola", "bom dia", "boa tarde", "boa noite", "oi",
    "quanto custa", "valor", "preco", "plano",
    "obrigado", "obrigada", "tchau", "ate logo",
]


class TipoIntencao(StrEnum):
    SAUDE = "saude"
    AGENDAMENTO = "agendamento"
    GERAL = "geral"


def classificar_intencao(texto: str) -> dict:
    """Classifica a intencao da mensagem do usuario.

    Abordagem: contagem de matches de palavras-chave por categoria.
    Categoria com mais matches ganha. Empate → GERAL.

    Args:
        texto: Mensagem bruta do usuario.

    Returns:
        dict com "tipo" (TipoIntencao) e "confianca" (0.0-1.0).
    """
    if not texto.strip():
        return {"tipo": TipoIntencao.GERAL, "confianca": 1.0}

    texto_lower = texto.lower()

    score_saude = sum(1 for kw in _KEYWORDS_SAUDE if kw in texto_lower)
    score_agendamento = sum(1 for kw in _KEYWORDS_AGENDAMENTO if kw in texto_lower)
    score_geral = sum(1 for kw in _KEYWORDS_GERAL if kw in texto_lower)

    total = score_saude + score_agendamento + score_geral

    if total == 0:
        resultado = {"tipo": TipoIntencao.GERAL, "confianca": 0.5}
    elif score_saude > score_agendamento and score_saude >= score_geral:
        confianca = round(score_saude / total, 2)
        resultado = {"tipo": TipoIntencao.SAUDE, "confianca": confianca}
    elif score_agendamento > score_saude and score_agendamento > score_geral:
        confianca = round(score_agendamento / total, 2)
        resultado = {"tipo": TipoIntencao.AGENDAMENTO, "confianca": confianca}
    else:
        confianca = round(max(score_geral, 1) / max(total, 1), 2)
        resultado = {"tipo": TipoIntencao.GERAL, "confianca": confianca}

    log.debug(
        "intencao_classificada",
        tipo=resultado["tipo"],
        confianca=resultado["confianca"],
        scores={"saude": score_saude, "agendamento": score_agendamento, "geral": score_geral},
    )
    return resultado
