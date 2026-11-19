"""Testes — Relatórios gerenciais (T94)."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.atendimento import AtendimentoCanal, AtendimentoStatus, MotivoCancelamento
from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.models.sessao_chat import SessaoCanal, SessaoChat
from app.models.slot import SlotStatus
from app.models.token_usage import TokenFeature, TokenUsage
from app.services import relatorio_service as rel
from tests.fabrica import (
    criar_atendimento,
    criar_cliente,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)

HOJE = date.today()
INICIO, FIM = HOJE - timedelta(days=7), HOJE + timedelta(days=7)


async def _base(db):
    est = await criar_estabelecimento(db)
    esp = await criar_especialidade(db, est)
    ana = await criar_profissional(db, est, esp, nome="Dra. Ana Lima")
    return est, esp, ana


async def _atendimento(db, est, prof, status=AtendimentoStatus.AGENDADA, dias=1, **campos):
    cliente = await criar_cliente(db, est)
    slot = await criar_slot(db, est, prof, dias=dias)
    return await criar_atendimento(db, slot, cliente, prof, status=status, **campos)


# ── Ocupação ────────────────────────────────────────────────────────────────

async def test_ocupacao_por_profissional_ignora_horarios_bloqueados(db_session):
    est, esp, ana = await _base(db_session)
    beto = await criar_profissional(db_session, est, esp, nome="Dr. Beto")
    await _atendimento(db_session, est, ana)
    await criar_slot(db_session, est, ana)
    await criar_slot(db_session, est, ana)
    await criar_slot(db_session, est, ana, status=SlotStatus.BLOQUEADO)
    await criar_slot(db_session, est, beto)

    resultado = await rel.ocupacao(db_session, est.id, INICIO, FIM)

    assert resultado["geral"] == {"total_slots": 4, "ocupados": 1, "taxa": 25.0}
    por_nome = {p["profissional_nome"]: p for p in resultado["profissionais"]}
    assert por_nome["Dra. Ana Lima"]["taxa"] == 33.3
    assert por_nome["Dr. Beto"] == {
        "profissional_id": beto.id, "profissional_nome": "Dr. Beto",
        "total_slots": 1, "ocupados": 0, "taxa": 0.0,
    }


async def test_ocupacao_respeita_periodo_unidade_e_filtro_de_profissional(db_session):
    est, esp, ana = await _base(db_session)
    beto = await criar_profissional(db_session, est, esp, nome="Dr. Beto")
    await criar_slot(db_session, est, ana, dias=1)
    await criar_slot(db_session, est, ana, dias=40)       # fora do período
    await criar_slot(db_session, est, beto, dias=1)
    outra, outra_esp, de_fora = await _base(db_session)
    await criar_slot(db_session, outra, de_fora, dias=1)  # outra unidade

    assert (await rel.ocupacao(db_session, est.id, INICIO, FIM))["geral"]["total_slots"] == 2
    so_ana = await rel.ocupacao(db_session, est.id, INICIO, FIM, profissional_id=ana.id)
    assert so_ana["geral"]["total_slots"] == 1
    assert [p["profissional_nome"] for p in so_ana["profissionais"]] == ["Dra. Ana Lima"]


async def test_ocupacao_sem_slots_tem_taxa_zero(db_session):
    est, _, _ = await _base(db_session)
    assert (await rel.ocupacao(db_session, est.id, INICIO, FIM))["geral"] == {
        "total_slots": 0, "ocupados": 0, "taxa": 0.0,
    }


# ── Comparecimento ──────────────────────────────────────────────────────────

async def test_confirmacao_calcula_comparecimento_e_cancelamento(db_session):
    est, _, ana = await _base(db_session)
    for status in (AtendimentoStatus.REALIZADA,) * 3 + (AtendimentoStatus.FALTA, AtendimentoStatus.AGENDADA):
        await _atendimento(db_session, est, ana, status=status)
    await _atendimento(
        db_session, est, ana, status=AtendimentoStatus.CANCELADA,
        motivo_cancelamento=MotivoCancelamento.PACIENTE,
    )
    await _atendimento(
        db_session, est, ana, status=AtendimentoStatus.CANCELADA,
        motivo_cancelamento=MotivoCancelamento.MEDICO,
    )

    r = await rel.confirmacao(db_session, est.id, INICIO, FIM)

    assert (r["total"], r["realizados"], r["faltas"], r["cancelados"], r["em_aberto"]) == (7, 3, 1, 2, 1)
    assert r["taxa_comparecimento"] == 75.0     # 3 de 4 que deveriam ter vindo
    assert r["taxa_cancelamento"] == 28.6       # 2 de 7
    assert r["cancelamentos_por_motivo"] == {"PACIENTE": 1, "MEDICO": 1}


async def test_confirmacao_sem_atendimentos_nao_divide_por_zero(db_session):
    est, _, _ = await _base(db_session)
    r = await rel.confirmacao(db_session, est.id, INICIO, FIM)
    assert (r["total"], r["taxa_comparecimento"], r["taxa_cancelamento"]) == (0, None, None)


# ── Sintomas ────────────────────────────────────────────────────────────────

async def test_sintomas_mais_citados_e_especialidades_procuradas(db_session):
    est, _, ana = await _base(db_session)
    for categorias in (["Dor de cabeça", "Febre"], ["Dor de cabeça"], ["Tosse"]):
        await _atendimento(
            db_session, est, ana,
            triagem_resumo={"texto": "x", "categorias": categorias, "especialidade": "Cardiologia"},
        )
    await _atendimento(db_session, est, ana)  # sem triagem (agendado pela recepção)

    r = await rel.sintomas(db_session, est.id, INICIO, FIM)

    assert r["total_triagens"] == 3
    assert r["sintomas"][0] == {"rotulo": "Dor de cabeça", "total": 2}
    assert {s["rotulo"] for s in r["sintomas"]} == {"Dor de cabeça", "Febre", "Tosse"}
    assert r["especialidades"] == [{"nome": "Cardiologia", "total": 4}]


# ── Custo de IA por agendamento ─────────────────────────────────────────────

async def test_custo_por_agendamento_divide_o_gasto_de_ia_pelos_agendamentos_do_chat(db_session):
    est, _, ana = await _base(db_session)
    sessao = SessaoChat(session_token=f"t-{est.id}", canal=SessaoCanal.PORTAL, estabelecimento_id=est.id)
    db_session.add(sessao)
    await db_session.flush()
    for custo in ("0.03", "0.01"):
        db_session.add(
            TokenUsage(
                session_id=sessao.id, estabelecimento_id=est.id, modelo="m", feature=TokenFeature.GERAL,
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
                cost_usd=Decimal(custo), user_type="EXTERNO",
            )
        )
    await _atendimento(db_session, est, ana, canal_origem=AtendimentoCanal.PORTAL)
    await _atendimento(db_session, est, ana, canal_origem=AtendimentoCanal.WHATSAPP)
    await _atendimento(db_session, est, ana, canal_origem=AtendimentoCanal.INTERNO)  # recepção: não conta

    r = await rel.custo_por_agendamento(db_session, est.id, INICIO, FIM)

    assert r["custo_total_usd"] == 0.04
    assert r["total_tokens"] == 300
    assert r["chamadas"] == 2
    assert r["agendamentos_chat"] == 2
    assert r["custo_por_agendamento_usd"] == 0.02


async def test_custo_por_agendamento_sem_agendamento_fica_sem_media(db_session):
    est, _, _ = await _base(db_session)
    r = await rel.custo_por_agendamento(db_session, est.id, INICIO, FIM)
    assert r["agendamentos_chat"] == 0
    assert r["custo_por_agendamento_usd"] is None


# ── Fila de espera ──────────────────────────────────────────────────────────

async def test_fila_espera_conta_status_conversao_e_espera_media(db_session):
    est, esp, _ = await _base(db_session)
    agora = datetime.now(timezone.utc)
    situacoes = [
        (FilaEsperaStatus.AGUARDANDO, None),
        (FilaEsperaStatus.AGENDADO, agora + timedelta(hours=2)),
        (FilaEsperaStatus.AGENDADO, agora + timedelta(hours=4)),
        (FilaEsperaStatus.CANCELADO, None),
    ]
    for status, notificado in situacoes:
        cliente = await criar_cliente(db_session, est)
        db_session.add(
            FilaEspera(
                cliente_id=cliente.id, estabelecimento_id=est.id, especialidade_id=esp.id,
                status=status, notificado_em=notificado, created_at=agora,
            )
        )
    await db_session.flush()

    r = await rel.fila_espera(db_session, est.id, INICIO, FIM)

    assert (r["entradas"], r["aguardando"], r["agendados"], r["cancelados"]) == (4, 1, 2, 1)
    assert r["taxa_conversao"] == 50.0
    assert r["espera_media_horas"] == 3.0
