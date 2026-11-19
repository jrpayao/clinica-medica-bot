"""Testes de integração — Telemedicina (G29) de ponta a ponta: chat → link → sala de espera → atendimento → PDF."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.slot import SlotStatus
from app.models.teleconsulta import Modalidade, RegistroClinico, Teleconsulta
from app.services import telemedicina_service as tele
from app.services.ia.chat_service import RESPOSTA_ONLINE, RESPOSTA_PRESENCIAL, ChatService
from app.services.ia.state_machine import ChatEstado
from app.services.whatsapp.evolution import EvolutionProvider
from tests.fabrica import (
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
    async def ainvoke(self, _mensagens):
        return SimpleNamespace(
            content="Recomendo uma consulta com Cardiologia.",
            response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
        )


async def _unidade(db, online=True, dias=3):
    est = await criar_estabelecimento(db)
    esp = await criar_especialidade(db, est, nome="Cardiologia")
    prof = await criar_profissional(db, est, esp)
    slot = await criar_slot(db, est, prof, dias=dias)
    slot.aceita_online = online
    await db.flush()
    return est, esp, prof, slot


async def _conversar(db, est, mensagens):
    servico = ChatService(db, RedisFalso())
    token = await servico.criar_sessao(estabelecimento_id=est.id)
    respostas = []
    with (
        patch.object(ChatService, "_criar_llm", return_value=ModeloFalso()),
        patch.object(EvolutionProvider, "enviar_mensagem", AsyncMock(return_value=True)) as whatsapp,
    ):
        for mensagem in mensagens:
            respostas.append(await servico.processar_mensagem(token, mensagem))
    return respostas, whatsapp


ATE_O_HORARIO = ["oi", "Maria Souza", "particular", "Sinto palpitação ao subir escada"]


# ── Chat ────────────────────────────────────────────────────────────────────

async def test_chat_oferece_online_e_o_agendamento_devolve_o_link_da_sala(db_session):
    est, _, _, slot = await _unidade(db_session)

    respostas, whatsapp = await _conversar(
        db_session, est,
        [*ATE_O_HORARIO, f"confirmar:{slot.id}", RESPOSTA_ONLINE, cpf_valido(), "(11) 98888-7777", "maria@teste.com", "Sim"],
    )

    assert respostas[3]["slots_sugeridos"][0]["aceita_online"] is True
    pergunta = respostas[4]
    assert pergunta["estado"] == ChatEstado.COLETANDO_CONTATO
    assert pergunta["quick_replies"] == [RESPOSTA_PRESENCIAL, RESPOSTA_ONLINE]
    assert "CPF" in respostas[5]["resposta"]
    assert "Modalidade:** Online" in respostas[8]["resposta"]

    atendimento = (await db_session.execute(select(Atendimento).where(Atendimento.slot_id == slot.id))).scalar_one()
    sala = (
        await db_session.execute(select(Teleconsulta).where(Teleconsulta.atendimento_id == atendimento.id))
    ).scalar_one()
    final = respostas[-1]
    assert atendimento.modalidade == Modalidade.ONLINE
    assert final["teleconsulta_link"].endswith(f"/teleconsulta/{sala.token_paciente}")
    assert final["teleconsulta_link"] in final["resposta"]
    assert sala.token_paciente in whatsapp.await_args.args[1]     # o link também vai por WhatsApp
    assert sala.link_enviado_em is not None


async def test_chat_presencial_em_horario_que_aceita_online_nao_cria_sala(db_session):
    est, _, _, slot = await _unidade(db_session)

    respostas, _ = await _conversar(
        db_session, est,
        [*ATE_O_HORARIO, f"confirmar:{slot.id}", "tanto faz", RESPOSTA_PRESENCIAL, cpf_valido(), "11988887777", "m@t.com", "Sim"],
    )

    assert "presencial ou online" in respostas[5]["resposta"]       # resposta ambígua: pergunta de novo
    atendimento = (await db_session.execute(select(Atendimento).where(Atendimento.slot_id == slot.id))).scalar_one()
    assert atendimento.modalidade == Modalidade.PRESENCIAL
    assert respostas[-1]["teleconsulta_link"] is None
    assert (await db_session.execute(select(Teleconsulta).where(Teleconsulta.atendimento_id == atendimento.id))).first() is None


async def test_chat_em_horario_so_presencial_nao_pergunta_a_modalidade(db_session):
    est, _, _, slot = await _unidade(db_session, online=False)

    respostas, _ = await _conversar(db_session, est, [*ATE_O_HORARIO, f"confirmar:{slot.id}"])

    assert respostas[3]["slots_sugeridos"][0]["aceita_online"] is False
    assert "CPF" in respostas[4]["resposta"]
    assert "quick_replies" not in respostas[4]


# ── Jornada completa pela API ───────────────────────────────────────────────

async def test_jornada_da_teleconsulta_pela_api(db_session, async_client):
    """Paciente aceita o termo e espera; profissional inicia, registra, emite a receita e conclui; paciente baixa o PDF."""
    est = await criar_estabelecimento(db_session, nome="Clínica Vida", timezone="America/Sao_Paulo")
    esp = await criar_especialidade(db_session, est)
    prof = await criar_profissional(db_session, est, esp)
    paciente = await criar_cliente(db_session, est, nome="Maria Souza")
    agora = tele.agora_local("America/Sao_Paulo")
    inicio = (agora + timedelta(minutes=10)).replace(second=0, microsecond=0)
    if inicio.date() != agora.date():
        pytest.skip("perto da meia-noite: o horário do teste cairia no dia seguinte")
    slot = await criar_slot(db_session, est, prof, data=inicio.date(), hora=inicio.time())
    slot.aceita_online = True
    atendimento = await criar_atendimento(db_session, slot, paciente, prof, modalidade=Modalidade.ONLINE)
    sala = await tele.criar_teleconsulta(db_session, atendimento)
    medico = cabecalho(est, role="MEDICO", profissional_id=prof.id)
    base_paciente = f"/v1/teleconsulta/{sala.token_paciente}"
    base_medico = f"/v1/profissional/atendimentos/{atendimento.id}"

    # paciente abre o link sem login
    pagina = (await async_client.get(base_paciente)).json()
    assert pagina["situacao"] == "AGUARDANDO_CONSENTIMENTO"
    assert pagina["termo"]["texto"]
    assert (await async_client.post(f"{base_paciente}/presenca")).status_code == 409

    espera = (await async_client.post(f"{base_paciente}/consentimento")).json()
    assert espera["situacao"] == "SALA_DE_ESPERA"
    assert espera["sala_url"] is None
    assert atendimento.status == AtendimentoStatus.PRESENTE

    # profissional vê o paciente na sala de espera e inicia
    tela = (await async_client.get(f"{base_medico}/sala", headers=medico)).json()
    assert tela["teleconsulta"]["paciente_na_sala"] is True
    assert tela["teleconsulta"]["sala_url"].startswith("https://meet.jit.si/")
    assert tela["acoes"] == ["EM_ATENDIMENTO"]
    cedo = await async_client.post(
        f"{base_medico}/documentos", headers=medico, json={"tipo": "ATESTADO", "conteudo": {"dias": 1}}
    )
    assert cedo.status_code == 409                                   # documento só com o atendimento iniciado

    iniciou = await async_client.patch(
        f"/v1/profissional/atendimentos/{atendimento.id}/status", headers=medico, json={"status_novo": "EM_ATENDIMENTO"}
    )
    assert iniciou.status_code == 200
    em_andamento = (await async_client.post(f"{base_paciente}/presenca")).json()
    assert em_andamento["situacao"] == "EM_ANDAMENTO"
    assert em_andamento["sala_url"].startswith("https://meet.jit.si/" + sala.sala)

    # registro e receita
    salvo = await async_client.put(
        f"{base_medico}/registro", headers=medico,
        json={"queixa": "Palpitação", "evolucao": "Sem alterações ao relato.", "conduta": "Solicitado retorno"},
    )
    assert salvo.status_code == 200
    invalida = await async_client.post(
        f"{base_medico}/documentos", headers=medico, json={"tipo": "RECEITA", "conteudo": {"itens": []}}
    )
    assert invalida.status_code == 422
    receita = await async_client.post(
        f"{base_medico}/documentos", headers=medico,
        json={"tipo": "RECEITA", "conteudo": {"itens": [{"medicamento": "Propranolol 40 mg", "posologia": "1 comprimido pela manhã"}]}},
    )
    assert receita.status_code == 201
    doc_id = receita.json()["id"]
    pdf_medico = await async_client.get(f"{base_medico}/documentos/{doc_id}.pdf", headers=medico)
    assert pdf_medico.headers["content-type"] == "application/pdf"
    assert pdf_medico.content.startswith(b"%PDF")

    # conclui; paciente vê o encerramento e baixa a receita
    await async_client.patch(
        f"/v1/profissional/atendimentos/{atendimento.id}/status", headers=medico, json={"status_novo": "REALIZADA"}
    )
    fim = (await async_client.get(base_paciente)).json()
    assert fim["situacao"] == "ENCERRADA"
    assert fim["sala_url"] is None
    assert [d["tipo"] for d in fim["documentos"]] == ["RECEITA"]
    pdf_paciente = await async_client.get(f"{base_paciente}/documentos/{doc_id}.pdf")
    assert pdf_paciente.status_code == 200 and pdf_paciente.content.startswith(b"%PDF")

    registro = (
        await db_session.execute(select(RegistroClinico).where(RegistroClinico.atendimento_id == atendimento.id))
    ).scalar_one()
    assert registro.conduta == "Solicitado retorno"


async def test_link_invalido_devolve_404(db_session, async_client):
    assert (await async_client.get("/v1/teleconsulta/nao-existe")).status_code == 404
    assert (await async_client.post("/v1/teleconsulta/nao-existe/consentimento")).status_code == 404
    assert (await async_client.get("/v1/teleconsulta/nao-existe/documentos/1.pdf")).status_code == 404


async def test_tela_de_atendimento_e_so_do_profissional_dono(db_session, async_client):
    est, _, prof, slot = await _unidade(db_session)
    outro = await criar_profissional(db_session, est, await criar_especialidade(db_session, est, nome="Ortopedia"), nome="Dr. Beto")
    paciente = await criar_cliente(db_session, est)
    atendimento = await criar_atendimento(db_session, slot, paciente, prof, modalidade=Modalidade.ONLINE)
    caminho = f"/v1/profissional/atendimentos/{atendimento.id}/sala"

    dono = await async_client.get(caminho, headers=cabecalho(est, role="MEDICO", profissional_id=prof.id))
    colega = await async_client.get(caminho, headers=cabecalho(est, role="MEDICO", profissional_id=outro.id))
    recepcao = await async_client.get(caminho, headers=cabecalho(est, role="RECEPCIONISTA"))
    gestor = await async_client.get(caminho, headers=cabecalho(est))

    assert dono.status_code == 200
    assert colega.status_code == 404
    assert (recepcao.status_code, gestor.status_code) == (403, 403)   # registro clínico é só do profissional


# ── Agenda: horários online ─────────────────────────────────────────────────

async def test_profissional_marca_os_proprios_horarios_como_online_pela_api(db_session, async_client):
    est, esp, prof, slot = await _unidade(db_session, online=False)
    colega = await criar_profissional(db_session, est, esp, nome="Dr. Beto")
    do_colega = await criar_slot(db_session, est, colega, data=slot.data)
    medico = cabecalho(est, role="MEDICO", profissional_id=prof.id)
    corpo = {"data": str(slot.data), "aceita_online": True, "profissional_id": colega.id}

    resposta = await async_client.patch("/v1/agenda/slots/online", headers=medico, json=corpo)
    dia = (await async_client.get(f"/v1/agenda/slots/dia/{slot.data}", headers=medico)).json()

    assert resposta.json() == {"alterados": 1}
    assert slot.aceita_online is True
    assert do_colega.aceita_online is False            # o pedido do médico vale só para a agenda dele
    assert dia[0]["aceita_online"] is True


async def test_recepcao_nao_define_horario_online_e_gestor_precisa_dizer_de_quem(db_session, async_client):
    est, _, prof, slot = await _unidade(db_session, online=False)
    corpo = {"data": str(slot.data), "aceita_online": True}

    recepcao = await async_client.patch("/v1/agenda/slots/online", headers=cabecalho(est, role="RECEPCIONISTA"), json=corpo)
    sem_alvo = await async_client.patch("/v1/agenda/slots/online", headers=cabecalho(est), json=corpo)
    gestor = await async_client.patch(
        "/v1/agenda/slots/online", headers=cabecalho(est), json={**corpo, "profissional_id": prof.id}
    )

    assert (recepcao.status_code, sem_alvo.status_code) == (403, 422)
    assert gestor.json() == {"alterados": 1}


async def test_recepcao_agenda_online_pela_api_e_a_fila_do_dia_mostra_a_modalidade(db_session, async_client):
    est, esp, prof, slot = await _unidade(db_session, dias=0)
    slot.data = date.today()
    await db_session.flush()
    paciente = await criar_cliente(db_session, est)
    recepcao = cabecalho(est, role="RECEPCIONISTA")

    criado = await async_client.post(
        "/v1/agenda/atendimentos", headers=recepcao,
        json={"slot_id": slot.id, "cliente_id": paciente.id, "profissional_id": prof.id,
              "especialidade_id": esp.id, "modalidade": "ONLINE", "canal_origem": "INTERNO"},
    )
    painel = (await async_client.get("/v1/recepcao/painel", params={"data": str(date.today())}, headers=recepcao)).json()

    assert criado.status_code == 201
    assert criado.json()["modalidade"] == "ONLINE"
    assert painel["atendimentos"][0]["modalidade"] == "ONLINE"
    assert slot.status == SlotStatus.AGENDADO
