"""Testes — Telemedicina (G29): horários online, sala, consentimento, sala de espera, registro e documentos."""

import re
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.atendimento_historico import AtendimentoStatusHistorico
from app.models.slot import SlotStatus
from app.models.teleconsulta import Modalidade, Teleconsulta, TipoDocumento
from app.schemas.atendimento import AtendimentoCreate
from app.services import telemedicina_service as tele
from app.services.agenda_service import AgendaService
from app.services.documentos_pdf import gerar_pdf
from tests.fabrica import (
    Caixa,
    criar_atendimento,
    criar_cliente,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)

INICIO = datetime(2030, 5, 10, 14, 0)


def _relogio(agora: datetime):
    return lambda _fuso=None: agora


async def _online(db, status=AtendimentoStatus.AGENDADA, **cliente):
    """Atendimento online marcado para INICIO, com a sala criada."""
    est = await criar_estabelecimento(db, nome="Clínica Vida")
    esp = await criar_especialidade(db, est)
    prof = await criar_profissional(db, est, esp)
    paciente = await criar_cliente(db, est, **cliente)
    slot = await criar_slot(db, est, prof, data=INICIO.date(), hora=INICIO.time())
    slot.aceita_online = True
    atendimento = await criar_atendimento(
        db, slot, paciente, prof, status=status, modalidade=Modalidade.ONLINE,
        triagem_resumo={"texto": "Paciente relata tosse seca.", "origem": "ia", "categorias": ["Tosse"], "historico": []},
    )
    sala = await tele.criar_teleconsulta(db, atendimento)
    return est, prof, paciente, atendimento, sala


# ── Horários que aceitam atendimento online ─────────────────────────────────

async def test_profissional_marca_os_horarios_livres_do_dia_como_online(db_session):
    est = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, est)
    prof = await criar_profissional(db_session, est, esp)
    outro = await criar_profissional(db_session, est, esp, nome="Dr. Beto")
    livre = await criar_slot(db_session, est, prof, dias=2)
    ocupado = await criar_slot(db_session, est, prof, dias=2, status=SlotStatus.AGENDADO)
    outro_dia = await criar_slot(db_session, est, prof, dias=3)
    de_outro = await criar_slot(db_session, est, outro, dias=2)

    total = await tele.marcar_slots_online(db_session, est.id, livre.data, True, profissional_id=prof.id)

    assert total == 1
    assert livre.aceita_online is True
    assert (ocupado.aceita_online, outro_dia.aceita_online, de_outro.aceita_online) == (False, False, False)

    await tele.marcar_slots_online(db_session, est.id, livre.data, False, profissional_id=prof.id)
    assert livre.aceita_online is False


async def test_marcar_online_escolhendo_horarios_e_respeitando_a_unidade(db_session):
    est = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, est)
    prof = await criar_profissional(db_session, est, esp)
    a = await criar_slot(db_session, est, prof, dias=2)
    b = await criar_slot(db_session, est, prof, dias=2)
    outra = await criar_estabelecimento(db_session)

    assert await tele.marcar_slots_online(db_session, outra.id, a.data, True, slot_ids=[a.id]) == 0
    assert await tele.marcar_slots_online(db_session, est.id, a.data, True, slot_ids=[a.id]) == 1
    assert (a.aceita_online, b.aceita_online) == (True, False)


# ── Agendamento online ──────────────────────────────────────────────────────

async def test_agendar_online_cria_a_sala_com_link_proprio(db_session):
    est = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, est)
    prof = await criar_profissional(db_session, est, esp)
    paciente = await criar_cliente(db_session, est)
    slot = await criar_slot(db_session, est, prof)
    slot.aceita_online = True
    dados = AtendimentoCreate(
        slot_id=slot.id, cliente_id=paciente.id, profissional_id=prof.id,
        especialidade_id=esp.id, modalidade=Modalidade.ONLINE,
    )

    atendimento = await AgendaService(db_session).agendar_consulta(dados, est.id)

    sala = (
        await db_session.execute(select(Teleconsulta).where(Teleconsulta.atendimento_id == atendimento.id))
    ).scalar_one()
    assert atendimento.modalidade == Modalidade.ONLINE
    assert len(sala.token_paciente) >= 32
    assert sala.sala.startswith("medbot-")
    assert sala.token_paciente not in sala.sala      # quem vê a sala não deduz o link do paciente


