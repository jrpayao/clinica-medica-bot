"""Validacoes de robustez do fluxo LLM.

Implementa as 4 validacoes obrigatorias da arquitetura:
1. Extracao de JSON com fallback (retry trigger)
2. Whitelist de especialidades
3. Limite de perguntas na fase de coleta
4. Mensagem de fallback para falhas do LLM
"""

import json
import re

import structlog

from app.services.ia.prompts import ESPECIALIDADES_WHITELIST

log = structlog.get_logger(__name__)

# Limite de perguntas na fase COLETANDO_SINTOMAS antes de avancar
MAX_PERGUNTAS_COLETA: int = 3

# Especialidade padrao quando nenhuma valida for encontrada
ESPECIALIDADE_FALLBACK: str = "Clinica Geral"

# Mensagem exibida ao paciente quando o LLM falha apos retries
FALLBACK_MESSAGE: str = (
    "Desculpe, estou com dificuldades tecnicas no momento. "
    "Por favor, tente novamente em instantes ou ligue para a recepção "
    "para agendar sua consulta."
)

# Mapa lowercase → nome canônico para lookup case-insensitive
_WHITELIST_MAP: dict[str, str] = {e.lower(): e for e in ESPECIALIDADES_WHITELIST}


def extrair_json_llm(texto: str) -> dict | None:
    """Extrai o primeiro objeto JSON valido de uma string.

    Suporta JSON puro ou JSON embutido em texto livre.
    Retorna None se nenhum JSON valido for encontrado
    (sinal para o chamador executar retry).

    Args:
        texto: Resposta bruta do LLM.

    Returns:
        dict com o JSON extraido, ou None.
    """
    if not texto:
        return None

    # Tentativa 1: texto e JSON puro
    try:
        return json.loads(texto.strip())
    except json.JSONDecodeError:
        pass

    # Tentativa 2: localizar { ... } com regex (primeira ocorrencia)
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    log.warning("json_llm_invalido", texto_len=len(texto))
    return None


def validar_especialidade(nome: str) -> str:
    """Valida se a especialidade esta na whitelist.

    Comparacao case-insensitive.
    Retorna o nome canonico da whitelist se valido,
    ou ESPECIALIDADE_FALLBACK se invalido/vazio.

    Args:
        nome: Nome da especialidade retornado pelo LLM.

    Returns:
        Nome canonico da especialidade ou 'Clinica Geral'.
    """
    if not nome:
        return ESPECIALIDADE_FALLBACK

    canonical = _WHITELIST_MAP.get(nome.lower().strip())
    if canonical:
        return canonical

    log.warning(
        "especialidade_fora_da_whitelist",
        especialidade=nome,
        fallback=ESPECIALIDADE_FALLBACK,
    )
    return ESPECIALIDADE_FALLBACK


def verificar_limite_perguntas(total_perguntas: int) -> bool:
    """Verifica se ainda e possivel fazer mais perguntas na fase de coleta.

    Args:
        total_perguntas: Numero de perguntas ja feitas nesta fase.

    Returns:
        True se ainda pode perguntar, False se deve avancar de estado.
    """
    return total_perguntas <= MAX_PERGUNTAS_COLETA
