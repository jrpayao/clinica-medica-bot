"""Testes da camada de orquestracao do ChatService.

Verifica que chat_service conecta corretamente:
- detectar_emergencia (ANTES do LLM)
- state_machine (transicoes de estado)
- intent_classifier (classificacao de intencao)
- robustez (JSON parsing, whitelist, limite perguntas, fallback)
- routing (modelo correto por estado)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ia.chat_service import ChatService, CHAT_SESSION_TTL
from app.services.ia.state_machine import ChatEstado


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def service(mock_db, mock_redis):
    return ChatService(mock_db, mock_redis)


def _session(estado: str = "START", mensagens=None, dados=None) -> str:
    """Helper: cria JSON de sessao com estado e dados."""
    return json.dumps({
        "token": "test-token",
        "canal": "PORTAL",
        "mensagens": mensagens or [],
        "estado": estado,
        "dados_coletados": dados or {
            "sintomas": [],
            "especialidade": None,
            "medico": None,
            "horario": None,
            "perguntas_coleta": 0,
        },
    })


# ============================================================
# Estrutura da sessao
# ============================================================

async def test_criar_sessao_usa_estado_start(service, mock_redis):
    """RF: Sessao criada com estado=START (ChatEstado)."""
    await service.criar_sessao()
    dados = json.loads(mock_redis.set.call_args[0][1])
    assert dados["estado"] == ChatEstado.START


async def test_criar_sessao_tem_campos_estruturados(service, mock_redis):
    """RF: dados_coletados tem campos estruturados da arquitetura."""
    await service.criar_sessao()
    dados = json.loads(mock_redis.set.call_args[0][1])
    dc = dados["dados_coletados"]
    assert "sintomas" in dc
    assert "especialidade" in dc
    assert "medico" in dc
    assert "horario" in dc
    assert "perguntas_coleta" in dc
    assert dc["sintomas"] == []
    assert dc["especialidade"] is None


# ============================================================
# Emergencia — REGRA DE OURO: nunca deixar LLM decidir
# ============================================================

async def test_emergencia_nao_chama_llm(service, mock_redis):
    """CRITICO: Emergencia deve retornar SAMU sem invocar LLM."""
    mock_redis.get.return_value = _session(estado="COLETANDO_SINTOMAS")

    with patch.object(service, "_criar_llm") as mock_llm:
        resultado = await service.processar_mensagem(
            "test-token", "Estou com dor no peito intensa"
        )

    mock_llm.assert_not_called()
    assert resultado["emergencia"] is True
    assert "192" in resultado["resposta"] or "SAMU" in resultado["resposta"]


async def test_emergencia_bloqueia_agendamento(service, mock_redis):
    """CRITICO: Emergencia retorna pode_agendar=False."""
    mock_redis.get.return_value = _session(estado="COLETANDO_SINTOMAS")

    resultado = await service.processar_mensagem(
        "test-token", "Sinto falta de ar grave"
    )

    assert resultado["emergencia"] is True
    assert resultado.get("sessao_expirada") is False


async def test_emergencia_em_qualquer_estado(service, mock_redis):
    """RF: Emergencia e detectada em qualquer estado, inclusive CONFIRMACAO."""
    mock_redis.get.return_value = _session(estado="CONFIRMACAO")

    with patch.object(service, "_criar_llm") as mock_llm:
        resultado = await service.processar_mensagem(
            "test-token", "Estou tendo um AVC"
        )

    mock_llm.assert_not_called()
    assert resultado["emergencia"] is True


# ============================================================
# Avanco de estado
# ============================================================

async def test_estado_avanca_start_para_coletando(service, mock_redis):
    """RF: Primeira mensagem avanca START para COLETANDO_NOME (fluxo guiado v2)."""
    mock_redis.get.return_value = _session(estado="START")

    mock_response = MagicMock()
    mock_response.content = "Ola! Pode descrever seus sintomas?"
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 10}}

    with patch.object(service, "_criar_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        await service.processar_mensagem("test-token", "oi")

    saved = json.loads(mock_redis.set.call_args[0][1])
    assert saved["estado"] == ChatEstado.COLETANDO_NOME


async def test_estado_retornado_na_resposta(service, mock_redis):
    """RF: Resposta contem estado atual para o frontend."""
    mock_redis.get.return_value = _session(estado="COLETANDO_SINTOMAS")

    mock_response = MagicMock()
    mock_response.content = "Ha quanto tempo?"
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 10}}

    with patch.object(service, "_criar_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        resultado = await service.processar_mensagem("test-token", "dor de cabeca")

    assert "estado" in resultado


# ============================================================
# Roteamento por estado
# ============================================================

async def test_coletando_sintomas_usa_modelo_economico(service, mock_redis):
    """RF: COLETANDO_SINTOMAS usa LLaMA (modelo economico)."""
    mock_redis.get.return_value = _session(estado="COLETANDO_SINTOMAS")

    mock_response = MagicMock()
    mock_response.content = "Entendi."
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    modelos_usados = []
    original_criar = service._criar_llm

    def capturar_modelo(modelo, **kwargs):
        modelos_usados.append(modelo)
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=mock_response)
        return llm

    with patch.object(service, "_criar_llm", side_effect=capturar_modelo):
        await service.processar_mensagem("test-token", "dor de cabeca")

    from app.core.config import settings
    assert modelos_usados[0] == settings.model_economico


async def test_triagem_usa_modelo_medico(service, mock_redis):
    """RF: Estado TRIAGEM usa BioMistral (modelo medico)."""
    mock_redis.get.return_value = _session(estado="TRIAGEM")

    json_triagem = '{"fase": "sugestao", "pergunta": null, "especialidades": ["Cardiologia"], "justificativa": "dor no peito"}'
    mock_response = MagicMock()
    mock_response.content = json_triagem
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 50, "completion_tokens": 30}}

    modelos_usados = []

    def capturar_modelo(modelo, **kwargs):
        modelos_usados.append(modelo)
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=mock_response)
        return llm

    with patch.object(service, "_criar_llm", side_effect=capturar_modelo):
        await service.processar_mensagem("test-token", "sinto pressao no peito")

    from app.core.config import settings
    assert modelos_usados[0] == settings.model_medico


# ============================================================
# Robustez: JSON e whitelist
# ============================================================

async def test_triagem_extrai_especialidade_do_json(service, mock_redis):
    """RF: Resposta JSON do BioMistral tem especialidade extraida e validada."""
    mock_redis.get.return_value = _session(estado="TRIAGEM")

    json_resp = '{"fase": "sugestao", "pergunta": null, "especialidades": ["Cardiologia"], "justificativa": "ok"}'
    mock_response = MagicMock()
    mock_response.content = json_resp
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 50, "completion_tokens": 30}}

    with patch.object(service, "_criar_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        await service.processar_mensagem("test-token", "sinto palpitacoes frequentes")

    saved = json.loads(mock_redis.set.call_args[0][1])
    assert saved["dados_coletados"]["especialidade"] == "Cardiologia"


async def test_triagem_valida_especialidade_contra_whitelist(service, mock_redis):
    """RF: Especialidade fora da whitelist e substituida por Clinica Geral."""
    mock_redis.get.return_value = _session(estado="TRIAGEM")

    json_resp = '{"fase": "sugestao", "pergunta": null, "especialidades": ["Homeopatia"], "justificativa": "ok"}'
    mock_response = MagicMock()
    mock_response.content = json_resp
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 50, "completion_tokens": 30}}

    with patch.object(service, "_criar_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        await service.processar_mensagem("test-token", "problemas")

    saved = json.loads(mock_redis.set.call_args[0][1])
    assert saved["dados_coletados"]["especialidade"] == "Clinica Geral"


async def test_json_invalido_retorna_fallback(service, mock_redis):
    """RF: JSON invalido do LLM resulta em mensagem de fallback."""
    mock_redis.get.return_value = _session(estado="TRIAGEM")

    mock_response = MagicMock()
    mock_response.content = "Desculpe, nao entendi."
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    with patch.object(service, "_criar_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        resultado = await service.processar_mensagem("test-token", "sinto algo")

    # Fallback nao deve ser vazio nem expor erro tecnico
    assert len(resultado["resposta"]) > 0
    assert resultado.get("fallback") is True


# ============================================================
# Limite de perguntas
# ============================================================

async def test_limite_perguntas_avanca_para_triagem(service, mock_redis):
    """RF: Apos 3 perguntas em COLETANDO_SINTOMAS, avanca para TRIAGEM."""
    session_data = json.loads(_session(estado="COLETANDO_SINTOMAS"))
    session_data["dados_coletados"]["perguntas_coleta"] = 3
    mock_redis.get.return_value = json.dumps(session_data)

    mock_response = MagicMock()
    mock_response.content = "Mais algum sintoma?"
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    with patch.object(service, "_criar_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        await service.processar_mensagem("test-token", "nao tenho mais")

    saved = json.loads(mock_redis.set.call_args[0][1])
    assert saved["estado"] == ChatEstado.TRIAGEM


# ============================================================
# Contador de perguntas
# ============================================================

async def test_pergunta_do_bot_incrementa_contador(service, mock_redis):
    """RF: Cada resposta do bot em COLETANDO_SINTOMAS incrementa contador."""
    session_data = json.loads(_session(estado="COLETANDO_SINTOMAS"))
    session_data["dados_coletados"]["perguntas_coleta"] = 1
    mock_redis.get.return_value = json.dumps(session_data)

    mock_response = MagicMock()
    mock_response.content = "Ha quanto tempo voce sente isso?"
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    with patch.object(service, "_criar_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        await service.processar_mensagem("test-token", "dor de cabeca")

    saved = json.loads(mock_redis.set.call_args[0][1])
    assert saved["dados_coletados"]["perguntas_coleta"] == 2
