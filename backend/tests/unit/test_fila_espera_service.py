"""Testes — Fila de espera (T90, T91): entrada, listagem, oferta de horário e resposta do cliente.

Usam o banco real (db_session faz rollback ao final).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.atendimento import Atendimento, AtendimentoCanal, AtendimentoStatus
from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.models.slot import SlotStatus
from app.services.fila_espera_service import (
    MAX_TENTATIVAS,
    FilaEsperaService,
    listar_fila,
    processar_fila,
    remover_da_fila,
    responder_oferta_fila,
)
from app.services.mensageria import obter_pendencia
from tests.fabrica import (
    nas_unidades_do_teste,
    Caixa,
    RedisFalso,
    criar_cliente,
    criar_convenio,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)


async def _cenario(db):
    est = await criar_estabelecimento(db)
    esp = await criar_especialidade(db, est)
    prof = await criar_profissional(db, est, esp)
    return est, esp, prof


async def _entrar(db, est, esp, nome="Maria Souza", **campos):
    cliente = await criar_cliente(db, est, nome=nome, **campos)
    entrada = await FilaEsperaService(db).entrar_sem_duplicar(cliente.id, est.id, esp.id, None)
    return cliente, entrada


# ── Entrada e listagem (T90) ────────────────────────────────────────────────

async def test_entrar_duas_vezes_na_mesma_especialidade_reaproveita_a_entrada(db_session):
    est, esp, _ = await _cenario(db_session)
    cliente, primeira = await _entrar(db_session, est, esp)

    segunda = await FilaEsperaService(db_session).entrar_sem_duplicar(cliente.id, est.id, esp.id, None)

    assert segunda.id == primeira.id


async def test_listar_fila_traz_dados_do_cliente_em_ordem_de_chegada(db_session):
    est, esp, _ = await _cenario(db_session)
    await _entrar(db_session, est, esp, nome="Primeira Pessoa")
    await _entrar(db_session, est, esp, nome="Segunda Pessoa")

    fila = await listar_fila(db_session, est.id)

    assert [i["cliente_nome"] for i in fila] == ["Primeira Pessoa", "Segunda Pessoa"]
    assert [i["posicao"] for i in fila] == [1, 2]
    assert fila[0]["especialidade_nome"] == "Cardiologia"
    assert fila[0]["status"] == "AGUARDANDO"
    assert "cliente_cpf" not in fila[0]
    assert "***" in fila[0]["cliente_cpf_mascarado"]


async def test_listar_fila_nao_mostra_outra_unidade(db_session):
    est, esp, _ = await _cenario(db_session)
    outra, outra_esp, _ = await _cenario(db_session)
    await _entrar(db_session, outra, outra_esp)

    assert await listar_fila(db_session, est.id) == []


async def test_remover_da_fila_cancela_e_respeita_a_unidade(db_session):
    est, esp, _ = await _cenario(db_session)
    outra = await criar_estabelecimento(db_session)
    _, entrada = await _entrar(db_session, est, esp)

    assert await remover_da_fila(db_session, entrada.id, outra.id) is False
    assert await remover_da_fila(db_session, entrada.id, est.id) is True
    assert entrada.status == FilaEsperaStatus.CANCELADO
    assert await listar_fila(db_session, est.id) == []


# ── Oferta de horário (T91) ─────────────────────────────────────────────────

async def test_slot_livre_e_oferecido_ao_primeiro_da_fila_e_fica_reservado(db_session):
    est, esp, prof = await _cenario(db_session)
    primeira, entrada = await _entrar(db_session, est, esp, nome="Primeira Pessoa")
    _, segunda = await _entrar(db_session, est, esp, nome="Segunda Pessoa")
    slot = await criar_slot(db_session, est, prof)
    redis, caixa = RedisFalso(), Caixa()

    resultado = await nas_unidades_do_teste(processar_fila, db_session, redis, enviar=caixa)

    assert resultado["notificados"] == 1
    assert entrada.status == FilaEsperaStatus.NOTIFICADO
    assert entrada.slot_ofertado_id == slot.id
    assert entrada.notificado_em is not None
    assert segunda.status == FilaEsperaStatus.AGUARDANDO
    assert slot.status == SlotStatus.RESERVADO
    assert len(caixa.enviadas) == 1
    assert "Dra. Ana Lima" in caixa.textos[0]
    assert "1" in caixa.textos[0]
    assert await obter_pendencia(redis, primeira.telefone) == {"tipo": "fila", "fila_id": entrada.id}


async def test_dois_slots_atendem_os_dois_primeiros_da_fila(db_session):
    est, esp, prof = await _cenario(db_session)
    _, a = await _entrar(db_session, est, esp, nome="A")
    _, b = await _entrar(db_session, est, esp, nome="B")
    s1 = await criar_slot(db_session, est, prof, dias=2)
    s2 = await criar_slot(db_session, est, prof, dias=3)

    await nas_unidades_do_teste(processar_fila, db_session, RedisFalso(), enviar=Caixa())

    assert {a.slot_ofertado_id, b.slot_ofertado_id} == {s1.id, s2.id}


async def test_slot_de_outra_especialidade_nao_e_oferecido(db_session):
    est, esp, _ = await _cenario(db_session)
    outra_esp = await criar_especialidade(db_session, est, nome="Ortopedia")
    ortopedista = await criar_profissional(db_session, est, outra_esp, nome="Dr. Beto")
    _, entrada = await _entrar(db_session, est, esp)
    await criar_slot(db_session, est, ortopedista)
    caixa = Caixa()

    await nas_unidades_do_teste(processar_fila, db_session, RedisFalso(), enviar=caixa)

    assert entrada.status == FilaEsperaStatus.AGUARDANDO
    assert caixa.enviadas == []


async def test_convenio_de_outra_unidade_nao_recebe_oferta(db_session):
    est, esp, prof = await _cenario(db_session)
    outra = await criar_estabelecimento(db_session)
    convenio_de_fora = await criar_convenio(db_session, outra)
    cliente = await criar_cliente(db_session, est)
    entrada = await FilaEsperaService(db_session).entrar_sem_duplicar(
        cliente.id, est.id, esp.id, convenio_de_fora.id
    )
    await criar_slot(db_session, est, prof)

    await nas_unidades_do_teste(processar_fila, db_session, RedisFalso(), enviar=Caixa())

    assert entrada.status == FilaEsperaStatus.AGUARDANDO


async def test_falha_no_envio_nao_reserva_o_slot(db_session):
    est, esp, prof = await _cenario(db_session)
    _, entrada = await _entrar(db_session, est, esp)
    slot = await criar_slot(db_session, est, prof)

    await nas_unidades_do_teste(processar_fila, db_session, RedisFalso(), enviar=Caixa(sucesso=False))

    assert entrada.status == FilaEsperaStatus.AGUARDANDO
    assert slot.status == SlotStatus.DISPONIVEL


async def test_cliente_sem_telefone_e_pulado_e_o_proximo_recebe(db_session):
    est, esp, prof = await _cenario(db_session)
    _, sem_fone = await _entrar(db_session, est, esp, nome="Sem Fone", telefone=None)
    _, com_fone = await _entrar(db_session, est, esp, nome="Com Fone")
    await criar_slot(db_session, est, prof)

    await nas_unidades_do_teste(processar_fila, db_session, RedisFalso(), enviar=Caixa())

    assert sem_fone.status == FilaEsperaStatus.AGUARDANDO
    assert com_fone.status == FilaEsperaStatus.NOTIFICADO


async def test_sem_resposta_em_30_min_libera_o_slot_e_oferece_ao_proximo(db_session):
    est, esp, prof = await _cenario(db_session)
    _, primeira = await _entrar(db_session, est, esp, nome="Primeira")
    _, segunda = await _entrar(db_session, est, esp, nome="Segunda")
    slot = await criar_slot(db_session, est, prof)
    redis, caixa = RedisFalso(), Caixa()
    inicio = datetime.now(timezone.utc)
    await nas_unidades_do_teste(processar_fila, db_session, redis, agora_utc=inicio, enviar=caixa)

    await nas_unidades_do_teste(processar_fila, db_session, redis, agora_utc=inicio + timedelta(minutes=29), enviar=caixa)
    assert primeira.status == FilaEsperaStatus.NOTIFICADO

    resultado = await nas_unidades_do_teste(processar_fila, db_session, redis, agora_utc=inicio + timedelta(minutes=31), enviar=caixa)

    assert resultado["expirados"] == 1
    assert primeira.status == FilaEsperaStatus.AGUARDANDO
    assert primeira.tentativas == 1
    assert segunda.status == FilaEsperaStatus.NOTIFICADO
    assert segunda.slot_ofertado_id == slot.id
    assert slot.status == SlotStatus.RESERVADO


async def test_quem_nao_responde_repetidas_vezes_sai_da_fila(db_session):
    est, esp, prof = await _cenario(db_session)
    _, entrada = await _entrar(db_session, est, esp)
    redis, caixa = RedisFalso(), Caixa()
    agora = datetime.now(timezone.utc)

    for rodada in range(MAX_TENTATIVAS):
        await criar_slot(db_session, est, prof, dias=2 + rodada)
        await nas_unidades_do_teste(processar_fila, db_session, redis, agora_utc=agora, enviar=caixa)
        assert entrada.status == FilaEsperaStatus.NOTIFICADO
        agora += timedelta(minutes=31)
        await nas_unidades_do_teste(processar_fila, db_session, redis, agora_utc=agora, enviar=Caixa(sucesso=False))

    assert entrada.status == FilaEsperaStatus.CANCELADO


# ── Resposta do cliente ─────────────────────────────────────────────────────

async def _oferta(db):
    est, esp, prof = await _cenario(db)
    cliente, entrada = await _entrar(db, est, esp)
    slot = await criar_slot(db, est, prof)
    await nas_unidades_do_teste(processar_fila, db, RedisFalso(), enviar=Caixa())
    return est, cliente, entrada, slot


async def test_resposta_1_agenda_no_slot_reservado(db_session):
    est, cliente, entrada, slot = await _oferta(db_session)

    resposta, concluido = await responder_oferta_fila(db_session, entrada.id, " 1 ")

    atendimento = (
        await db_session.execute(select(Atendimento).where(Atendimento.slot_id == slot.id))
    ).scalar_one()
    assert concluido is True
    assert "confirmad" in resposta.lower()
    assert atendimento.cliente_id == cliente.id
    assert atendimento.status == AtendimentoStatus.AGENDADA
    assert atendimento.canal_origem == AtendimentoCanal.WHATSAPP
    assert atendimento.estabelecimento_id == est.id
    assert slot.status == SlotStatus.AGENDADO
    assert entrada.status == FilaEsperaStatus.AGENDADO


async def test_resposta_2_libera_o_slot_e_mantem_na_fila(db_session):
    _, _, entrada, slot = await _oferta(db_session)

    resposta, concluido = await responder_oferta_fila(db_session, entrada.id, "2")

    assert concluido is True
    assert slot.status == SlotStatus.DISPONIVEL
    assert entrada.status == FilaEsperaStatus.AGUARDANDO
    assert entrada.slot_ofertado_id == slot.id  # o mesmo horário não volta para a mesma pessoa
    assert "lista" in resposta.lower()


async def test_resposta_0_sai_da_fila(db_session):
    _, _, entrada, slot = await _oferta(db_session)

    _, concluido = await responder_oferta_fila(db_session, entrada.id, "0")

    assert concluido is True
    assert slot.status == SlotStatus.DISPONIVEL
    assert entrada.status == FilaEsperaStatus.CANCELADO


async def test_resposta_que_nao_e_opcao_orienta_e_mantem_a_oferta(db_session):
    _, _, entrada, slot = await _oferta(db_session)

    resposta, concluido = await responder_oferta_fila(db_session, entrada.id, "pode ser amanhã?")

    assert concluido is False
    assert "1" in resposta and "0" in resposta
    assert entrada.status == FilaEsperaStatus.NOTIFICADO
    assert slot.status == SlotStatus.RESERVADO


async def test_resposta_depois_do_prazo_avisa_que_o_horario_nao_esta_mais_guardado(db_session):
    _, _, entrada, slot = await _oferta(db_session)
    await nas_unidades_do_teste(processar_fila, db_session, RedisFalso(), agora_utc=datetime.now(timezone.utc) + timedelta(minutes=40),
        enviar=Caixa(sucesso=False),
    )

    resposta, concluido = await responder_oferta_fila(db_session, entrada.id, "1")

    assert concluido is True
    assert "não está mais" in resposta
    total = (await db_session.execute(select(Atendimento).where(Atendimento.slot_id == slot.id))).all()
    assert total == []
