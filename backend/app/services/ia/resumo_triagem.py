"""Resumo de triagem para o profissional (T92).

O profissional recebe, antes do atendimento, o que o paciente relatou no chat — sem conclusão clínica.
O resumo vem do modelo econômico; se o modelo falhar, demorar ou escrever algo que pareça diagnóstico
ou prescrição, vale o resumo montado por regra a partir do próprio relato.
"""

import asyncio
import re
import unicodedata

import structlog

log = structlog.get_logger(__name__)

MAX_PALAVRAS = 200
TEMPO_LIMITE_IA_S = 15

# Sinais de que o texto concluiu algo que só o profissional pode concluir
_TERMOS_DIAGNOSTICO = (
    "diagnostic", "prescrev", "prescric", "receit", "medicar", "medicament", "posologia",
    "tratamento indicado", "deve tomar", "sofre de", "portador de", "portadora de",
    "trata-se de", "confirma-se", "provavelmente tem", "provavel que tenha", "indica que tem",
)

# Rótulos usados nos relatórios de sintomas mais citados
_CATEGORIAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Dor de cabeça", ("dor de cabeca", "cefaleia", "enxaqueca")),
    ("Febre", ("febre", "febril")),
    ("Tosse", ("tosse", "tossindo")),
    ("Dor de garganta", ("garganta",)),
    ("Náusea / vômito", ("nausea", "enjoo", "vomit", "ansia")),
    ("Dor abdominal", ("dor abdominal", "dor na barriga", "dor de barriga", "dor no estomago", "colica")),
    ("Dor nas costas", ("dor nas costas", "lombar", "coluna")),
    ("Dor articular / muscular", ("joelho", "ombro", "articula", "muscular", "tornozelo", "torcao", "torci")),
    ("Dor no peito", ("dor no peito", "aperto no peito", "palpitac")),
    ("Falta de ar", ("falta de ar", "dificuldade para respirar", "cansaco ao respirar")),
    ("Tontura", ("tontura", "tonto", "tonta", "vertigem")),
    ("Pele", ("coceira", "mancha", "alergia", "pele", "acne", "espinha")),
    ("Ansiedade / sono", ("ansiedade", "ansios", "insonia", "nao consigo dormir", "estresse", "depress")),
    ("Visão", ("visao", "vista", "olho", "enxergar")),
    ("Check-up / rotina", ("check-up", "checkup", "check up", "rotina", "preventiv", "exames de rotina")),
)

_PROMPT_SISTEMA = (
    "Você escreve o resumo de pré-atendimento que o profissional de saúde lê antes de receber o paciente. "
    "Use somente o que o paciente relatou. Escreva em português, em texto corrido, no máximo 120 palavras, "
    "na terceira pessoa ('Paciente relata...'). Informe queixa principal, há quanto tempo, intensidade e "
    "sintomas associados, quando o paciente tiver dito. "
    "NUNCA dê diagnóstico, hipótese de doença, tratamento, exame ou medicamento. Não invente nada."
)


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )


def limitar_palavras(texto: str, limite: int = MAX_PALAVRAS) -> str:
    palavras = texto.split()
    if len(palavras) <= limite:
        return texto.strip()
    return " ".join(palavras[:limite]) + " …"


def contem_diagnostico(texto: str) -> bool:
    plano = _sem_acento(texto)
    return any(termo in plano for termo in _TERMOS_DIAGNOSTICO)


def categorizar_sintomas(relatos: list[str]) -> list[str]:
    """Rótulos dos sintomas citados, na ordem da tabela de categorias, sem repetição."""
    plano = _sem_acento(" ".join(relatos or []))
    return [rotulo for rotulo, termos in _CATEGORIAS if any(t in plano for t in termos)]


def resumo_por_regra(dados: dict) -> str:
    """Resumo sem IA: o relato do paciente, entre aspas, mais o que a triagem registrou."""
    relatos = [r.strip() for r in (dados.get("sintomas") or []) if r and r.strip()]
    partes = []
    if relatos:
        partes.append("Relato do paciente no chat: “" + " / ".join(relatos) + "”.")
    else:
        partes.append("O paciente não descreveu sintomas no chat.")
    if dados.get("especialidade"):
        partes.append(f"Especialidade indicada na triagem: {dados['especialidade']}.")
    if dados.get("pagamento"):
        partes.append(f"Atendimento: {dados['pagamento']}.")
    if dados.get("urgencia"):
        partes.append(f"Urgência registrada: {str(dados['urgencia']).capitalize()}.")
    return limitar_palavras(" ".join(partes))


async def _invocar_llm(sistema: str, usuario: str) -> tuple[str, int, int, str]:
    """Chama o modelo econômico. Devolve (texto, tokens de entrada, tokens de saída, modelo)."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    from app.core.config import settings
    from app.services.ia.router import obter_api_key, obter_base_url

    modelo = settings.model_economico
    llm = ChatOpenAI(
        model=modelo,
        openai_api_key=obter_api_key(),
        openai_api_base=obter_base_url(),
        temperature=0.2,
        max_tokens=320,
    )
    from app.core import metricas

    async with metricas.medir_ia("resumo_triagem"):
        resposta = await asyncio.wait_for(
            llm.ainvoke([SystemMessage(content=sistema), HumanMessage(content=usuario)]),
            timeout=TEMPO_LIMITE_IA_S,
        )
    uso = resposta.response_metadata.get("token_usage", {}) or {}
    return str(resposta.content), uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0), modelo


async def gerar_resumo_triagem(dados: dict, invocar=None) -> dict:
    """Monta o resumo guardado em `atendimentos.triagem_resumo`.

    `uso` vem preenchido sempre que o modelo foi chamado (mesmo se o texto foi descartado),
    para quem chama registrar no billing.
    """
    relatos = [r.strip() for r in (dados.get("sintomas") or []) if r and r.strip()]
    texto, origem, uso = resumo_por_regra(dados), "regra", None

    if relatos:
        try:
            usuario = (
                "Relato do paciente:\n- " + "\n- ".join(relatos)
                + f"\n\nEspecialidade indicada na triagem: {dados.get('especialidade') or 'não definida'}."
            )
            bruto, entrada, saida, modelo = await (invocar or _invocar_llm)(_PROMPT_SISTEMA, usuario)
            uso = {"modelo": modelo, "prompt_tokens": entrada, "completion_tokens": saida}
            limpo = re.sub(r"\s+", " ", bruto or "").strip().strip("*")
            if limpo and not contem_diagnostico(limpo):
                texto, origem = limitar_palavras(limpo), "ia"
            else:
                log.warning("resumo_triagem_descartado", motivo="vazio" if not limpo else "diagnostico")
        except Exception as erro:  # modelo fora do ar, tempo esgotado, resposta inesperada
            log.warning("resumo_triagem_ia_falhou", erro=str(erro)[:200])

    return {
        "texto": texto,
        "origem": origem,
        "sintomas": relatos,
        "categorias": categorizar_sintomas(relatos),
        "especialidade": dados.get("especialidade"),
        "urgencia": dados.get("urgencia"),
        "uso": uso,
    }


def texto_do_resumo(triagem_resumo: dict | None) -> str | None:
    """Texto do resumo guardado no atendimento (None quando não houve triagem pelo chat)."""
    if not isinstance(triagem_resumo, dict):
        return None
    texto = triagem_resumo.get("texto")
    return texto.strip() if isinstance(texto, str) and texto.strip() else None
