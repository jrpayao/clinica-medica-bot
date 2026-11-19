"""Testes — Reagendamento após cancelamento pela unidade (T96, T97, T98)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.atendimento import Atendimento, AtendimentoCanal, AtendimentoStatus, MotivoCancelamento
from app.models.reagendamento import ReagendamentoOferta, ReagendamentoStatus
from app.models.slot import SlotStatus
from app.services.mensageria import obter_pendencia
from app.services.reagendamento_service import (
    cancelar_com_motivo,
    expirar_ofertas,
    listar_pendencias,
    resolver_pendencia,
    responder_reagendamento,
)
from tests.fabrica import (
    Caixa,
    RedisFalso,
    criar_atendimento,
    criar_cliente,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)


async def _agendado(db, slots_livres=3, **cliente):
    est = await criar_estabelecimento(db)
    esp = await criar_especialidade(db, est)
    prof = await criar_profissional(db, est, esp)
    paciente = await criar_cliente(db, est, **cliente)
    slot = await criar_slot(db, est, prof, dias=1)
    atendimento = await criar_atendimento(
        db, slot, paciente, prof, triagem_resumo={"texto": "Relata dor de cabeça.", "origem": "ia"}
    )
    livres = [await criar_slot(db, est, prof, dias=2 + i) for i in range(slots_livres)]
    return est, prof, paciente, slot, atendimento, livres


async def _oferta_de(db, atendimento) -> ReagendamentoOferta | None:
    return (
        await db.execute(
            select(ReagendamentoOferta).where(ReagendamentoOferta.atendimento_id == atendimento.id)
        )
    ).scalar_one_or_none()


async def _cancelar(db, atendimento, origem, redis=None, wa=None, aviso=None):
    return await cancelar_com_motivo(
        db,
        redis or RedisFalso(),
        atendimento_id=atendimento.id,
        texto_motivo="Profissional indisponível",
        origem=origem,
        estabelecimento_id=atendimento.estabelecimento_id,
        enviar=wa or Caixa(),
        avisar=aviso or Caixa(),
    )


# ── T96: motivo do cancelamento ─────────────────────────────────────────────

async def test_motivo_do_cancelamento_e_gravado(db_session):
    _, _, _, _, atendimento, _ = await _agendado(db_session)

    await _cancelar(db_session, atendimento, MotivoCancelamento.ESTABELECIMENTO)

    assert atendimento.status == AtendimentoStatus.CANCELADA
    assert atendimento.motivo_cancelamento == MotivoCancelamento.ESTABELECIMENTO


async def test_cancelamento_pelo_paciente_nao_oferece_reagendamento(db_session):
    _, _, _, slot, atendimento, _ = await _agendado(db_session)
    wa = Caixa()

    await _cancelar(db_session, atendimento, MotivoCancelamento.PACIENTE, wa=wa)

    assert wa.enviadas == []
    assert await _oferta_de(db_session, atendimento) is None
    assert slot.status == SlotStatus.DISPONIVEL


async def test_cancelamento_pelo_sistema_nao_oferece_reagendamento(db_session):
    _, _, _, _, atendimento, _ = await _agendado(db_session)
    wa = Caixa()

    await _cancelar(db_session, atendimento, MotivoCancelamento.SISTEMA, wa=wa)

    assert wa.enviadas == []


async def test_cancelamento_pelo_profissional_bloqueia_o_horario(db_session):
    """Se o profissional não pode atender, o horário não deve voltar para a agenda."""
    _, _, _, slot, atendimento, _ = await _agendado(db_session)

    await _cancelar(db_session, atendimento, MotivoCancelamento.MEDICO)

    assert slot.status == SlotStatus.BLOQUEADO
    assert slot.motivo_bloqueio


# ── T97: oferta de novos horários ───────────────────────────────────────────

async def test_cancelamento_pela_unidade_envia_tres_opcoes_numeradas(db_session):
    _, _, paciente, slot, atendimento, livres = await _agendado(db_session, slots_livres=4)
    redis, wa = RedisFalso(), Caixa()

    await _cancelar(db_session, atendimento, MotivoCancelamento.ESTABELECIMENTO, redis=redis, wa=wa)

    oferta = await _oferta_de(db_session, atendimento)
    assert oferta.status == ReagendamentoStatus.PENDENTE
    assert oferta.slot_ids == [s.id for s in livres[:3]]
    assert slot.id not in oferta.slot_ids
    texto = wa.textos[0]
    assert wa.enviadas[0][0] == paciente.telefone
    assert all(f"{n} - " in texto for n in (1, 2, 3))
    assert "4 - " not in texto
    assert "0" in texto
    assert await obter_pendencia(redis, paciente.telefone) == {"tipo": "reagendamento", "oferta_id": oferta.id}


async def test_sem_horario_livre_avisa_a_recepcao(db_session):
    _, _, _, _, atendimento, _ = await _agendado(db_session, slots_livres=0)
    wa, aviso = Caixa(), Caixa()

    await _cancelar(db_session, atendimento, MotivoCancelamento.MEDICO, wa=wa, aviso=aviso)

    oferta = await _oferta_de(db_session, atendimento)
    assert oferta.status == ReagendamentoStatus.SEM_HORARIO
    assert len(aviso.enviadas) == 1
    assert len(wa.enviadas) == 1  # o cliente é avisado do cancelamento mesmo sem opção para oferecer
    assert "recepção" in wa.textos[0]


async def test_cliente_sem_telefone_vira_pendencia_da_recepcao(db_session):
    _, _, _, _, atendimento, _ = await _agendado(db_session, telefone=None)
    aviso = Caixa()

    await _cancelar(db_session, atendimento, MotivoCancelamento.ESTABELECIMENTO, aviso=aviso)

    assert (await _oferta_de(db_session, atendimento)).status == ReagendamentoStatus.SEM_CONTATO
    assert len(aviso.enviadas) == 1


async def test_sem_resposta_em_30_min_expira_e_avisa_a_recepcao(db_session):
    _, _, _, _, atendimento, _ = await _agendado(db_session)
    await _cancelar(db_session, atendimento, MotivoCancelamento.ESTABELECIMENTO)
    oferta = await _oferta_de(db_session, atendimento)
    aviso = Caixa()
    agora = datetime.now(timezone.utc)

    assert await expirar_ofertas(db_session, agora_utc=agora + timedelta(minutes=29), avisar=aviso) == 0
    assert await expirar_ofertas(db_session, agora_utc=agora + timedelta(minutes=31), avisar=aviso) == 1

    assert oferta.status == ReagendamentoStatus.EXPIRADA
    assert len(aviso.enviadas) == 1


# ── T98: resposta do cliente ────────────────────────────────────────────────

async def _oferta_enviada(db, **kw):
    est, prof, paciente, slot, atendimento, livres = await _agendado(db, **kw)
    await _cancelar(db, atendimento, MotivoCancelamento.ESTABELECIMENTO)
    return est, paciente, atendimento, livres, await _oferta_de(db, atendimento)


async def test_resposta_2_agenda_o_segundo_horario(db_session):
    est, paciente, original, livres, oferta = await _oferta_enviada(db_session)

    resposta, concluido = await responder_reagendamento(db_session, oferta.id, "2", avisar=Caixa())

    novo = (
        await db_session.execute(select(Atendimento).where(Atendimento.slot_id == livres[1].id))
    ).scalar_one()
    assert concluido is True
    assert "confirmad" in resposta.lower()
    assert novo.cliente_id == paciente.id
    assert novo.canal_origem == AtendimentoCanal.WHATSAPP
    assert novo.triagem_resumo == original.triagem_resumo  # o profissional não perde a triagem
    assert novo.estabelecimento_id == est.id
    assert livres[1].status == SlotStatus.AGENDADO
    assert livres[0].status == SlotStatus.DISPONIVEL
    assert oferta.status == ReagendamentoStatus.ACEITA
    assert oferta.novo_atendimento_id == novo.id


async def test_resposta_0_recusa_e_avisa_a_recepcao(db_session):
    _, _, _, livres, oferta = await _oferta_enviada(db_session)
    aviso = Caixa()

    resposta, concluido = await responder_reagendamento(db_session, oferta.id, "0", avisar=aviso)

    assert concluido is True
    assert oferta.status == ReagendamentoStatus.RECUSADA
    assert len(aviso.enviadas) == 1
    assert all(s.status == SlotStatus.DISPONIVEL for s in livres)
    assert "recepção" in resposta


async def test_resposta_invalida_orienta_e_mantem_a_oferta(db_session):
    _, _, _, _, oferta = await _oferta_enviada(db_session)

    resposta, concluido = await responder_reagendamento(db_session, oferta.id, "7", avisar=Caixa())

    assert concluido is False
    assert oferta.status == ReagendamentoStatus.PENDENTE
    assert "1" in resposta and "0" in resposta


async def test_horario_ocupado_enquanto_o_cliente_decidia_oferece_os_restantes(db_session):
    _, _, _, livres, oferta = await _oferta_enviada(db_session)
    livres[0].status = SlotStatus.AGENDADO
    await db_session.flush()

    resposta, concluido = await responder_reagendamento(db_session, oferta.id, "1", avisar=Caixa())

    assert concluido is False
    assert oferta.status == ReagendamentoStatus.PENDENTE
    assert oferta.slot_ids == [livres[1].id, livres[2].id]
    assert "1 - " in resposta and "2 - " in resposta and "3 - " not in resposta


async def test_resposta_a_oferta_expirada_nao_agenda(db_session):
    _, _, _, livres, oferta = await _oferta_enviada(db_session)
    await expirar_ofertas(
        db_session, agora_utc=datetime.now(timezone.utc) + timedelta(hours=1), avisar=Caixa()
    )

    resposta, concluido = await responder_reagendamento(db_session, oferta.id, "1", avisar=Caixa())

    assert concluido is True
    assert livres[0].status == SlotStatus.DISPONIVEL
    assert "recepção" in resposta


# ── Pendências para a recepção ──────────────────────────────────────────────

async def test_pendencias_listam_quem_precisa_de_contato_e_somem_ao_resolver(db_session):
    est, paciente, _, _, oferta = await _oferta_enviada(db_session)
    assert await listar_pendencias(db_session, est.id) == []  # oferta ainda aguardando o cliente

    await responder_reagendamento(db_session, oferta.id, "0", avisar=Caixa())
    pendencias = await listar_pendencias(db_session, est.id)

    assert len(pendencias) == 1
    assert pendencias[0]["cliente_nome"] == paciente.nome
    assert pendencias[0]["status"] == "RECUSADA"
    assert pendencias[0]["cliente_telefone"] == paciente.telefone

    outra_unidade = await criar_estabelecimento(db_session)
    assert await resolver_pendencia(db_session, oferta.id, outra_unidade.id) is False
    assert await resolver_pendencia(db_session, oferta.id, est.id) is True
    assert await listar_pendencias(db_session, est.id) == []