async def test_agendar_online_em_horario_so_presencial_e_recusado(db_session):
    from app.services.agenda_service import SlotIndisponivelError

    est = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, est)
    prof = await criar_profissional(db_session, est, esp)
    paciente = await criar_cliente(db_session, est)
    slot = await criar_slot(db_session, est, prof)
    dados = AtendimentoCreate(
        slot_id=slot.id, cliente_id=paciente.id, profissional_id=prof.id,
        especialidade_id=esp.id, modalidade=Modalidade.ONLINE,
    )

    with pytest.raises(SlotIndisponivelError):
        await AgendaService(db_session).agendar_consulta(dados, est.id)
    assert slot.status == SlotStatus.DISPONIVEL


async def test_criar_teleconsulta_duas_vezes_devolve_a_mesma_sala(db_session):
    _, _, _, atendimento, sala = await _online(db_session)
    assert (await tele.criar_teleconsulta(db_session, atendimento)).id == sala.id


async def test_link_e_enviado_por_whatsapp_e_email(db_session):
    _, prof, paciente, atendimento, sala = await _online(db_session)
    wa, mail = Caixa(), Caixa()

    assert await tele.enviar_link(db_session, atendimento, enviar_wa=wa, enviar_mail=mail) is True

    assert wa.enviadas[0][0] == paciente.telefone
    assert f"/teleconsulta/{sala.token_paciente}" in wa.textos[0]
    assert prof.nome in wa.textos[0]
    assert "10/05/2030" in wa.textos[0] and "14:00" in wa.textos[0]
    assert len(mail.enviadas) == 1
    assert sala.link_enviado_em is not None


# ── Paciente: consentimento e sala de espera ────────────────────────────────

async def test_link_invalido_nao_revela_nada(db_session):
    with pytest.raises(tele.TeleconsultaNaoEncontradaError):
        await tele.situacao_do_paciente(db_session, "token-que-nao-existe")


async def test_antes_do_consentimento_o_paciente_ve_o_termo_e_nao_a_sala(db_session):
    _, prof, paciente, _, sala = await _online(db_session)

    s = await tele.situacao_do_paciente(db_session, sala.token_paciente, agora=_relogio(INICIO - timedelta(minutes=10)))

    assert s["situacao"] == "AGUARDANDO_CONSENTIMENTO"
    assert s["termo"]["versao"] == tele.TERMO_VERSAO
    assert s["sala_url"] is None
    assert s["profissional_nome"] == prof.nome
    assert s["paciente_nome"] == paciente.nome.split()[0]     # só o primeiro nome em página pública
    assert (s["data"], s["hora"]) == ("10/05/2030", "14:00")
    assert "cpf" not in str(s).lower()


async def test_consentimento_registra_versao_do_termo_data_e_ip(db_session):
    _, _, _, _, sala = await _online(db_session)

    await tele.registrar_consentimento(db_session, sala.token_paciente, ip="203.0.113.7")

    assert sala.termo_versao == tele.TERMO_VERSAO
    assert sala.consentimento_em is not None
    assert sala.consentimento_ip == "203.0.113.7"


async def test_presenca_sem_consentimento_e_recusada(db_session):
    _, _, _, _, sala = await _online(db_session)
    with pytest.raises(tele.ConsentimentoPendenteError):
        await tele.registrar_presenca(db_session, sala.token_paciente, agora=_relogio(INICIO))


async def test_entrar_na_sala_de_espera_faz_o_check_in(db_session):
    _, _, _, atendimento, sala = await _online(db_session)
    await tele.registrar_consentimento(db_session, sala.token_paciente, ip=None)

    s = await tele.registrar_presenca(db_session, sala.token_paciente, agora=_relogio(INICIO - timedelta(minutes=10)))

    assert s["situacao"] == "SALA_DE_ESPERA"
    assert s["sala_url"] is None                    # a sala só abre quando o profissional inicia
    assert atendimento.status == AtendimentoStatus.PRESENTE
    assert sala.paciente_entrou_em is not None
    historico = (
        await db_session.execute(
            select(AtendimentoStatusHistorico).where(AtendimentoStatusHistorico.atendimento_id == atendimento.id)
        )
    ).scalars().all()
    assert [h.status_novo for h in historico] == [AtendimentoStatus.PRESENTE]
    assert "online" in historico[0].observacao.lower()


