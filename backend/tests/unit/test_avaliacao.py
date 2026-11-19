"""Testes — Avaliação pós-atendimento e NPS (T99, T100, T101, T102)."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.atendimento import AtendimentoStatus
from app.models.atendimento_historico import AtendimentoStatusHistorico
from app.models.avaliacao import Avaliacao, AvaliacaoCanal
from app.services.avaliacao_service import (
    calcular_nps,
    listar_avaliacoes,
    registrar_comentario,
    registrar_nota,
    resumo_nps,
    solicitar_avaliacoes,
)
from app.services.mensageria import obter_pendencia, registrar_pendencia
from tests.fabrica import (
    nas_unidades_do_teste,
    Caixa,
    RedisFalso,
    criar_atendimento,
    criar_cliente,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)

AGORA = datetime.now(timezone.utc)


async def _realizado(db, horas_atras=25, est=None, prof=None, status=AtendimentoStatus.REALIZADA, **cliente):
    est = est or await criar_estabelecimento(db)
    if prof is None:
        esp = await criar_especialidade(db, est)
        prof = await criar_profissional(db, est, esp)
    paciente = await criar_cliente(db, est, **cliente)
    slot = await criar_slot(db, est, prof, data=date.today() - timedelta(days=1))
    atendimento = await criar_atendimento(db, slot, paciente, prof, status=status)
    db.add(
        AtendimentoStatusHistorico(
            atendimento_id=atendimento.id,
            status_anterior=AtendimentoStatus.EM_ATENDIMENTO,
            status_novo=status,
            created_at=AGORA - timedelta(hours=horas_atras),
        )
    )
    await db.flush()
    return est, prof, paciente, atendimento


# ── T99: model ──────────────────────────────────────────────────────────────

async def test_nota_fora_de_1_a_5_e_recusada_pelo_banco(db_session):
    est, prof, paciente, atendimento = await _realizado(db_session)
    db_session.add(
        Avaliacao(
            atendimento_id=atendimento.id, cliente_id=paciente.id, profissional_id=prof.id,
            estabelecimento_id=est.id, nota=6, canal=AvaliacaoCanal.WHATSAPP,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_uma_avaliacao_por_atendimento(db_session):
    est, prof, paciente, atendimento = await _realizado(db_session)
    for _ in range(2):
        db_session.add(
            Avaliacao(
                atendimento_id=atendimento.id, cliente_id=paciente.id, profissional_id=prof.id,
                estabelecimento_id=est.id, nota=5, canal=AvaliacaoCanal.WHATSAPP,
            )
        )
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ── NPS ─────────────────────────────────────────────────────────────────────

def test_nps_em_escala_de_1_a_5():
    """5 = promotor, 4 = neutro, 1 a 3 = detrator."""
    resultado = calcular_nps([5, 5, 5, 4, 3, 1])
    assert resultado["total"] == 6
    assert (resultado["promotores"], resultado["neutros"], resultado["detratores"]) == (3, 1, 2)
    assert resultado["nps"] == 17  # (3 - 2) / 6
    assert resultado["media"] == 3.8


def test_nps_sem_avaliacoes_nao_inventa_numero():
    assert calcular_nps([]) == {
        "total": 0, "promotores": 0, "neutros": 0, "detratores": 0, "nps": None, "media": None,
    }


# ── T100: pedido de avaliação ───────────────────────────────────────────────

async def test_avaliacao_e_pedida_24h_depois_do_atendimento(db_session):
    _, prof, paciente, atendimento = await _realizado(db_session, horas_atras=25)
    redis, wa = RedisFalso(), Caixa()

    resultado = await nas_unidades_do_teste(solicitar_avaliacoes, db_session, redis, agora_utc=AGORA, enviar=wa)

    assert resultado["enviados"] == 1
    assert wa.enviadas[0][0] == paciente.telefone
    assert prof.nome in wa.textos[0]
    assert "1 a 5" in wa.textos[0]
    assert atendimento.avaliacao_solicitada_em is not None
    assert await obter_pendencia(redis, paciente.telefone) == {
        "tipo": "avaliacao", "atendimento_id": atendimento.id,
    }


async def test_avaliacao_nao_e_pedida_antes_de_24h_nem_depois_de_72h(db_session):
    await _realizado(db_session, horas_atras=23)
    await _realizado(db_session, horas_atras=73)
    wa = Caixa()

    resultado = await nas_unidades_do_teste(solicitar_avaliacoes, db_session, RedisFalso(), agora_utc=AGORA, enviar=wa)

    assert resultado["enviados"] == 0


async def test_avaliacao_nao_e_pedida_duas_vezes(db_session):
    await _realizado(db_session)
    wa = Caixa()
    await nas_unidades_do_teste(solicitar_avaliacoes, db_session, RedisFalso(), agora_utc=AGORA, enviar=wa)
    await nas_unidades_do_teste(solicitar_avaliacoes, db_session, RedisFalso(), agora_utc=AGORA + timedelta(hours=1), enviar=wa)

    assert len(wa.enviadas) == 1


async def test_avaliacao_nao_e_pedida_para_cancelado_ou_falta(db_session):
    await _realizado(db_session, status=AtendimentoStatus.CANCELADA)
    await _realizado(db_session, status=AtendimentoStatus.FALTA)
    wa = Caixa()

    await nas_unidades_do_teste(solicitar_avaliacoes, db_session, RedisFalso(), agora_utc=AGORA, enviar=wa)

    assert wa.enviadas == []


async def test_avaliacao_nao_e_pedida_se_ja_foi_avaliado(db_session):
    est, prof, paciente, atendimento = await _realizado(db_session)
    db_session.add(
        Avaliacao(
            atendimento_id=atendimento.id, cliente_id=paciente.id, profissional_id=prof.id,
            estabelecimento_id=est.id, nota=5, canal=AvaliacaoCanal.PORTAL,
        )
    )
    await db_session.flush()
    wa = Caixa()

    await nas_unidades_do_teste(solicitar_avaliacoes, db_session, RedisFalso(), agora_utc=AGORA, enviar=wa)

    assert wa.enviadas == []


async def test_pedido_espera_se_o_cliente_tem_outra_pergunta_em_aberto(db_session):
    """Não atropela uma oferta de horário que o cliente ainda está respondendo."""
    _, _, paciente, atendimento = await _realizado(db_session)
    redis, wa = RedisFalso(), Caixa()
    await registrar_pendencia(redis, paciente.telefone, {"tipo": "fila", "fila_id": 1}, ttl=60)

    await nas_unidades_do_teste(solicitar_avaliacoes, db_session, redis, agora_utc=AGORA, enviar=wa)

    assert wa.enviadas == []
    assert atendimento.avaliacao_solicitada_em is None


# ── T101: resposta ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(("mensagem", "nota"), [("5", 5), (" 4 ", 4), ("nota 3", 3), ("Dou 5 estrelas!", 5)])
async def test_nota_e_salva_e_o_comentario_e_pedido(db_session, mensagem, nota):
    est, prof, paciente, atendimento = await _realizado(db_session)

    texto, proxima = await registrar_nota(db_session, atendimento.id, mensagem, avisar=Caixa())

    avaliacao = (
        await db_session.execute(select(Avaliacao).where(Avaliacao.atendimento_id == atendimento.id))
    ).scalar_one()
    assert avaliacao.nota == nota
    assert avaliacao.canal == AvaliacaoCanal.WHATSAPP
    assert (avaliacao.cliente_id, avaliacao.profissional_id, avaliacao.estabelecimento_id) == (
        paciente.id, prof.id, est.id,
    )
    assert proxima == {"tipo": "avaliacao_comentario", "avaliacao_id": avaliacao.id}
    assert "pular" in texto.lower()


@pytest.mark.parametrize("mensagem", ["0", "6", "foi bom", "10"])
async def test_resposta_que_nao_e_nota_orienta_e_mantem_a_pergunta(db_session, mensagem):
    _, _, _, atendimento = await _realizado(db_session)

    texto, proxima = await registrar_nota(db_session, atendimento.id, mensagem, avisar=Caixa())

    assert proxima == "manter"
    assert "1 a 5" in texto
    assert (await db_session.execute(select(Avaliacao).where(Avaliacao.atendimento_id == atendimento.id))).first() is None


async def test_nota_baixa_avisa_a_recepcao(db_session):
    _, _, _, atendimento = await _realizado(db_session)
    aviso = Caixa()

    await registrar_nota(db_session, atendimento.id, "2", avisar=aviso)

    assert len(aviso.enviadas) == 1


async def test_nota_boa_nao_avisa_a_recepcao(db_session):
    _, _, _, atendimento = await _realizado(db_session)
    aviso = Caixa()

    await registrar_nota(db_session, atendimento.id, "3", avisar=aviso)

    assert aviso.enviadas == []


async def test_comentario_e_gravado(db_session):
    _, _, _, atendimento = await _realizado(db_session)
    _, proxima = await registrar_nota(db_session, atendimento.id, "5", avisar=Caixa())

    texto = await registrar_comentario(db_session, proxima["avaliacao_id"], "  Atendimento muito atencioso.  ")

    avaliacao = (await db_session.execute(select(Avaliacao).where(Avaliacao.id == proxima["avaliacao_id"]))).scalar_one()
    assert avaliacao.comentario == "Atendimento muito atencioso."
    assert "obrigad" in texto.lower()


@pytest.mark.parametrize("mensagem", ["pular", "Pular.", "PULAR"])
async def test_pular_encerra_sem_comentario(db_session, mensagem):
    _, _, _, atendimento = await _realizado(db_session)
    _, proxima = await registrar_nota(db_session, atendimento.id, "4", avisar=Caixa())

    await registrar_comentario(db_session, proxima["avaliacao_id"], mensagem)

    avaliacao = (await db_session.execute(select(Avaliacao).where(Avaliacao.id == proxima["avaliacao_id"]))).scalar_one()
    assert avaliacao.comentario is None


async def test_segunda_nota_para_o_mesmo_atendimento_nao_duplica(db_session):
    _, _, _, atendimento = await _realizado(db_session)
    await registrar_nota(db_session, atendimento.id, "5", avisar=Caixa())

    texto, proxima = await registrar_nota(db_session, atendimento.id, "1", avisar=Caixa())

    notas = (await db_session.execute(select(Avaliacao.nota).where(Avaliacao.atendimento_id == atendimento.id))).scalars().all()
    assert notas == [5]
    assert proxima is None
    assert "já" in texto


# ── T102: consulta e NPS do painel ──────────────────────────────────────────

async def test_resumo_nps_traz_geral_distribuicao_e_ranking(db_session):
    est, ana, _, a1 = await _realizado(db_session)
    esp = await criar_especialidade(db_session, est, nome="Ortopedia")
    beto = await criar_profissional(db_session, est, esp, nome="Dr. Beto")
    _, _, _, a2 = await _realizado(db_session, est=est, prof=ana)
    _, _, _, a3 = await _realizado(db_session, est=est, prof=beto)
    for atendimento, nota in ((a1, "5"), (a2, "5"), (a3, "2")):
        await registrar_nota(db_session, atendimento.id, nota, avisar=Caixa())
    hoje = date.today()

    resumo = await resumo_nps(db_session, est.id, hoje - timedelta(days=1), hoje + timedelta(days=1))

    assert resumo["geral"]["total"] == 3
    assert resumo["geral"]["nps"] == 33
    assert resumo["distribuicao"] == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 2}
    assert [p["profissional_nome"] for p in resumo["profissionais"]] == ["Dra. Ana Lima", "Dr. Beto"]
    assert resumo["profissionais"][0]["media"] == 5.0
    assert resumo["profissionais"][1]["nps"] == -100


async def test_listar_avaliacoes_traz_as_mais_recentes_e_respeita_a_unidade(db_session):
    est, _, paciente, atendimento = await _realizado(db_session)
    _, proxima = await registrar_nota(db_session, atendimento.id, "4", avisar=Caixa())
    await registrar_comentario(db_session, proxima["avaliacao_id"], "Bom.")
    outra, _, _, de_fora = await _realizado(db_session)
    await registrar_nota(db_session, de_fora.id, "1", avisar=Caixa())
    hoje = date.today()

    itens = await listar_avaliacoes(db_session, est.id, hoje - timedelta(days=1), hoje + timedelta(days=1))

    assert len(itens) == 1
    assert itens[0]["nota"] == 4
    assert itens[0]["comentario"] == "Bom."
    assert itens[0]["cliente_nome"] == paciente.nome
    assert itens[0]["profissional_nome"] == "Dra. Ana Lima"
