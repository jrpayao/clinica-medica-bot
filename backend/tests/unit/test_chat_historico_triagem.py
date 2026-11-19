"""Testes — Histórico enviado à IA na triagem (economia de tokens).

A IA só participa da etapa de sintomas. Nome, convênio e plano são coletados sem IA e não precisam
ir junto a cada chamada: só encarecem a conversa.
"""

from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.services.ia import chat_service as chat
from app.services.ia.chat_service import ChatService
from tests.fabrica import RedisFalso, criar_especialidade, criar_estabelecimento


class ModeloQueGuarda:
    """Faz o papel do LLM: guarda o que recebeu e pede mais detalhes (não encerra a triagem)."""

    def __init__(self) -> None:
        self.chamadas: list[list] = []

    async def ainvoke(self, mensagens):
        self.chamadas.append(list(mensagens))
        return SimpleNamespace(
            content="Entendi. Há quanto tempo você sente isso?",
            response_metadata={"token_usage": {"prompt_tokens": 100, "completion_tokens": 10}},
        )


async def _conversar(db, mensagens):
    est = await criar_estabelecimento(db)
    await criar_especialidade(db, est, nome="Cardiologia")
    modelo = ModeloQueGuarda()
    servico = ChatService(db, RedisFalso())
    token = await servico.criar_sessao(estabelecimento_id=est.id)
    with patch.object(ChatService, "_criar_llm", return_value=modelo):
        for mensagem in mensagens:
            await servico.processar_mensagem(token, mensagem)
    return modelo


def _textos(chamada) -> list[str]:
    return [m.content for m in chamada]


async def test_ia_nao_recebe_nome_nem_convenio(db_session):
    modelo = await _conversar(
        db_session, ["oi", "Maria Aparecida Souza", "particular", "Estou com palpitação"]
    )

    assert len(modelo.chamadas) == 1
    enviado = " ".join(_textos(modelo.chamadas[0]))
    assert "Maria Aparecida Souza" not in enviado
    respostas_do_paciente = [m.content for m in modelo.chamadas[0] if isinstance(m, HumanMessage)]
    assert respostas_do_paciente == ["Estou com palpitação"]          # "oi", nome e "particular" ficam de fora
    assert "Estou com palpitação" in enviado


async def test_ia_recebe_a_pergunta_que_abriu_a_triagem_e_o_relato(db_session):
    modelo = await _conversar(db_session, ["oi", "Maria Souza", "particular", "Estou com palpitação"])

    chamada = modelo.chamadas[0]
    assert isinstance(chamada[0], SystemMessage)
    assert isinstance(chamada[1], AIMessage) and "sentindo" in chamada[1].content   # a pergunta do bot
    assert isinstance(chamada[-1], HumanMessage) and chamada[-1].content == "Estou com palpitação"
    assert len(chamada) == 3


async def test_ia_recebe_toda_a_conversa_da_triagem_nas_mensagens_seguintes(db_session):
    modelo = await _conversar(
        db_session, ["oi", "Maria Souza", "particular", "Estou com palpitação", "Há uns três dias"]
    )

    segunda = _textos(modelo.chamadas[1])
    assert segunda[2:] == ["Estou com palpitação", "Entendi. Há quanto tempo você sente isso?", "Há uns três dias"]
    assert "Maria Souza" not in " ".join(segunda)


async def test_triagem_longa_manda_so_as_ultimas_mensagens(db_session):
    relatos = [f"Detalhe número {n}" for n in range(1, 16)]
    modelo = await _conversar(db_session, ["oi", "Maria Souza", "particular", *relatos])

    ultima = modelo.chamadas[-1]
    assert isinstance(ultima[0], SystemMessage)
    assert len(ultima) == 1 + chat.MAX_MENSAGENS_TRIAGEM + 1   # instruções + histórico limitado + mensagem atual
    assert ultima[-1].content == "Detalhe número 15"
    assert "Detalhe número 1" not in _textos(ultima)


async def test_sessao_antiga_sem_marcador_continua_funcionando(db_session):
    """Sessões abertas antes desta mudança não têm o marcador: vale o histórico limitado."""
    est = await criar_estabelecimento(db_session)
    await criar_especialidade(db_session, est, nome="Cardiologia")
    redis, modelo = RedisFalso(), ModeloQueGuarda()
    servico = ChatService(db_session, redis)
    token = await servico.criar_sessao(estabelecimento_id=est.id)
    with patch.object(ChatService, "_criar_llm", return_value=modelo):
        for mensagem in ["oi", "Maria Souza", "particular"]:
            await servico.processar_mensagem(token, mensagem)
        sessao = await servico._carregar_sessao(token)
        sessao.pop("inicio_triagem", None)
        await servico._salvar_sessao(token, sessao)
        await servico.processar_mensagem(token, "Estou com palpitação")

    assert len(modelo.chamadas) == 1
    assert modelo.chamadas[0][-1].content == "Estou com palpitação"