async def test_cedo_demais_nao_faz_check_in_e_informa_quando_abre(db_session):
    _, _, _, atendimento, sala = await _online(db_session)
    await tele.registrar_consentimento(db_session, sala.token_paciente, ip=None)

    s = await tele.registrar_presenca(db_session, sala.token_paciente, agora=_relogio(INICIO - timedelta(hours=3)))

    assert s["situacao"] == "CEDO"
    assert s["abre_as"] == "13:30"
    assert atendimento.status == AtendimentoStatus.AGENDADA


async def test_quando_o_profissional_inicia_o_paciente_recebe_a_sala(db_session):
    _, _, paciente, atendimento, sala = await _online(db_session)
    await tele.registrar_consentimento(db_session, sala.token_paciente, ip=None)
    atendimento.status = AtendimentoStatus.EM_ATENDIMENTO

    s = await tele.situacao_do_paciente(db_session, sala.token_paciente, agora=_relogio(INICIO))

    assert s["situacao"] == "EM_ANDAMENTO"
    assert s["sala_url"].startswith("https://meet.jit.si/" + sala.sala)
    assert paciente.nome.split()[0] in s["sala_url"]


async def test_sem_consentimento_a_sala_nao_e_entregue_mesmo_com_o_atendimento_iniciado(db_session):
    _, _, _, atendimento, sala = await _online(db_session)
    atendimento.status = AtendimentoStatus.EM_ATENDIMENTO

    s = await tele.situacao_do_paciente(db_session, sala.token_paciente, agora=_relogio(INICIO))

    assert s["situacao"] == "AGUARDANDO_CONSENTIMENTO"
    assert s["sala_url"] is None


@pytest.mark.parametrize(
    ("status", "situacao"),
    [
        (AtendimentoStatus.REALIZADA, "ENCERRADA"),
        (AtendimentoStatus.CANCELADA, "CANCELADA"),
        (AtendimentoStatus.FALTA, "CANCELADA"),
    ],
)
async def test_atendimento_encerrado_ou_cancelado_nao_abre_sala(db_session, status, situacao):
    _, _, _, _, sala = await _online(db_session, status=status)
    await tele.registrar_consentimento(db_session, sala.token_paciente, ip=None)

    s = await tele.situacao_do_paciente(db_session, sala.token_paciente, agora=_relogio(INICIO))

    assert s["situacao"] == situacao
    assert s["sala_url"] is None


async def test_sala_com_jwt_quando_o_servidor_proprio_esta_configurado(db_session):
    from jose import jwt

    with (
        patch.object(tele.settings, "jitsi_base_url", "https://video.clinica.com/"),
        patch.object(tele.settings, "jitsi_app_id", "medbot"),
        patch.object(tele.settings, "jitsi_app_secret", "segredo"),
    ):
        url = tele.url_da_sala("medbot-abc", "Dra. Ana", moderador=True)

    assert url.startswith("https://video.clinica.com/medbot-abc?jwt=")
    carga = jwt.decode(url.split("jwt=")[1].split("#")[0], "segredo", algorithms=["HS256"], audience="jitsi")
    assert carga["room"] == "medbot-abc"
    assert carga["context"]["user"] == {"name": "Dra. Ana", "moderator": "true"}


# ── Profissional: sala, registro e documentos ───────────────────────────────

async def test_profissional_ve_triagem_sala_e_presenca_do_paciente(db_session):
    est, prof, paciente, atendimento, sala = await _online(db_session)
    await tele.registrar_consentimento(db_session, sala.token_paciente, ip=None)
    agora = INICIO - timedelta(minutes=5)
    await tele.registrar_presenca(db_session, sala.token_paciente, agora=_relogio(agora))

    dados = await tele.sala_do_profissional(db_session, atendimento.id, prof.id, est.id)

    assert dados["cliente_nome"] == paciente.nome
    assert dados["modalidade"] == "ONLINE"
    assert dados["triagem"]["texto"] == "Paciente relata tosse seca."
    assert dados["teleconsulta"]["sala_url"].startswith("https://meet.jit.si/" + sala.sala)
    assert dados["teleconsulta"]["paciente_na_sala"] is True
    assert dados["teleconsulta"]["consentimento"] is True
    assert dados["status"] == "PRESENTE"
    assert dados["acoes"] == ["EM_ATENDIMENTO"]
    assert dados["registro"] == {"queixa": None, "evolucao": None, "conduta": None, "atualizado_em": None}
    assert dados["documentos"] == []


