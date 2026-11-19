"""Testes — Resumo de triagem para o profissional (T92) e envio 30 min antes (T93)."""

from datetime import datetime, timedelta

from app.models.atendimento import AtendimentoStatus
from app.services.ia.resumo_triagem import (
    MAX_PALAVRAS,
    categorizar_sintomas,
    contem_diagnostico,
    gerar_resumo_triagem,
    limitar_palavras,
    resumo_por_regra,
)
from app.workers.resumo_medico import enviar_resumos_pendentes
from tests.fabrica import (
    nas_unidades_do_teste,
    Caixa,
    criar_atendimento,
    criar_cliente,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)

DADOS = {
    "nome": "Maria Souza",
    "sintomas": ["Estou com dor de cabeça há três dias", "piora à noite e tenho enjoo"],
    "especialidade": "Neurologia",
    "pagamento": "Unimed — plano Especial",
    "urgencia": "MEDIA",
}


def _ia(texto: str):
    async def invocar(_sistema: str, _usuario: str):
        return texto, 120, 60, "llama3.1:8b"

    return invocar


# ── Regras de texto ─────────────────────────────────────────────────────────

def test_limitar_palavras_corta_no_limite():
    texto = " ".join(["palavra"] * 300)
    assert len(limitar_palavras(texto, 200).split()) <= 201  # 200 + reticências
    assert limitar_palavras("curto", 200) == "curto"


def test_contem_diagnostico_detecta_termos_de_conclusao_clinica():
    assert contem_diagnostico("O paciente tem enxaqueca crônica, diagnóstico provável.")
    assert contem_diagnostico("Recomenda-se prescrever analgésico.")
    assert not contem_diagnostico("Paciente relata dor de cabeça há três dias, com enjoo.")


def test_categorizar_sintomas_agrupa_relatos_em_rotulos():
    categorias = categorizar_sintomas(["Estou com DOR DE CABEÇA e febre", "tosse seca"])
    assert categorias == ["Dor de cabeça", "Febre", "Tosse"]
    assert categorizar_sintomas(["só quero um check-up"]) == ["Check-up / rotina"]
    assert categorizar_sintomas(["xyz"]) == []


def test_resumo_por_regra_usa_o_relato_do_paciente_sem_concluir_nada():
    texto = resumo_por_regra(DADOS)
    assert "dor de cabeça há três dias" in texto
    assert "Neurologia" in texto
    assert "Unimed" in texto
    assert not contem_diagnostico(texto)
    assert len(texto.split()) <= MAX_PALAVRAS


# ── Geração (T92) ───────────────────────────────────────────────────────────

async def test_resumo_da_ia_e_usado_quando_respeita_as_regras():
    resultado = await gerar_resumo_triagem(DADOS, invocar=_ia("Paciente relata cefaleia há três dias com náusea."))

    assert resultado["origem"] == "ia"
    assert resultado["texto"] == "Paciente relata cefaleia há três dias com náusea."
    assert resultado["categorias"] == ["Dor de cabeça", "Náusea / vômito"]
    assert resultado["especialidade"] == "Neurologia"
    assert resultado["uso"] == {"modelo": "llama3.1:8b", "prompt_tokens": 120, "completion_tokens": 60}


async def test_resumo_da_ia_com_diagnostico_e_descartado():
    resultado = await gerar_resumo_triagem(DADOS, invocar=_ia("Diagnóstico: enxaqueca. Prescrever dipirona."))

    assert resultado["origem"] == "regra"
    assert not contem_diagnostico(resultado["texto"])
    assert resultado["uso"]["prompt_tokens"] == 120  # a chamada aconteceu e precisa ser cobrada


async def test_resumo_da_ia_longo_e_cortado_em_200_palavras():
    resultado = await gerar_resumo_triagem(DADOS, invocar=_ia(" ".join(["relata"] * 400)))

    assert resultado["origem"] == "ia"
    assert len(resultado["texto"].split()) <= MAX_PALAVRAS + 1


async def test_falha_da_ia_cai_no_resumo_por_regra():
    async def quebra(_s, _u):
        raise RuntimeError("modelo fora do ar")

    resultado = await gerar_resumo_triagem(DADOS, invocar=quebra)

    assert resultado["origem"] == "regra"
    assert "dor de cabeça" in resultado["texto"]
    assert resultado["uso"] is None


