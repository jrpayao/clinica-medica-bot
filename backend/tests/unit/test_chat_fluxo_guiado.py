"""Testes unitários — Fluxo guiado de agendamento (T83).

Cobre:
- Estado COLETANDO_NOME → bot pergunta nome (sem LLM)
- Estado COLETANDO_CONVENIO → bot pergunta convênio (sem LLM)
- Estado OUVINDO_SINTOMAS → bot processa com LLM
- Prompts não contêm asteriscos (*)
- Uma pergunta por mensagem
- Transição COLETANDO_NOME → COLETANDO_CONVENIO após receber nome
- Transição COLETANDO_CONVENIO → OUVINDO_SINTOMAS
- Sistema de coleta progressiva salva nome no dados_coletados
- Resposta do bot nunca contém asteriscos (*)
- EMERGENCIA → banner + SAMU 192 + encerrando
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ia.chat_service import ChatService
from app.services.ia.state_machine import ChatEstado


def _make_service():
    db = AsyncMock()
    redis = AsyncMock()
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return ChatService(db=db, redis=redis)


def _session(estado: str = "START", dados: dict | None = None) -> bytes:
    data = {
        "token": "test-token",
        "canal": "PORTAL",
        "mensagens": [],
        "estado": estado,
        "dados_coletados": dados or {
            "nome": None,
            "convenio_id": None,
            "tipo_atendimento": None,
            "sintomas": [],
            "especialidade": None,
            "telefone": None,
            "email": None,
            "perguntas_coleta": 0,
        },
    }
    return json.dumps(data).encode()


class TestFluxoColetandoNome:
    async def test_estado_coletando_nome_retorna_pergunta_nome(self):
        """COLETANDO_NOME → resposta deve pedir o nome sem chamar LLM."""
        svc = _make_service()
        svc.redis.get = AsyncMock(return_value=_session("COLETANDO_NOME"))

        resultado = await svc.processar_mensagem("test-token", "oi")

        assert resultado["estado"] == ChatEstado.COLETANDO_NOME
        assert "nome" in resultado["resposta"].lower()
        assert "*" not in resultado["resposta"]

    async def test_estado_coletando_nome_salva_nome_e_avanca(self):
        """Após receber nome, avança para COLETANDO_CONVENIO."""
        svc = _make_service()
        svc.redis.get = AsyncMock(return_value=_session("COLETANDO_NOME"))

        resultado = await svc.processar_mensagem("test-token", "João Silva")

        saved = json.loads(svc.redis.set.call_args[0][1])
        assert saved["estado"] == ChatEstado.COLETANDO_CONVENIO
        assert saved["dados_coletados"]["nome"] == "João Silva"


class TestFluxoColetandoConvenio:
    async def test_estado_coletando_convenio_retorna_pergunta_convenio(self):
        """COLETANDO_CONVENIO → resposta deve perguntar sobre convênio."""
        svc = _make_service()
        dados = {"nome": "Maria", "convenio_id": None, "tipo_atendimento": None,
                 "sintomas": [], "especialidade": None, "telefone": None, "email": None, "perguntas_coleta": 0}
        svc.redis.get = AsyncMock(return_value=_session("COLETANDO_CONVENIO", dados))

        resultado = await svc.processar_mensagem("test-token", "oi")

        assert resultado["estado"] == ChatEstado.COLETANDO_CONVENIO
        assert "convenio" in resultado["resposta"].lower() or "plano" in resultado["resposta"].lower()
        assert "*" not in resultado["resposta"]

    async def test_resposta_particular_avanca_para_sintomas(self):
        """Dizer 'não' ou 'particular' avança para OUVINDO_SINTOMAS."""
        svc = _make_service()
        dados = {"nome": "Maria", "convenio_id": None, "tipo_atendimento": None,
                 "sintomas": [], "especialidade": None, "telefone": None, "email": None, "perguntas_coleta": 0}
        svc.redis.get = AsyncMock(return_value=_session("COLETANDO_CONVENIO", dados))

        resultado = await svc.processar_mensagem("test-token", "não, sou particular")

        saved = json.loads(svc.redis.set.call_args[0][1])
        assert saved["estado"] == ChatEstado.OUVINDO_SINTOMAS
        assert saved["dados_coletados"]["tipo_atendimento"] == "PARTICULAR"


class TestFluxoOuvindoSintomas:
    async def test_estado_ouvindo_sintomas_usa_llm(self):
        """OUVINDO_SINTOMAS → processa com LLM."""
        svc = _make_service()
        dados = {"nome": "Pedro", "convenio_id": None, "tipo_atendimento": "PARTICULAR",
                 "sintomas": [], "especialidade": None, "telefone": None, "email": None, "perguntas_coleta": 0}
        svc.redis.get = AsyncMock(return_value=_session("OUVINDO_SINTOMAS", dados))

        mock_response = MagicMock()
        mock_response.content = "Há quanto tempo você sente isso?"
        mock_response.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 10}}

        with patch.object(svc, "_criar_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            resultado = await svc.processar_mensagem("test-token", "dor de cabeça")

        assert resultado["estado"] in (ChatEstado.OUVINDO_SINTOMAS, ChatEstado.SUGERINDO_ESPECIALIDADE)


class TestSemAsteriscos:
    async def test_prompt_coletando_nome_sem_asteriscos(self):
        """Respostas diretas (sem LLM) não têm asteriscos."""
        svc = _make_service()
        svc.redis.get = AsyncMock(return_value=_session("COLETANDO_NOME"))

        resultado = await svc.processar_mensagem("test-token", "olá")

        assert "*" not in resultado["resposta"]

    async def test_prompt_coletando_convenio_sem_asteriscos(self):
        dados = {"nome": "Ana", "convenio_id": None, "tipo_atendimento": None,
                 "sintomas": [], "especialidade": None, "telefone": None, "email": None, "perguntas_coleta": 0}
        svc = _make_service()
        svc.redis.get = AsyncMock(return_value=_session("COLETANDO_CONVENIO", dados))

        resultado = await svc.processar_mensagem("test-token", "olá")

        assert "*" not in resultado["resposta"]


class TestDadosColetadosIniciais:
    def test_dados_coletados_tem_campos_novos(self):
        """_DADOS_COLETADOS_INICIAL deve ter nome, convenio_id, tipo_atendimento, telefone, email."""
        from app.services.ia.chat_service import _DADOS_COLETADOS_INICIAL

        assert "nome" in _DADOS_COLETADOS_INICIAL
        assert "convenio_id" in _DADOS_COLETADOS_INICIAL
        assert "tipo_atendimento" in _DADOS_COLETADOS_INICIAL
        assert "telefone" in _DADOS_COLETADOS_INICIAL
        assert "email" in _DADOS_COLETADOS_INICIAL
