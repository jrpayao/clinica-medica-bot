"""Testes unitários — Painel do profissional/médico (G24 / T146–T147).

Cobre:
- profissional_do_token: MEDICO sempre restrito ao próprio profissional_id; demais perfis sem restrição
- Fluxo de status do profissional: só inicia e conclui o atendimento (não faz check-in nem marca falta)
- Fila do dia e mudança de status filtradas pelo profissional
- Meus pacientes: só quem já teve atendimento com o profissional na unidade, CPF mascarado
- Unidades do profissional e troca de unidade (somente onde há vínculo ativo)
- Criação de usuário MEDICO exige vínculo com um profissional da unidade
"""

from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.dependencies import profissional_do_token
from app.models.atendimento import AtendimentoStatus as S
from app.services.painel_profissional_service import (
    listar_clientes_do_profissional,
    unidades_do_profissional,
)
from app.services.recepcao_service import (
    AtendimentoNaoEncontradoError,
    TransicaoInvalidaError,
    listar_atendimentos_do_dia,
    mudar_status,
    proximas_acoes,
    transicao_permitida,
)


def _sql(mock_db, chamada: int = -1) -> str:
    stmt = mock_db.execute.call_args_list[chamada][0][0]
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


# ============================================================
# Restrição pelo token
# ============================================================

def test_medico_fica_restrito_ao_proprio_profissional():
    assert profissional_do_token({"role": "MEDICO", "profissional_id": 10}) == 10


def test_medico_sem_vinculo_e_barrado():
    with pytest.raises(HTTPException) as erro:
        profissional_do_token({"role": "MEDICO"})
    assert erro.value.status_code == 403


@pytest.mark.parametrize("role", ["RECEPCIONISTA", "ADMIN_ESTABELECIMENTO", "ADMIN_GLOBAL"])
def test_outros_perfis_nao_sao_restritos(role):
    assert profissional_do_token({"role": role, "profissional_id": 10}) is None


# ============================================================
# Fluxo de status do profissional
# ============================================================

@pytest.mark.parametrize(
    ("atual", "novo"),
    [(S.PRESENTE, S.EM_ATENDIMENTO), (S.AGUARDANDO_PROFISSIONAL, S.EM_ATENDIMENTO), (S.EM_ATENDIMENTO, S.REALIZADA)],
)
def test_profissional_inicia_e_conclui(atual, novo):
    assert transicao_permitida(atual, novo, perfil="MEDICO") is True


@pytest.mark.parametrize(
    ("atual", "novo"),
    [(S.AGENDADA, S.PRESENTE), (S.AGENDADA, S.FALTA), (S.CONFIRMADA, S.PRESENTE), (S.AGENDADA, S.EM_ATENDIMENTO)],
)
def test_profissional_nao_faz_o_trabalho_da_recepcao(atual, novo):
    assert transicao_permitida(atual, novo, perfil="MEDICO") is False


def test_acoes_oferecidas_dependem_do_perfil():
    assert proximas_acoes(S.AGENDADA, perfil="MEDICO") == []
    assert proximas_acoes(S.PRESENTE, perfil="MEDICO") == ["EM_ATENDIMENTO"]
    assert proximas_acoes(S.AGENDADA) == ["PRESENTE", "CONFIRMADA", "FALTA"]


# ============================================================
# Fila do dia do profissional
# ============================================================

async def test_fila_do_profissional_filtra_e_traz_observacoes(mock_db):
    resultado = MagicMock()
    resultado.all.return_value = [
        (42, time(9, 30), time(10, 0), "João Silva", "12345678901", None,
         "Dr. Carlos", "Cardiologia", S.PRESENTE, "ALTA", "PORTAL", "Unimed", "Dor no peito há 2 dias"),
    ]
    mock_db.execute = AsyncMock(return_value=resultado)

    itens = await listar_atendimentos_do_dia(
        mock_db, data=date(2026, 11, 19), estabelecimento_id=2, profissional_id=10, perfil="MEDICO",
    )

    assert itens[0]["observacoes"] == "Dor no peito há 2 dias"
    assert itens[0]["acoes"] == ["EM_ATENDIMENTO"]
    assert itens[0]["cliente_cpf_mascarado"] == "123.***.***-01"
    sql = _sql(mock_db)
    assert "atendimentos.profissional_id = 10" in sql
    assert "atendimentos.estabelecimento_id = 2" in sql


async def test_mudar_status_do_profissional_so_alcanca_os_proprios_atendimentos(mock_db):
    resultado = MagicMock()
    resultado.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=resultado)

    with pytest.raises(AtendimentoNaoEncontradoError):
        await mudar_status(
            mock_db, atendimento_id=42, status_novo=S.EM_ATENDIMENTO,
            estabelecimento_id=2, usuario_id=9, profissional_id=10, perfil="MEDICO",
        )

    assert "atendimentos.profissional_id = 10" in _sql(mock_db)


async def test_mudar_status_do_profissional_respeita_o_fluxo_dele(mock_db):
    atendimento = MagicMock(id=42, status=S.AGENDADA)
    resultado = MagicMock()
    resultado.scalar_one_or_none.return_value = atendimento
    mock_db.execute = AsyncMock(return_value=resultado)

    with pytest.raises(TransicaoInvalidaError):
        await mudar_status(
            mock_db, atendimento_id=42, status_novo=S.PRESENTE,
            estabelecimento_id=2, usuario_id=9, profissional_id=10, perfil="MEDICO",
        )

    assert atendimento.status == S.AGENDADA


