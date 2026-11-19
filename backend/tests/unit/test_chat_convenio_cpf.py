"""Testes unitários — convênio/plano e CPF no agendamento pelo chat (gaps do G28).

Cobre:
- dados_paciente: validação/máscara de CPF e localização de convênio/plano no texto livre
- Chat envia a lista de convênios aceitos (botões) ao perguntar pelo convênio
- Convênio com planos → pergunta o plano com respostas rápidas; sem planos → segue para os sintomas
- Convênio que a unidade não aceita → informa os aceitos e continua perguntando
- Horário escolhido → pede CPF, valida, só então telefone e e-mail
- Resumo mostra o CPF mascarado; cliente é criado com o CPF real e o convênio informado
- agora_local: relógio no fuso configurado (horário "já passou" não depende do fuso do servidor)
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ia.chat_service import ChatService
from app.services.ia.dados_paciente import localizar_por_nome, mascarar_cpf, normalizar_cpf
from app.services.ia.state_machine import ChatEstado

CPF_VALIDO = "52998224725"

_CONVENIOS = [
    {"id": 1, "nome": "Unimed", "planos": [{"id": 10, "nome": "Básico"}, {"id": 11, "nome": "Especial"}]},
    {"id": 2, "nome": "SulAmérica", "planos": []},
]

_SLOT_TEMP = {
    "id": 42, "data": "20/11/2026", "hora_inicio": "09:00", "hora_fim": "09:40",
    "profissional_nome": "Dr. Ricardo Nunes",
}


def _servico() -> ChatService:
    db = AsyncMock()
    db.add = MagicMock()
    redis = AsyncMock()
    return ChatService(db=db, redis=redis)


def _dados(**extras) -> dict:
    base = {
        "nome": "Pedro Henrique Oliveira", "cpf": None, "convenio_id": None, "convenio": None,
        "plano_id": None, "plano": None, "convenio_step": None, "tipo_atendimento": None,
        "telefone": None, "email": None, "slot_id_selecionado": None, "contato_step": "cpf",
        "sintomas": [], "especialidade": "Ortopedia", "perguntas_coleta": 0,
    }
    return {**base, **extras}


def _sessao(estado: str, dados: dict, convenios: list | None = _CONVENIOS) -> bytes:
    return json.dumps({
        "token": "t", "canal": "PORTAL", "estabelecimento_id": 1, "mensagens": [],
        "estado": estado, "especialidades": ["Clínica Geral", "Ortopedia"],
        "convenios": convenios if convenios is not None else [],
        "slots_temp": [_SLOT_TEMP], "dados_coletados": dados,
    }).encode()


def _salvo(svc: ChatService) -> dict:
    return json.loads(svc.redis.set.call_args[0][1])


# ============================================================
# dados_paciente
# ============================================================

@pytest.mark.parametrize("texto", ["529.982.247-25", "52998224725", "meu cpf é 529 982 247 25"])
def test_cpf_valido_e_normalizado_para_11_digitos(texto):
    assert normalizar_cpf(texto) == CPF_VALIDO


@pytest.mark.parametrize("texto", ["", "123", "11111111111", "52998224724", "00000000000", "não tenho"])
def test_cpf_invalido_e_recusado(texto):
    assert normalizar_cpf(texto) is None


def test_cpf_mascarado_esconde_o_miolo():
    assert mascarar_cpf(CPF_VALIDO) == "529.XXX.XXX-25"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Sim, meu convênio é Unimed", 1),
        ("unimed", 1),
        ("tenho sulamerica", 2),        # sem acento
        ("Sul América Saúde", 2),        # nome cadastrado contido no que foi digitado
        ("Bradesco", None),
        ("", None),
    ],
)
def test_localiza_convenio_no_texto_livre(texto, esperado):
    achado = localizar_por_nome(texto, _CONVENIOS)
    assert (achado["id"] if achado else None) == esperado


# ============================================================
# Convênio e plano
# ============================================================

async def test_ao_perguntar_o_convenio_envia_os_convenios_aceitos():
    svc = _servico()
    svc.redis.get = AsyncMock(return_value=_sessao("COLETANDO_NOME", _dados(nome=None)))

    resultado = await svc.processar_mensagem("t", "Pedro Henrique Oliveira")

    assert resultado["estado"] == ChatEstado.COLETANDO_CONVENIO
    assert resultado["convenios"] == [{"id": 1, "nome": "Unimed"}, {"id": 2, "nome": "SulAmérica"}]


async def test_convenio_com_planos_pergunta_o_plano():
    svc = _servico()
    svc.redis.get = AsyncMock(return_value=_sessao("COLETANDO_CONVENIO", _dados()))

    resultado = await svc.processar_mensagem("t", "Sim, meu convênio é Unimed")

    assert resultado["estado"] == ChatEstado.COLETANDO_CONVENIO
    assert "plano" in resultado["resposta"].lower()
    assert resultado["quick_replies"] == ["Básico", "Especial", "Não sei informar"]
    assert "convenios" not in resultado
    dados = _salvo(svc)["dados_coletados"]
    assert dados["convenio_id"] == 1
    assert dados["convenio"] == "Unimed"
    assert dados["tipo_atendimento"] == "CONVENIO"


async def test_plano_escolhido_segue_para_os_sintomas():
    svc = _servico()
    dados = _dados(convenio_id=1, convenio="Unimed", tipo_atendimento="CONVENIO", convenio_step="plano")
    svc.redis.get = AsyncMock(return_value=_sessao("COLETANDO_CONVENIO", dados))

    resultado = await svc.processar_mensagem("t", "Especial")

    assert resultado["estado"] == ChatEstado.OUVINDO_SINTOMAS
    salvos = _salvo(svc)["dados_coletados"]
    assert salvos["plano_id"] == 11
    assert salvos["plano"] == "Especial"
    assert salvos["tipo_atendimento"] == "CONVENIO"


async def test_plano_nao_informado_nao_vira_particular():
    svc = _servico()
    dados = _dados(convenio_id=1, convenio="Unimed", tipo_atendimento="CONVENIO", convenio_step="plano")
    svc.redis.get = AsyncMock(return_value=_sessao("COLETANDO_CONVENIO", dados))

    resultado = await svc.processar_mensagem("t", "Não sei informar")

    assert resultado["estado"] == ChatEstado.OUVINDO_SINTOMAS
    salvos = _salvo(svc)["dados_coletados"]
    assert salvos["tipo_atendimento"] == "CONVENIO"
    assert salvos["convenio_id"] == 1
    assert salvos["plano_id"] is None


async def test_convenio_sem_planos_segue_direto_para_os_sintomas():
    svc = _servico()
    svc.redis.get = AsyncMock(return_value=_sessao("COLETANDO_CONVENIO", _dados()))

    resultado = await svc.processar_mensagem("t", "SulAmérica")

    assert resultado["estado"] == ChatEstado.OUVINDO_SINTOMAS
    assert _salvo(svc)["dados_coletados"]["convenio_id"] == 2


async def test_convenio_nao_aceito_informa_os_aceitos_e_continua_perguntando():
    svc = _servico()
    svc.redis.get = AsyncMock(return_value=_sessao("COLETANDO_CONVENIO", _dados()))

    resultado = await svc.processar_mensagem("t", "Bradesco Saúde")

    assert resultado["estado"] == ChatEstado.COLETANDO_CONVENIO
    assert "Unimed" in resultado["resposta"] and "SulAmérica" in resultado["resposta"]
    assert "particular" in resultado["resposta"].lower()
    assert [c["nome"] for c in resultado["convenios"]] == ["Unimed", "SulAmérica"]
    assert _salvo(svc)["dados_coletados"]["convenio_id"] is None


async def test_unidade_sem_convenios_cadastrados_aceita_o_que_o_paciente_digitar():
    svc = _servico()
    svc.redis.get = AsyncMock(return_value=_sessao("COLETANDO_CONVENIO", _dados(), convenios=[]))

    resultado = await svc.processar_mensagem("t", "Bradesco Saúde")

    assert resultado["estado"] == ChatEstado.OUVINDO_SINTOMAS
    assert _salvo(svc)["dados_coletados"]["convenio"] == "Bradesco Saúde"


# ============================================================
# CPF
# ============================================================

async def test_horario_escolhido_pede_o_cpf_antes_do_telefone():
    svc = _servico()
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.APRESENTANDO_SLOTS, _dados()))

    resultado = await svc.processar_mensagem("t", "confirmar:42")

    assert resultado["estado"] == ChatEstado.COLETANDO_CONTATO
    assert "cpf" in resultado["resposta"].lower()
    assert _salvo(svc)["dados_coletados"]["contato_step"] == "cpf"


async def test_cpf_invalido_pede_de_novo_sem_avancar():
    svc = _servico()
    svc.redis.get = AsyncMock(
        return_value=_sessao(ChatEstado.COLETANDO_CONTATO, _dados(slot_id_selecionado=42))
    )

    resultado = await svc.processar_mensagem("t", "111.111.111-11")

    assert resultado["estado"] == ChatEstado.COLETANDO_CONTATO
    assert "cpf" in resultado["resposta"].lower()
    salvos = _salvo(svc)["dados_coletados"]
    assert salvos["contato_step"] == "cpf"
    assert salvos["cpf"] is None


async def test_cpf_valido_e_guardado_e_pede_o_telefone():
    svc = _servico()
    svc.redis.get = AsyncMock(
        return_value=_sessao(ChatEstado.COLETANDO_CONTATO, _dados(slot_id_selecionado=42))
    )

    resultado = await svc.processar_mensagem("t", "529.982.247-25")

    assert "telefone" in resultado["resposta"].lower()
    salvos = _salvo(svc)["dados_coletados"]
    assert salvos["cpf"] == CPF_VALIDO
    assert salvos["contato_step"] == "telefone"


async def test_resumo_mostra_cpf_mascarado_e_convenio():
    svc = _servico()
    dados = _dados(
        slot_id_selecionado=42, contato_step="email", cpf=CPF_VALIDO, telefone="(11) 98765-4321",
        convenio_id=1, convenio="Unimed", plano_id=11, plano="Especial", tipo_atendimento="CONVENIO",
    )
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.COLETANDO_CONTATO, dados))

    resultado = await svc.processar_mensagem("t", "pedro@exemplo.com.br")

    assert resultado["estado"] == ChatEstado.CONFIRMANDO
    assert "529.XXX.XXX-25" in resultado["resposta"]
    assert CPF_VALIDO not in resultado["resposta"]
    assert "Unimed" in resultado["resposta"] and "Especial" in resultado["resposta"]


def _db_para_agendamento(db, cliente_existente=None) -> list:
    """Mocka as consultas de _processar_criar_agendamento e devolve a lista de SQLs de cliente."""
    slot = MagicMock(id=42, profissional_id=10, status="DISPONIVEL", estabelecimento_id=1)
    profissional = MagicMock(id=10, especialidade_id=4)
    consultas_cliente: list[str] = []

    def execute(stmt):
        resultado = MagicMock()
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        primeira_tabela = sql.lower().split("from ")[1].split()[0] if "from " in sql.lower() else ""
        if primeira_tabela == "slots":
            resultado.scalar_one_or_none.return_value = slot
        elif primeira_tabela == "profissionais":
            resultado.scalar_one_or_none.return_value = profissional
        elif primeira_tabela == "clientes":
            consultas_cliente.append(sql)
            resultado.scalar_one_or_none.return_value = cliente_existente
        else:
            resultado.scalar_one_or_none.return_value = None
        return resultado

    db.execute = AsyncMock(side_effect=execute)
    db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 99))
    return consultas_cliente


def _dados_prontos(**extras) -> dict:
    return _dados(
        slot_id_selecionado=42, contato_step="email", cpf=CPF_VALIDO,
        telefone="(11) 98765-4321", email="pedro@exemplo.com.br", **extras,
    )


async def test_cliente_novo_e_criado_com_cpf_real_e_convenio():
    from app.models.cliente import Cliente

    svc = _servico()
    dados = _dados_prontos(convenio_id=1, convenio="Unimed", plano="Especial", plano_id=11, tipo_atendimento="CONVENIO")
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.CONFIRMANDO, dados))
    consultas = _db_para_agendamento(svc.db)

    resultado = await svc.processar_mensagem("t", "Sim")

    assert resultado["estado"] == ChatEstado.FINALIZADO
    assert "confirmado" in resultado["resposta"].lower()
    criados = [c.args[0] for c in svc.db.add.call_args_list if isinstance(c.args[0], Cliente)]
    assert len(criados) == 1
    assert criados[0].cpf == CPF_VALIDO
    assert criados[0].convenio_id == 1
    assert criados[0].convenio == "Unimed"
    assert criados[0].modalidade_pagamento.value == "CONVENIO"
    assert f"clientes.cpf = '{CPF_VALIDO}'" in consultas[0]
    assert "clientes.estabelecimento_id = 1" in consultas[0]


async def test_cliente_ja_cadastrado_pelo_cpf_e_reaproveitado():
    from app.models.cliente import Cliente

    svc = _servico()
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.CONFIRMANDO, _dados_prontos(tipo_atendimento="PARTICULAR")))
    existente = MagicMock(id=7, email=None, telefone=None)
    _db_para_agendamento(svc.db, cliente_existente=existente)

    resultado = await svc.processar_mensagem("t", "Sim")

    assert "confirmado" in resultado["resposta"].lower()
    assert not [c for c in svc.db.add.call_args_list if isinstance(c.args[0], Cliente)]
    assert existente.telefone == "(11) 98765-4321"
    assert existente.email == "pedro@exemplo.com.br"


async def test_sem_cpf_na_sessao_volta_a_pedir_em_vez_de_gravar_placeholder():
    svc = _servico()
    dados = _dados_prontos()
    dados["cpf"] = None
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.CONFIRMANDO, dados))
    _db_para_agendamento(svc.db)

    resultado = await svc.processar_mensagem("t", "Sim")

    assert resultado["estado"] == ChatEstado.COLETANDO_CONTATO
    assert "cpf" in resultado["resposta"].lower()
    svc.db.add.assert_not_called()


# ============================================================
# Fuso horário
# ============================================================

def test_agora_local_usa_o_fuso_configurado(monkeypatch):
    from app.core import tempo

    monkeypatch.setattr(tempo.settings, "app_timezone", "Asia/Tokyo")

    esperado = datetime.now(timezone.utc) + timedelta(hours=9)
    obtido = tempo.agora_local()

    assert obtido.tzinfo is None  # ingênuo, comparável com as colunas DATE/TIME dos slots
    assert abs((obtido - esperado.replace(tzinfo=None)).total_seconds()) < 5


# ============================================================
# Carteirinha do convênio
# ============================================================

def _dados_convenio(**extras) -> dict:
    return _dados(
        slot_id_selecionado=42, convenio_id=1, convenio="Unimed", plano_id=11, plano="Especial",
        tipo_atendimento="CONVENIO", **extras,
    )


async def test_com_convenio_o_cpf_valido_leva_a_pergunta_da_carteirinha():
    svc = _servico()
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.COLETANDO_CONTATO, _dados_convenio()))

    resultado = await svc.processar_mensagem("t", CPF_VALIDO)

    assert "carteirinha" in resultado["resposta"].lower()
    assert resultado["quick_replies"] == ["Não tenho em mãos"]
    assert _salvo(svc)["dados_coletados"]["contato_step"] == "carteirinha"


async def test_particular_nao_e_perguntado_sobre_carteirinha():
    svc = _servico()
    svc.redis.get = AsyncMock(
        return_value=_sessao(ChatEstado.COLETANDO_CONTATO, _dados(slot_id_selecionado=42, tipo_atendimento="PARTICULAR"))
    )

    resultado = await svc.processar_mensagem("t", CPF_VALIDO)

    assert "carteirinha" not in resultado["resposta"].lower()
    assert _salvo(svc)["dados_coletados"]["contato_step"] == "telefone"


async def test_numero_da_carteirinha_e_guardado_e_segue_para_o_telefone():
    svc = _servico()
    dados = _dados_convenio(cpf=CPF_VALIDO, contato_step="carteirinha")
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.COLETANDO_CONTATO, dados))

    resultado = await svc.processar_mensagem("t", "0 123 456789012-3")

    assert "telefone" in resultado["resposta"].lower()
    salvos = _salvo(svc)["dados_coletados"]
    assert salvos["numero_carteirinha"] == "01234567890123"
    assert salvos["contato_step"] == "telefone"


async def test_sem_a_carteirinha_em_maos_segue_sem_numero():
    svc = _servico()
    dados = _dados_convenio(cpf=CPF_VALIDO, contato_step="carteirinha")
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.COLETANDO_CONTATO, dados))

    resultado = await svc.processar_mensagem("t", "Não tenho em mãos")

    assert "telefone" in resultado["resposta"].lower()
    salvos = _salvo(svc)["dados_coletados"]
    assert salvos["numero_carteirinha"] is None
    assert salvos["contato_step"] == "telefone"
    assert salvos["tipo_atendimento"] == "CONVENIO"


async def test_agendamento_cria_a_carteirinha_e_vincula_ao_atendimento():
    from app.models.atendimento import Atendimento
    from app.models.cliente_convenio import ClienteConvenio

    svc = _servico()
    dados = _dados_prontos(
        convenio_id=1, convenio="Unimed", plano_id=11, plano="Especial",
        tipo_atendimento="CONVENIO", numero_carteirinha="01234567890123",
    )
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.CONFIRMANDO, dados))
    _db_para_agendamento(svc.db)

    resultado = await svc.processar_mensagem("t", "Sim")

    assert "confirmado" in resultado["resposta"].lower()
    adicionados = [c.args[0] for c in svc.db.add.call_args_list]
    carteirinhas = [o for o in adicionados if isinstance(o, ClienteConvenio)]
    assert len(carteirinhas) == 1
    assert carteirinhas[0].convenio_id == 1
    assert carteirinhas[0].plano_id == 11
    assert carteirinhas[0].numero_carteirinha == "01234567890123"
    assert carteirinhas[0].nome_titular == "Pedro Henrique Oliveira"
    assert carteirinhas[0].principal is True
    atendimentos = [o for o in adicionados if isinstance(o, Atendimento)]
    assert atendimentos[0].cliente_convenio_id == 99  # id atribuído pelo refresh mockado


async def test_sem_numero_nao_cria_carteirinha():
    from app.models.cliente_convenio import ClienteConvenio

    svc = _servico()
    dados = _dados_prontos(convenio_id=1, convenio="Unimed", tipo_atendimento="CONVENIO", numero_carteirinha=None)
    svc.redis.get = AsyncMock(return_value=_sessao(ChatEstado.CONFIRMANDO, dados))
    _db_para_agendamento(svc.db)

    resultado = await svc.processar_mensagem("t", "Sim")

    assert "confirmado" in resultado["resposta"].lower()
    assert not [c for c in svc.db.add.call_args_list if isinstance(c.args[0], ClienteConvenio)]


# ============================================================
# Fuso por estabelecimento
# ============================================================

def test_agora_local_aceita_o_fuso_da_unidade(monkeypatch):
    from app.core import tempo

    manaus = tempo.agora_local("America/Manaus")
    sao_paulo = tempo.agora_local("America/Sao_Paulo")

    assert round((sao_paulo - manaus).total_seconds() / 3600) == 1


def test_fuso_invalido_cai_no_padrao_da_plataforma():
    from app.core import tempo

    assert tempo.fuso_valido("Marte/Olympus") == tempo.settings.app_timezone
    assert tempo.fuso_valido(None) == tempo.settings.app_timezone
    assert tempo.fuso_valido("America/Manaus") == "America/Manaus"


async def test_fuso_do_estabelecimento_vem_do_cadastro():
    from app.core import tempo

    db = AsyncMock()
    resultado = MagicMock()
    resultado.scalar_one_or_none.return_value = "America/Manaus"
    db.execute = AsyncMock(return_value=resultado)

    assert await tempo.fuso_do_estabelecimento(db, 3) == "America/Manaus"
    sql = str(db.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
    assert "estabelecimentos.id = 3" in sql


def test_schema_do_estabelecimento_recusa_fuso_inexistente():
    import pydantic

    from app.schemas.estabelecimento import EstabelecimentoUpdate

    assert EstabelecimentoUpdate(timezone="America/Manaus").timezone == "America/Manaus"
    with pytest.raises(pydantic.ValidationError):
        EstabelecimentoUpdate(timezone="Marte/Olympus")