async def test_sem_relato_de_sintomas_nao_chama_a_ia():
    chamadas = []

    async def invocar(_s, _u):
        chamadas.append(1)
        return "x", 1, 1, "m"

    resultado = await gerar_resumo_triagem({**DADOS, "sintomas": []}, invocar=invocar)

    assert chamadas == []
    assert resultado["origem"] == "regra"


# ── Envio ao profissional (T93) ─────────────────────────────────────────────

async def _atendimento_as(db, quando: datetime, **campos):
    est = await criar_estabelecimento(db)
    esp = await criar_especialidade(db, est)
    prof = await criar_profissional(db, est, esp, telefone="11977776666", email="dra@teste.com")
    cliente = await criar_cliente(db, est)
    slot = await criar_slot(db, est, prof, data=quando.date(), hora=quando.time().replace(second=0, microsecond=0))
    campos.setdefault("triagem_resumo", {"texto": "Paciente relata dor de cabeça há três dias.", "origem": "ia"})
    return await criar_atendimento(db, slot, cliente, prof, **campos)


def _relogio(agora: datetime):
    return lambda _fuso: agora


async def test_resumo_e_enviado_ao_profissional_30_min_antes(db_session):
    agora = datetime(2030, 5, 10, 14, 0)
    atendimento = await _atendimento_as(db_session, agora + timedelta(minutes=25))
    wa, mail = Caixa(), Caixa()

    resultado = await nas_unidades_do_teste(enviar_resumos_pendentes, db_session, agora=_relogio(agora), enviar_wa=wa, enviar_mail=mail)

    assert resultado["enviados"] == 1
    assert wa.enviadas[0][0] == "11977776666"
    assert "Maria Souza" in wa.textos[0]
    assert "dor de cabeça há três dias" in wa.textos[0]
    assert "14:25" in wa.textos[0]
    assert len(mail.enviadas) == 1
    assert atendimento.resumo_enviado_em is not None


async def test_resumo_nao_e_reenviado(db_session):
    agora = datetime(2030, 5, 10, 14, 0)
    await _atendimento_as(db_session, agora + timedelta(minutes=25))
    wa = Caixa()
    await nas_unidades_do_teste(enviar_resumos_pendentes, db_session, agora=_relogio(agora), enviar_wa=wa, enviar_mail=Caixa())

    resultado = await nas_unidades_do_teste(enviar_resumos_pendentes, db_session, agora=_relogio(agora + timedelta(minutes=10)), enviar_wa=wa, enviar_mail=Caixa()
    )

    assert resultado["enviados"] == 0
    assert len(wa.enviadas) == 1


async def test_atendimento_fora_da_janela_nao_envia(db_session):
    agora = datetime(2030, 5, 10, 14, 0)
    await _atendimento_as(db_session, agora + timedelta(minutes=50))   # ainda cedo
    await _atendimento_as(db_session, agora - timedelta(minutes=5))    # já começou
    wa = Caixa()

    resultado = await nas_unidades_do_teste(enviar_resumos_pendentes, db_session, agora=_relogio(agora), enviar_wa=wa, enviar_mail=Caixa())

    assert resultado["enviados"] == 0
    assert wa.enviadas == []


async def test_atendimento_cancelado_ou_sem_triagem_nao_envia(db_session):
    agora = datetime(2030, 5, 10, 14, 0)
    await _atendimento_as(db_session, agora + timedelta(minutes=20), status=AtendimentoStatus.CANCELADA)
    await _atendimento_as(db_session, agora + timedelta(minutes=21), triagem_resumo=None)
    wa = Caixa()

    await nas_unidades_do_teste(enviar_resumos_pendentes, db_session, agora=_relogio(agora), enviar_wa=wa, enviar_mail=Caixa())

    assert wa.enviadas == []


async def test_falha_nos_dois_canais_deixa_para_a_proxima_rodada(db_session):
    agora = datetime(2030, 5, 10, 14, 0)
    atendimento = await _atendimento_as(db_session, agora + timedelta(minutes=25))

    resultado = await nas_unidades_do_teste(enviar_resumos_pendentes, db_session, agora=_relogio(agora), enviar_wa=Caixa(sucesso=False), enviar_mail=Caixa(sucesso=False)
    )

    assert resultado["enviados"] == 0
    assert atendimento.resumo_enviado_em is None
