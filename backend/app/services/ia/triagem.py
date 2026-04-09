"""Servico de triagem clinica.

Classifica urgencia dos sintomas e detecta emergencias.
REGRA: Emergencia detectada bloqueia agendamento e exibe SAMU 192.
"""

import structlog

from app.core.config import EMERGENCY_KEYWORDS
from app.models.consulta import ConsultaUrgencia

log = structlog.get_logger(__name__)

_URGENCIA_ORDEM = {
    ConsultaUrgencia.BAIXA: 0,
    ConsultaUrgencia.MEDIA: 1,
    ConsultaUrgencia.ALTA: 2,
    ConsultaUrgencia.EMERGENCIA: 3,
}

MENSAGEM_EMERGENCIA = (
    "ATENCAO: Seus sintomas indicam uma possivel EMERGENCIA MEDICA.\n\n"
    "Ligue IMEDIATAMENTE para o SAMU: 192\n"
    "Ou dirija-se a UPA/pronto-socorro mais proximo.\n\n"
    "NAO e possivel agendar consulta para casos de emergencia. "
    "Sua saude e prioridade."
)


def detectar_emergencia(texto: str) -> bool:
    """Verifica se o texto contem palavras-chave de emergencia.

    Comparacao case-insensitive.
    """
    texto_lower = texto.lower()
    for keyword in EMERGENCY_KEYWORDS:
        if keyword.lower() in texto_lower:
            log.warning(
                "emergencia_detectada",
                keyword=keyword,
            )
            return True
    return False


def classificar_urgencia(
    sintomas: str,
    duracao_dias: int | None = None,
    intensidade: int | None = None,
) -> dict:
    """Classifica urgencia baseado nos sintomas.

    Returns:
        dict com urgencia, pode_agendar, mensagem_extra
    """
    # Emergencia tem prioridade absoluta
    if detectar_emergencia(sintomas):
        return {
            "urgencia": ConsultaUrgencia.EMERGENCIA,
            "pode_agendar": False,
            "mensagem": MENSAGEM_EMERGENCIA,
            "priorizar_mesmo_dia": False,
        }

    # Classificacao por heuristica
    urgencia = ConsultaUrgencia.BAIXA
    priorizar = False

    # Intensidade alta (>=8 em escala 1-10)
    if intensidade and intensidade >= 8:
        urgencia = ConsultaUrgencia.ALTA
        priorizar = True
    elif intensidade and intensidade >= 5:
        urgencia = ConsultaUrgencia.MEDIA

    # Duracao curta com sintomas novos sugere maior urgencia
    if duracao_dias is not None and duracao_dias <= 1 and urgencia == ConsultaUrgencia.BAIXA:
        urgencia = ConsultaUrgencia.MEDIA

    # Palavras que indicam urgencia alta (nao emergencia)
    palavras_alta = ["febre alta", "muita dor", "piora rapida", "sangue", "inchaço"]
    texto_lower = sintomas.lower()
    for palavra in palavras_alta:
        if palavra in texto_lower:
            if _URGENCIA_ORDEM[urgencia] < _URGENCIA_ORDEM[ConsultaUrgencia.ALTA]:
                urgencia = ConsultaUrgencia.ALTA
                priorizar = True

    return {
        "urgencia": urgencia,
        "pode_agendar": True,
        "mensagem": None,
        "priorizar_mesmo_dia": priorizar,
    }