# ============================================================
# Meus pacientes
# ============================================================

async def test_meus_pacientes_formata_e_mascara(mock_db):
    resultado = MagicMock()
    resultado.all.return_value = [
        (7, "Ana Lima", "98765432100", "11999990000", 3, date(2026, 11, 19), "Unimed"),
    ]
    mock_db.execute = AsyncMock(return_value=resultado)

    clientes = await listar_clientes_do_profissional(mock_db, profissional_id=10, estabelecimento_id=2)

    assert clientes == [{
        "cliente_id": 7,
        "nome": "Ana Lima",
        "cpf_mascarado": "987.***.***-00",
        "telefone": "11999990000",
        "total_atendimentos": 3,
        "ultimo_atendimento": "2026-11-19",
        "convenio_nome": "Unimed",
    }]
    sql = _sql(mock_db)
    assert "atendimentos.profissional_id = 10" in sql
    assert "atendimentos.estabelecimento_id = 2" in sql
    assert "CANCELADA" in sql  # cancelados não contam como paciente atendido


# ============================================================
# Unidades do profissional
# ============================================================

async def test_unidades_listam_apenas_vinculos_ativos(mock_db):
    resultado = MagicMock()
    resultado.all.return_value = [(1, "Hospital São Lucas"), (2, "Clínica Vida Saúde")]
    mock_db.execute = AsyncMock(return_value=resultado)

    unidades = await unidades_do_profissional(mock_db, profissional_id=10)

    assert unidades == [{"id": 1, "nome": "Hospital São Lucas"}, {"id": 2, "nome": "Clínica Vida Saúde"}]
    sql = _sql(mock_db)
    assert "profissional_estabelecimentos.profissional_id = 10" in sql
    assert "profissional_estabelecimentos.ativo" in sql
    assert "estabelecimentos.ativo" in sql


# ============================================================
# Usuário MEDICO precisa de vínculo
# ============================================================

def test_usuario_medico_exige_profissional():
    from app.api.v1.endpoints.admin_usuarios import UsuarioCreateSchema

    with pytest.raises(ValueError):
        UsuarioCreateSchema(nome="Dr. X", email="x@a.com", senha="Senha@123", role="MEDICO")

    ok = UsuarioCreateSchema(nome="Dr. X", email="x@a.com", senha="Senha@123", role="MEDICO", profissional_id=10)
    assert ok.profissional_id == 10


def test_usuario_recepcionista_nao_carrega_profissional():
    from app.api.v1.endpoints.admin_usuarios import UsuarioCreateSchema

    u = UsuarioCreateSchema(
        nome="Carla", email="c@a.com", senha="Senha@123", role="RECEPCIONISTA", profissional_id=10,
    )
    assert u.profissional_id is None


# ============================================================
# Rotas
# ============================================================

def test_rotas_do_painel_do_profissional_estao_registradas():
    from app.main import app

    rotas = {(r.path, tuple(sorted(r.methods))) for r in app.routes if hasattr(r, "methods")}
    for rota in [
        ("/v1/profissional/painel", ("GET",)),
        ("/v1/profissional/atendimentos/{atendimento_id}/status", ("PATCH",)),
        ("/v1/profissional/clientes", ("GET",)),
        ("/v1/profissional/unidades", ("GET",)),
        ("/v1/profissional/selecionar-unidade", ("POST",)),
    ]:
        assert rota in rotas


# ============================================================
# Endpoints existentes: MEDICO só alcança o que é dele
# ============================================================

def test_filtro_de_profissional_do_medico_ignora_o_parametro_da_url():
    from app.api.v1.endpoints.agenda import profissional_efetivo

    assert profissional_efetivo(restrito=10, pedido=33) == 10
    assert profissional_efetivo(restrito=10, pedido=None) == 10


def test_filtro_de_profissional_dos_demais_perfis_respeita_o_parametro():
    from app.api.v1.endpoints.agenda import profissional_efetivo

    assert profissional_efetivo(restrito=None, pedido=33) == 33
    assert profissional_efetivo(restrito=None, pedido=None) is None


def test_atendimento_de_outro_profissional_responde_404_para_o_medico():
    from app.api.v1.endpoints.agenda import garantir_atendimento_proprio

    alheio = MagicMock(profissional_id=33)
    with pytest.raises(HTTPException) as erro:
        garantir_atendimento_proprio(alheio, restrito=10)
    assert erro.value.status_code == 404

    garantir_atendimento_proprio(MagicMock(profissional_id=10), restrito=10)  # não levanta
    garantir_atendimento_proprio(alheio, restrito=None)                        # recepção/admin: livre


async def test_cadastro_de_clientes_e_vedado_ao_medico():
    from app.api.v1.endpoints.clientes import sem_medico

    with pytest.raises(HTTPException) as erro:
        await sem_medico({"role": "MEDICO", "profissional_id": 10})
    assert erro.value.status_code == 403

    assert (await sem_medico({"role": "RECEPCIONISTA"}))["role"] == "RECEPCIONISTA"