async def test_atendimento_de_outro_profissional_ou_unidade_nao_e_encontrado(db_session):
    est, prof, _, atendimento, _ = await _online(db_session)
    outra = await criar_estabelecimento(db_session)

    with pytest.raises(tele.AtendimentoNaoEncontradoError):
        await tele.sala_do_profissional(db_session, atendimento.id, prof.id + 9999, est.id)
    with pytest.raises(tele.AtendimentoNaoEncontradoError):
        await tele.sala_do_profissional(db_session, atendimento.id, prof.id, outra.id)


async def test_atendimento_presencial_tambem_tem_registro_mas_nao_tem_sala(db_session):
    est = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, est)
    prof = await criar_profissional(db_session, est, esp)
    paciente = await criar_cliente(db_session, est)
    atendimento = await criar_atendimento(db_session, await criar_slot(db_session, est, prof), paciente, prof)

    dados = await tele.sala_do_profissional(db_session, atendimento.id, prof.id, est.id)

    assert dados["modalidade"] == "PRESENCIAL"
    assert dados["teleconsulta"] is None


async def test_registro_do_atendimento_e_gravado_e_atualizado(db_session):
    est, prof, _, atendimento, _ = await _online(db_session, status=AtendimentoStatus.EM_ATENDIMENTO)

    await tele.salvar_registro(db_session, atendimento.id, prof.id, est.id, queixa="Tosse", evolucao="  ", conduta=None)
    await tele.salvar_registro(db_session, atendimento.id, prof.id, est.id, queixa="Tosse seca", evolucao="Sem febre.", conduta="Retorno em 7 dias")

    registro = (await tele.sala_do_profissional(db_session, atendimento.id, prof.id, est.id))["registro"]
    assert (registro["queixa"], registro["evolucao"], registro["conduta"]) == ("Tosse seca", "Sem febre.", "Retorno em 7 dias")
    assert registro["atualizado_em"] is not None


async def test_registro_nao_e_aceito_em_atendimento_cancelado(db_session):
    est, prof, _, atendimento, _ = await _online(db_session, status=AtendimentoStatus.CANCELADA)
    with pytest.raises(tele.OperacaoNaoPermitidaError):
        await tele.salvar_registro(db_session, atendimento.id, prof.id, est.id, queixa="x", evolucao=None, conduta=None)


async def test_receita_emitida_durante_o_atendimento_fica_disponivel_ao_paciente(db_session):
    est, prof, _, atendimento, sala = await _online(db_session, status=AtendimentoStatus.EM_ATENDIMENTO)
    await tele.registrar_consentimento(db_session, sala.token_paciente, ip=None)
    conteudo = {"itens": [{"medicamento": "Dipirona 500 mg", "posologia": "1 comprimido a cada 6 horas se houver dor"}]}

    doc = await tele.emitir_documento(db_session, atendimento.id, prof.id, est.id, TipoDocumento.RECEITA, conteudo)
    situacao = await tele.situacao_do_paciente(db_session, sala.token_paciente, agora=_relogio(INICIO))

    assert len(doc.codigo) >= 8
    assert situacao["documentos"] == [{"id": doc.id, "tipo": "RECEITA", "emitido_em": situacao["documentos"][0]["emitido_em"]}]
    pdf, nome = await tele.pdf_do_documento_do_paciente(db_session, sala.token_paciente, doc.id)
    assert pdf.startswith(b"%PDF")
    assert nome.endswith(".pdf") and "receita" in nome


async def test_paciente_nao_baixa_documento_de_outro_atendimento(db_session):
    est, prof, _, atendimento, _ = await _online(db_session, status=AtendimentoStatus.EM_ATENDIMENTO)
    doc = await tele.emitir_documento(
        db_session, atendimento.id, prof.id, est.id, TipoDocumento.ATESTADO, {"dias": 2}
    )
    _, _, _, _, outra_sala = await _online(db_session)

    with pytest.raises(tele.AtendimentoNaoEncontradoError):
        await tele.pdf_do_documento_do_paciente(db_session, outra_sala.token_paciente, doc.id)


async def test_documento_so_e_emitido_com_o_atendimento_em_andamento_ou_realizado(db_session):
    est, prof, _, atendimento, _ = await _online(db_session, status=AtendimentoStatus.AGENDADA)
    with pytest.raises(tele.OperacaoNaoPermitidaError):
        await tele.emitir_documento(db_session, atendimento.id, prof.id, est.id, TipoDocumento.ATESTADO, {"dias": 1})


