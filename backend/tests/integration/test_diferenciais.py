"""Testes de integração — diferenciais do G15 de ponta a ponta (T104) e fluxo guiado completo (T85).

Banco real (rollback ao final), Redis em memória, WhatsApp e IA substituídos por dublês.
"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.atendimento import Atendimento, AtendimentoCanal, AtendimentoStatus, MotivoCancelamento
from app.models.atendimento_historico import AtendimentoStatusHistorico
from app.models.avaliacao import Avaliacao
from app.models.cliente import Cliente
from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.models.sessao_historico import SessaoHistorico
from app.models.slot import SlotStatus
from app.models.token_usage import TokenUsage
from app.services import mensageria
from app.services.avaliacao_service import solicitar_avaliacoes
from app.services.fila_espera_service import processar_fila
from app.services.ia.chat_service import RESPOSTA_ENTRAR_NA_FILA, ChatService
from app.services.ia.state_machine import ChatEstado
from app.services.reagendamento_service import cancelar_com_motivo
from app.services.whatsapp.evolution import EvolutionProvider
from app.services.whatsapp.uazapi import UazapiProvider
from app.services.whatsapp_respostas import tratar_resposta_pendente
from tests.fabrica import (
    nas_unidades_do_teste,
    Caixa,
    RedisFalso,
    cabecalho,
    cpf_valido,
    criar_atendimento,
    criar_cliente,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)


class ModeloFalso:
    """Faz o papel do LLM na etapa de sintomas: sempre recomenda a especialidade informada."""

    def __init__(self, especialidade: str) -> None:
        self.especialidade = especialidade

    async def ainvoke(self, _mensagens):
        return SimpleNamespace(
            content=f"Entendi. Recomendo uma consulta com {self.especialidade}.",
            response_metadata={"token_usage": {"prompt_tokens": 200, "completion_tokens": 30}},
        )


async def _unidade(db, com_slot=True):
    est = await criar_estabelecimento(db)
    esp = await criar_especialidade(db, est, nome="Cardiologia")
    prof = await criar_profissional(db, est, esp)
    slot = await criar_slot(db, est, prof) if com_slot else None
    return est, esp, prof, slot


async def _conversar(db, redis, est, mensagens: list[str], token: str | None = None):
    """Envia as mensagens em sequência e devolve (token, respostas)."""
    servico = ChatService(db, redis)
    token = token or await servico.criar_sessao(estabelecimento_id=est.id)
    respostas = []
    with patch.object(ChatService, "_criar_llm", return_value=ModeloFalso("Cardiologia")):
        for mensagem in mensagens:
            respostas.append(await servico.processar_mensagem(token, mensagem))
    return token, respostas


async def _agendar_pelo_chat(db, redis, est, slot, cpf, nome="Maria Souza", sintoma="Estou com dor de cabeça há três dias"):
    return await _conversar(
        db, redis, est,
        ["oi", nome, "particular", sintoma, f"confirmar:{slot.id}", cpf, "(11) 98888-7777", "maria@teste.com", "Sim"],
    )


# ── T85: fluxo guiado completo, do nome à confirmação ───────────────────────

async def test_fluxo_guiado_completo_do_nome_a_confirmacao(db_session):
    est, _, prof, slot = await _unidade(db_session)
    cpf = cpf_valido()

    _, respostas = await _agendar_pelo_chat(db_session, RedisFalso(), est, slot, cpf)

    estados = [r["estado"] for r in respostas]
    assert estados == [
        ChatEstado.COLETANDO_NOME, ChatEstado.COLETANDO_CONVENIO, ChatEstado.OUVINDO_SINTOMAS,
        ChatEstado.APRESENTANDO_SLOTS, ChatEstado.COLETANDO_CONTATO, ChatEstado.COLETANDO_CONTATO,
        ChatEstado.COLETANDO_CONTATO, ChatEstado.CONFIRMANDO, ChatEstado.FINALIZADO,
    ]
    assert respostas[3]["slots_sugeridos"][0]["id"] == slot.id
    assert "PROTO-" in respostas[-1]["resposta"]
    atendimento = (await db_session.execute(select(Atendimento).where(Atendimento.slot_id == slot.id))).scalar_one()
    cliente = (await db_session.execute(select(Cliente).where(Cliente.id == atendimento.cliente_id))).scalar_one()
    assert (cliente.cpf, cliente.nome) == (cpf, "Maria Souza")
    assert atendimento.profissional_id == prof.id
    assert atendimento.canal_origem == AtendimentoCanal.PORTAL
    assert slot.status == SlotStatus.AGENDADO


async def test_agendamento_pelo_chat_guarda_resumo_de_triagem_e_registra_uso_da_ia(db_session):
    est, _, _, slot = await _unidade(db_session)

    await _agendar_pelo_chat(db_session, RedisFalso(), est, slot, cpf_valido())

    atendimento = (await db_session.execute(select(Atendimento).where(Atendimento.slot_id == slot.id))).scalar_one()
    resumo = atendimento.triagem_resumo
    assert "dor de cabeça há três dias" in resumo["texto"]
    assert resumo["categorias"] == ["Dor de cabeça"]
    assert resumo["origem"] == "regra"          # a IA do resumo está desligada nos testes
    assert "uso" not in resumo
    usos = (
        await db_session.execute(select(TokenUsage).where(TokenUsage.estabelecimento_id == est.id))
    ).scalars().all()
    assert len(usos) == 1 and usos[0].total_tokens == 230   # a conversa de sintomas foi cobrada


# ── Cenário 1: paciente retorna e é reconhecido ─────────────────────────────

async def test_paciente_que_retorna_e_reconhecido_e_o_profissional_ve_a_triagem_anterior(db_session):
    est, _, prof, primeiro_slot = await _unidade(db_session)
    segundo_slot = await criar_slot(db_session, est, prof, dias=5)
    cpf, redis = cpf_valido(), RedisFalso()
    await _agendar_pelo_chat(db_session, redis, est, primeiro_slot, cpf)

    _, respostas = await _agendar_pelo_chat(
        db_session, redis, est, segundo_slot, cpf, sintoma="Agora estou com tosse seca"
    )

    assert "Encontrei o seu cadastro, Maria" in respostas[5]["resposta"]
    historicos = (await db_session.execute(select(SessaoHistorico))).scalars().all()
    assert len([h for h in historicos if h.especialidade_sugerida == "Cardiologia"]) >= 2
    retorno = (
        await db_session.execute(select(Atendimento).where(Atendimento.slot_id == segundo_slot.id))
    ).scalar_one()
    anteriores = retorno.triagem_resumo["historico"]
    assert len(anteriores) == 1
    assert "dor de cabeça" in anteriores[0]["resumo"]
    clientes = (await db_session.execute(select(Cliente).where(Cliente.cpf == cpf))).scalars().all()
    assert len(clientes) == 1


# ── Cenário 2: sem horário → fila → WhatsApp → agenda ───────────────────────

async def test_sem_horario_o_paciente_entra_na_fila_e_agenda_pelo_whatsapp_quando_abre_vaga(db_session):
    est, esp, prof, _ = await _unidade(db_session, com_slot=False)
    redis, cpf = RedisFalso(), cpf_valido()

    _, respostas = await _conversar(
        db_session, redis, est,
        ["oi", "João Pereira", "particular", "Sinto palpitação quando subo escada"],
    )
    convite = respostas[-1]
    assert convite["estado"] == ChatEstado.OFERECENDO_FILA
    assert RESPOSTA_ENTRAR_NA_FILA in convite["quick_replies"]
    assert "slots_sugeridos" not in convite

    token = (await _conversar(db_session, redis, est, []))[0]  # nova sessão não interfere
    assert token

    sessao, respostas = await _conversar(
        db_session, redis, est,
        ["oi", "João Pereira", "particular", "Sinto palpitação quando subo escada",
         RESPOSTA_ENTRAR_NA_FILA, cpf, "telefone errado", "(11) 97777-6666"],
    )
    assert "CPF" in respostas[4]["resposta"]
    assert respostas[6]["estado"] == ChatEstado.COLETANDO_CONTATO      # número inválido: pergunta de novo
    assert respostas[7]["estado"] == ChatEstado.FINALIZADO
    assert "lista de espera de Cardiologia" in respostas[7]["resposta"]
    entrada = (
        await db_session.execute(select(FilaEspera).where(FilaEspera.estabelecimento_id == est.id))
    ).scalar_one()
    assert (entrada.status, entrada.especialidade_id) == (FilaEsperaStatus.AGUARDANDO, esp.id)

    vaga = await criar_slot(db_session, est, prof)
    whatsapp = Caixa()
    await nas_unidades_do_teste(processar_fila, db_session, redis, enviar=whatsapp)
    assert "Abriu um horário" in whatsapp.textos[0]

    # o WhatsApp entrega o número sem o nono dígito: a resposta precisa ser reconhecida mesmo assim
    resposta = await tratar_resposta_pendente(db_session, redis, "551177776666", "1")

    assert "confirmado" in resposta.lower()
    atendimento = (await db_session.execute(select(Atendimento).where(Atendimento.slot_id == vaga.id))).scalar_one()
    assert atendimento.cliente_id == entrada.cliente_id
    assert entrada.status == FilaEsperaStatus.AGENDADO
    assert await tratar_resposta_pendente(db_session, redis, "551177776666", "1") is None


async def test_recusar_a_lista_de_espera_encerra_sem_cadastrar_ninguem(db_session):
    est, _, _, _ = await _unidade(db_session, com_slot=False)

    _, respostas = await _conversar(
        db_session, RedisFalso(), est, ["oi", "João Pereira", "particular", "Sinto palpitação", "Não, obrigado"]
    )

    assert respostas[-1]["estado"] == ChatEstado.FINALIZADO
    assert (await db_session.execute(select(FilaEspera).where(FilaEspera.estabelecimento_id == est.id))).first() is None


# ── Cenário 3: profissional cancela → cliente remarca pelo WhatsApp ─────────

async def test_cancelamento_pelo_profissional_e_remarcado_pelo_whatsapp(db_session, async_client):
    est, _, prof, slot = await _unidade(db_session)
    cliente = await criar_cliente(db_session, est, telefone="11955554444")
    atendimento = await criar_atendimento(db_session, slot, cliente, prof)
    novo_slot = await criar_slot(db_session, est, prof, dias=4)
    redis, whatsapp = RedisFalso(), AsyncMock(return_value=True)

    with (
        patch("app.api.v1.endpoints.agenda.get_redis_client", return_value=redis),
        patch.object(EvolutionProvider, "enviar_mensagem", whatsapp),
    ):
        resposta = await async_client.patch(
            f"/v1/agenda/atendimentos/{atendimento.id}/cancelar",
            json={"motivo": "Profissional em cirurgia de urgência"},
            headers=cabecalho(est, role="MEDICO", profissional_id=prof.id),
        )

    assert resposta.status_code == 200
    assert resposta.json()["motivo_cancelamento"] == "MEDICO"
    assert slot.status == SlotStatus.BLOQUEADO
    numero, texto = whatsapp.await_args.args
    assert numero == "5511955554444" and "1 - " in texto

    confirmacao = await tratar_resposta_pendente(db_session, redis, "5511955554444", "1")

    assert "Remarcação confirmada" in confirmacao
    remarcado = (
        await db_session.execute(select(Atendimento).where(Atendimento.slot_id == novo_slot.id))
    ).scalar_one()
    assert remarcado.cliente_id == cliente.id


async def test_recepcao_cancelando_a_pedido_do_paciente_nao_envia_oferta(db_session, async_client):
    est, _, prof, slot = await _unidade(db_session)
    cliente = await criar_cliente(db_session, est)
    atendimento = await criar_atendimento(db_session, slot, cliente, prof)
    await criar_slot(db_session, est, prof, dias=4)
    whatsapp = AsyncMock(return_value=True)

    with patch.object(EvolutionProvider, "enviar_mensagem", whatsapp):
        resposta = await async_client.patch(
            f"/v1/agenda/atendimentos/{atendimento.id}/cancelar",
            json={"motivo": "Paciente ligou desmarcando", "origem": "PACIENTE"},
            headers=cabecalho(est, role="RECEPCIONISTA"),
        )

    assert resposta.status_code == 200
    assert atendimento.motivo_cancelamento == MotivoCancelamento.PACIENTE
    whatsapp.assert_not_awaited()
    assert slot.status == SlotStatus.DISPONIVEL


# ── Cenários 4 e 5: avaliação 24h depois → NPS e relatórios no painel ───────

async def test_avaliacao_respondida_no_whatsapp_aparece_no_nps_e_nos_relatorios_do_gestor(db_session, async_client):
    est, _, prof, _ = await _unidade(db_session, com_slot=False)
    cliente = await criar_cliente(db_session, est, telefone="11944443333")
    slot = await criar_slot(db_session, est, prof, data=date.today() - timedelta(days=1))
    atendimento = await criar_atendimento(db_session, slot, cliente, prof, status=AtendimentoStatus.REALIZADA)
    agora = datetime.now(timezone.utc)
    db_session.add(
        AtendimentoStatusHistorico(
            atendimento_id=atendimento.id, status_novo=AtendimentoStatus.REALIZADA,
            created_at=agora - timedelta(hours=25),
        )
    )
    await db_session.flush()
    redis, whatsapp = RedisFalso(), Caixa()

    await nas_unidades_do_teste(solicitar_avaliacoes, db_session, redis, agora_utc=agora, enviar=whatsapp)
    assert "nota de 1 a 5" in whatsapp.textos[0]
    pedido_de_comentario = await tratar_resposta_pendente(db_session, redis, cliente.telefone, "5")
    agradecimento = await tratar_resposta_pendente(db_session, redis, cliente.telefone, "Fui muito bem atendido")

    assert "pular" in pedido_de_comentario
    assert "Obrigado" in agradecimento
    avaliacao = (await db_session.execute(select(Avaliacao).where(Avaliacao.atendimento_id == atendimento.id))).scalar_one()
    assert (avaliacao.nota, avaliacao.comentario) == (5, "Fui muito bem atendido")

    gestor = cabecalho(est)
    nps = (await async_client.get("/v1/admin/avaliacoes/nps", headers=gestor)).json()
    lista = (await async_client.get("/v1/admin/avaliacoes", headers=gestor)).json()
    periodo = {"inicio": str(date.today() - timedelta(days=7)), "fim": str(date.today())}
    ocupacao = (await async_client.get("/v1/relatorios/ocupacao", params=periodo, headers=gestor)).json()
    comparecimento = (await async_client.get("/v1/relatorios/confirmacao", params=periodo, headers=gestor)).json()

    assert nps["geral"] == {"total": 1, "promotores": 1, "neutros": 0, "detratores": 0, "nps": 100, "media": 5.0}
    assert nps["profissionais"][0]["profissional_nome"] == prof.nome
    assert lista[0]["comentario"] == "Fui muito bem atendido"
    assert ocupacao["geral"] == {"total_slots": 1, "ocupados": 1, "taxa": 100.0}
    assert ocupacao["inicio"] == periodo["inicio"]
    assert comparecimento["taxa_comparecimento"] == 100.0


@pytest.mark.parametrize(
    ("role", "caminho", "status"),
    [
        ("RECEPCIONISTA", "/v1/relatorios/ocupacao", 403),
        ("MEDICO", "/v1/relatorios/sintomas", 403),
        ("RECEPCIONISTA", "/v1/admin/avaliacoes/nps", 403),
        ("MEDICO", "/v1/fila-espera", 403),
        ("MEDICO", "/v1/reagendamentos/pendencias", 403),
        ("RECEPCIONISTA", "/v1/fila-espera", 200),
        ("RECEPCIONISTA", "/v1/reagendamentos/pendencias", 200),
        ("ADMIN_ESTABELECIMENTO", "/v1/relatorios/custo-por-agendamento", 200),
        ("ADMIN_ESTABELECIMENTO", "/v1/relatorios/fila-espera", 200),
        ("ADMIN_ESTABELECIMENTO", "/v1/admin/fila-espera", 200),
    ],
)
async def test_perfis_que_acessam_relatorios_e_lista_de_espera(db_session, async_client, role, caminho, status):
    est = await criar_estabelecimento(db_session)
    extras = {"profissional_id": 1} if role == "MEDICO" else {}

    resposta = await async_client.get(caminho, headers=cabecalho(est, role=role, **extras))

    assert resposta.status_code == status


async def test_relatorio_recusa_periodo_invertido(db_session, async_client):
    est = await criar_estabelecimento(db_session)

    resposta = await async_client.get(
        "/v1/relatorios/ocupacao", params={"inicio": "2026-02-10", "fim": "2026-02-01"}, headers=cabecalho(est)
    )

    assert resposta.status_code == 422


async def test_recepcao_coloca_e_tira_cliente_da_lista_de_espera_pela_api(db_session, async_client):
    est, esp, _, _ = await _unidade(db_session, com_slot=False)
    cliente = await criar_cliente(db_session, est)
    de_fora = await criar_cliente(db_session, await criar_estabelecimento(db_session))
    recepcao = cabecalho(est, role="RECEPCIONISTA")

    recusado = await async_client.post("/v1/fila-espera", json={"cliente_id": de_fora.id}, headers=recepcao)
    criado = await async_client.post(
        "/v1/fila-espera", json={"cliente_id": cliente.id, "especialidade_id": esp.id}, headers=recepcao
    )
    fila = (await async_client.get("/v1/fila-espera", headers=recepcao)).json()
    removido = await async_client.delete(f"/v1/fila-espera/{criado.json()['id']}", headers=recepcao)
    depois = (await async_client.get("/v1/fila-espera", headers=recepcao)).json()

    assert recusado.status_code == 404          # cliente de outra unidade
    assert criado.status_code == 201
    assert [i["cliente_nome"] for i in fila] == [cliente.nome]
    assert removido.status_code == 204
    assert depois == []


# ── Cenário 6: troca de provedor de WhatsApp sem tocar na regra de negócio ──

@pytest.mark.parametrize(("nome", "classe"), [("evolution", EvolutionProvider), ("uazapi", UazapiProvider)])
async def test_troca_de_provedor_de_whatsapp_nao_muda_o_fluxo(db_session, nome, classe):
    est, _, prof, slot = await _unidade(db_session)
    cliente = await criar_cliente(db_session, est, telefone="11933332222")
    atendimento = await criar_atendimento(db_session, slot, cliente, prof)
    await criar_slot(db_session, est, prof, dias=4)
    envio = AsyncMock(return_value=True)

    with (
        patch.object(mensageria.settings, "whatsapp_provider", nome),
        patch.object(classe, "enviar_mensagem", envio),
    ):
        await cancelar_com_motivo(
            db_session, RedisFalso(), atendimento_id=atendimento.id, texto_motivo="Agenda fechada",
            origem=MotivoCancelamento.ESTABELECIMENTO, estabelecimento_id=est.id, avisar=Caixa(),
        )

    assert envio.await_args.args[0] == "5511933332222"
    assert "Temos estes horários" in envio.await_args.args[1]


async def test_webhook_entrega_a_resposta_ao_fluxo_pendente_e_responde_pelo_provedor(db_session, async_client):
    est, esp, prof, slot = await _unidade(db_session)
    cliente = await criar_cliente(db_session, est, telefone="11922221111")
    from app.services.fila_espera_service import FilaEsperaService

    await FilaEsperaService(db_session).entrar_sem_duplicar(cliente.id, est.id, esp.id, None)
    redis, envio = RedisFalso(), AsyncMock(return_value=True)
    await nas_unidades_do_teste(processar_fila, db_session, redis, enviar=Caixa())
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "5511922221111@s.whatsapp.net", "fromMe": False, "id": "abc"},
            "message": {"conversation": "1"},
        },
    }

    with (
        patch("app.api.v1.endpoints.chat.get_redis_client", return_value=redis),
        patch.object(EvolutionProvider, "enviar_mensagem", envio),
    ):
        resposta = await async_client.post("/v1/chat/webhook/whatsapp", json=payload)

    assert resposta.json() == {"status": "processado"}
    assert "Agendamento confirmado" in envio.await_args.args[1]
    assert slot.status == SlotStatus.AGENDADO


async def test_emergencia_em_resposta_pendente_orienta_samu_e_nao_registra_nada(db_session):
    est, _, prof, _ = await _unidade(db_session, com_slot=False)
    cliente = await criar_cliente(db_session, est, telefone="11911110000")
    redis = RedisFalso()
    await mensageria.registrar_pendencia(redis, cliente.telefone, {"tipo": "avaliacao", "atendimento_id": 1}, ttl=60)

    resposta = await tratar_resposta_pendente(db_session, redis, cliente.telefone, "estou com dor no peito")

    assert "192" in resposta
    assert await mensageria.obter_pendencia(redis, cliente.telefone) is not None


async def test_profissional_ve_o_resumo_de_triagem_no_painel_do_dia_e_a_recepcao_nao(db_session, async_client):
    est, _, prof, _ = await _unidade(db_session, com_slot=False)
    hoje = date.today()
    slot = await criar_slot(db_session, est, prof, data=hoje)
    cliente = await criar_cliente(db_session, est)
    await criar_atendimento(
        db_session, slot, cliente, prof,
        triagem_resumo={"texto": "Paciente relata tosse seca.", "origem": "ia", "categorias": ["Tosse"], "historico": []},
    )
    periodo = {"data": str(hoje)}

    medico = await async_client.get(
        "/v1/profissional/painel", params=periodo, headers=cabecalho(est, role="MEDICO", profissional_id=prof.id)
    )
    recepcao = await async_client.get(
        "/v1/recepcao/painel", params=periodo, headers=cabecalho(est, role="RECEPCIONISTA")
    )

    assert medico.json()["atendimentos"][0]["triagem"]["texto"] == "Paciente relata tosse seca."
    assert "triagem" not in recepcao.json()["atendimentos"][0]