@pytest.mark.parametrize(
    ("tipo", "conteudo"),
    [
        (TipoDocumento.RECEITA, {"itens": []}),
        (TipoDocumento.RECEITA, {"itens": [{"medicamento": "  ", "posologia": "1x ao dia"}]}),
        (TipoDocumento.RECEITA, {"itens": [{"medicamento": "Dipirona"}]}),
        (TipoDocumento.ATESTADO, {"dias": 0}),
        (TipoDocumento.ATESTADO, {"dias": 400}),
        (TipoDocumento.ATESTADO, {}),
    ],
)
async def test_documento_com_conteudo_invalido_e_recusado(db_session, tipo, conteudo):
    est, prof, _, atendimento, _ = await _online(db_session, status=AtendimentoStatus.EM_ATENDIMENTO)
    with pytest.raises(tele.ConteudoInvalidoError):
        await tele.emitir_documento(db_session, atendimento.id, prof.id, est.id, tipo, conteudo)


# ── PDF ─────────────────────────────────────────────────────────────────────

def _texto_do_pdf(pdf: bytes) -> str:
    import re
    import zlib

    partes = []
    for bruto in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            partes.append(zlib.decompress(bruto).decode("latin-1"))
        except zlib.error:
            continue
    return " ".join(partes).replace(r"\(", "(").replace(r"\)", ")")


BASE_PDF = {
    "codigo": "AB12CD34",
    "emitido_em": "10/05/2030",
    "unidade": {"nome": "Clínica Vida", "endereco": "Rua das Flores, 100 — São Paulo/SP", "telefone": "(11) 3333-4444"},
    "profissional": {"nome": "Dra. Ana Lima", "registro": "CRM 12345"},
    "paciente": {"nome": "João da Conceição"},
}


def test_pdf_de_receita_traz_paciente_itens_profissional_e_codigo():
    pdf = gerar_pdf({
        **BASE_PDF, "tipo": "RECEITA",
        "conteudo": {"itens": [{"medicamento": "Dipirona 500 mg", "posologia": "1 comprimido a cada 6 horas"}]},
    })
    texto = _texto_do_pdf(pdf)

    assert pdf.startswith(b"%PDF")
    for trecho in ("Dipirona 500 mg", "1 comprimido a cada 6 horas", "Dra. Ana Lima", "CRM 12345", "AB12CD34"):
        assert trecho in texto
    assert "Jo\xe3o da Concei\xe7\xe3o" in texto      # acentos preservados


def test_pdf_de_atestado_escreve_os_dias_por_extenso_e_so_inclui_cid_se_informado():
    sem_cid = _texto_do_pdf(gerar_pdf({**BASE_PDF, "tipo": "ATESTADO", "conteudo": {"dias": 3, "a_partir_de": "10/05/2030"}}))
    com_cid = _texto_do_pdf(gerar_pdf({**BASE_PDF, "tipo": "ATESTADO", "conteudo": {"dias": 1, "cid": "J06.9"}}))

    assert "3 (tr\xeas) dias" in sem_cid
    assert "CID" not in sem_cid
    assert "1 (um) dia" in com_cid and "J06.9" in com_cid


def test_pdf_nao_quebra_com_caracteres_fora_do_latin1():
    pdf = gerar_pdf({
        **BASE_PDF, "tipo": "RECEITA",
        "conteudo": {"itens": [{"medicamento": "Vitamina D — 2.000 UI “gotas” 😀", "posologia": "1× ao dia"}]},
    })
    assert pdf.startswith(b"%PDF")


def test_pdf_de_receita_longa_quebra_pagina_e_assina_uma_vez_so():
    itens = [
        {"medicamento": f"Medicamento {n} 500 mg", "posologia": "Tomar 1 comprimido a cada 8 horas, " * 6}
        for n in range(1, 11)
    ]
    pdf = gerar_pdf({**BASE_PDF, "tipo": "RECEITA", "conteudo": {"itens": itens}})
    texto = _texto_do_pdf(pdf)

    paginas = len(re.findall(rb"/Type /Page\b(?!s)", pdf))
    assert paginas >= 2
    assert "Medicamento 10 500 mg" in texto
    assert texto.count("CRM 12345") == 1
