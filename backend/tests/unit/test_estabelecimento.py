"""Testes TDAD para EstabelecimentoSaude, RedeEstabelecimentos e MedicoEstabelecimento.

Ciclo RED → GREEN:
  Estes testes são escritos ANTES da implementação (RED).
  Os models e services serão criados para fazê-los passar (GREEN).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.estabelecimento import EstabelecimentoSaude, TipoEstabelecimento
from app.models.medico_estabelecimento import MedicoEstabelecimento
from app.models.rede_estabelecimento import RedeEstabelecimentos
from app.schemas.estabelecimento import (
    EstabelecimentoCreate,
    EstabelecimentoResponse,
    EstabelecimentoUpdate,
)
from app.services.estabelecimento_service import EstabelecimentoService


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def service(mock_db: AsyncMock) -> EstabelecimentoService:
    return EstabelecimentoService(mock_db)


def _make_estabelecimento(**kwargs) -> EstabelecimentoSaude:
    defaults = {
        "id": 1,
        "nome": "Hospital São Lucas",
        "cnpj": "12345678000100",
        "slug": "hospital-sao-lucas",
        "tipo": TipoEstabelecimento.HOSPITAL,
        "plano": "pro",
        "ativo": True,
    }
    defaults.update(kwargs)
    est = EstabelecimentoSaude(**{k: v for k, v in defaults.items() if k != "id"})
    est.id = defaults["id"]
    return est


# ============================================================
# T57-A: TipoEstabelecimento enum
# ============================================================


def test_tipo_estabelecimento_tem_todos_os_valores() -> None:
    """Enum deve conter todos os tipos previstos no domínio."""
    tipos = {t.value for t in TipoEstabelecimento}
    assert "HOSPITAL" in tipos
    assert "CLINICA" in tipos
    assert "UBS" in tipos
    assert "LABORATORIO" in tipos
    assert "POSTO_SAUDE" in tipos
    assert "OUTRO" in tipos


def test_tipo_estabelecimento_e_str_enum() -> None:
    """TipoEstabelecimento deve ser StrEnum para serialização automática."""
    assert TipoEstabelecimento.HOSPITAL == "HOSPITAL"
    assert TipoEstabelecimento.CLINICA == "CLINICA"


# ============================================================
# T57-B: Model EstabelecimentoSaude
# ============================================================


def test_model_tem_tablename_correto() -> None:
    """Tabela deve ser 'estabelecimentos'."""
    assert EstabelecimentoSaude.__tablename__ == "estabelecimentos"


def test_model_instancia_com_campos_obrigatorios() -> None:
    """Model deve instanciar com nome, cnpj, slug e tipo.

    Nota: `ativo` default=True aplica-se no INSERT (server-side),
    não na instanciação Python pura. Passamos explicitamente no teste.
    """
    est = EstabelecimentoSaude(
        nome="Clínica Vida",
        cnpj="98765432000199",
        slug="clinica-vida",
        tipo=TipoEstabelecimento.CLINICA,
        plano="basico",
        ativo=True,
    )
    assert est.nome == "Clínica Vida"
    assert est.tipo == TipoEstabelecimento.CLINICA
    assert est.ativo is True


# ============================================================
# T57-C: Schemas Pydantic v2
# ============================================================


def test_schema_create_valida_cnpj_formato() -> None:
    """EstabelecimentoCreate deve aceitar CNPJ com 14 dígitos."""
    dados = EstabelecimentoCreate(
        nome="Hospital Teste",
        cnpj="12345678000100",
        slug="hospital-teste",
        tipo=TipoEstabelecimento.HOSPITAL,
        plano="basico",
    )
    assert dados.cnpj == "12345678000100"


def test_schema_create_rejeita_cnpj_invalido() -> None:
    """CNPJ com menos de 14 dígitos deve gerar ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EstabelecimentoCreate(
            nome="Teste",
            cnpj="123",
            slug="teste",
            tipo=TipoEstabelecimento.CLINICA,
            plano="basico",
        )


def test_schema_response_tem_id_e_ativo() -> None:
    """EstabelecimentoResponse deve incluir id e ativo."""
    resp = EstabelecimentoResponse(
        id=1,
        nome="Hospital São Lucas",
        cnpj="12345678000100",
        slug="hospital-sao-lucas",
        tipo=TipoEstabelecimento.HOSPITAL,
        plano="pro",
        ativo=True,
        created_at=__import__("datetime").datetime.now(),
    )
    assert resp.id == 1
    assert resp.ativo is True


def test_schema_update_todos_campos_opcionais() -> None:
    """EstabelecimentoUpdate deve funcionar com dict vazio."""
    update = EstabelecimentoUpdate()
    assert update.nome is None
    assert update.plano is None
    assert update.ativo is None


# ============================================================
# T57-D: EstabelecimentoService
# ============================================================


async def test_criar_estabelecimento_persiste_no_banco(
    service: EstabelecimentoService,
    mock_db: AsyncMock,
) -> None:
    """Criar deve chamar db.add() e db.flush()."""
    dados = EstabelecimentoCreate(
        nome="UBS Central",
        cnpj="11222333000144",
        slug="ubs-central",
        tipo=TipoEstabelecimento.UBS,
        plano="basico",
    )
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 10)

    resultado = await service.criar(dados)

    assert mock_db.add.call_count >= 1  # estabelecimento + licença trial
    assert mock_db.flush.call_count >= 1
    assert resultado.nome == "UBS Central"
    assert resultado.tipo == TipoEstabelecimento.UBS


async def test_listar_retorna_apenas_ativos(
    service: EstabelecimentoService,
    mock_db: AsyncMock,
) -> None:
    """listar() deve retornar apenas estabelecimentos ativo=True."""
    est1 = _make_estabelecimento(id=1, nome="Hospital A", ativo=True)
    est2 = _make_estabelecimento(id=2, nome="Clínica B", tipo=TipoEstabelecimento.CLINICA)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [est1, est2]
    mock_db.execute.return_value = mock_result

    resultado = await service.listar()

    assert len(resultado) == 2
    mock_db.execute.assert_called_once()


async def test_buscar_por_id_existente_retorna_estabelecimento(
    service: EstabelecimentoService,
    mock_db: AsyncMock,
) -> None:
    """buscar_por_id com ID existente deve retornar o objeto."""
    est = _make_estabelecimento(id=5, nome="Laboratório Central")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = est
    mock_db.execute.return_value = mock_result

    resultado = await service.buscar_por_id(5)

    assert resultado is not None
    assert resultado.id == 5


async def test_buscar_por_id_inexistente_retorna_none(
    service: EstabelecimentoService,
    mock_db: AsyncMock,
) -> None:
    """buscar_por_id com ID inexistente deve retornar None."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    resultado = await service.buscar_por_id(999)

    assert resultado is None


async def test_desativar_estabelecimento_seta_ativo_false(
    service: EstabelecimentoService,
    mock_db: AsyncMock,
) -> None:
    """desativar() deve setar ativo=False no estabelecimento."""
    est = _make_estabelecimento(id=3, ativo=True)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = est
    mock_db.execute.return_value = mock_result

    resultado = await service.desativar(3)

    assert resultado is not None
    assert resultado.ativo is False
    mock_db.flush.assert_called_once()


# ============================================================
# T57-E: RedeEstabelecimentos
# ============================================================


def test_rede_tem_tablename_correto() -> None:
    """Tabela deve ser 'redes_estabelecimentos'."""
    assert RedeEstabelecimentos.__tablename__ == "redes_estabelecimentos"


def test_rede_instancia_com_nome() -> None:
    """RedeEstabelecimentos deve instanciar apenas com nome."""
    rede = RedeEstabelecimentos(nome="Clínica Vida S/A")
    assert rede.nome == "Clínica Vida S/A"
    assert rede.cnpj_holding is None  # holding opcional


def test_estabelecimento_aceita_rede_id_nulo() -> None:
    """Estabelecimento sem rede é permitido (rede_id nullable)."""
    est = EstabelecimentoSaude(
        nome="Clínica Solo",
        cnpj="11111111000100",
        slug="clinica-solo",
        tipo=TipoEstabelecimento.CLINICA,
        plano="basico",
        ativo=True,
    )
    assert est.rede_id is None


def test_estabelecimento_aceita_rede_id_preenchido() -> None:
    """Estabelecimento com rede deve aceitar rede_id."""
    est = EstabelecimentoSaude(
        nome="Clínica Vida Asa Sul",
        cnpj="22222222000100",
        slug="clinica-vida-asa-sul",
        tipo=TipoEstabelecimento.CLINICA,
        plano="pro",
        ativo=True,
        rede_id=1,
    )
    assert est.rede_id == 1


# ============================================================
# T57-F: MedicoEstabelecimento (junction N:N)
# ============================================================


def test_medico_estabelecimento_tem_tablename_correto() -> None:
    """Tabela deve ser 'medico_estabelecimentos'."""
    assert MedicoEstabelecimento.__tablename__ == "medico_estabelecimentos"


def test_medico_estabelecimento_instancia_com_ids() -> None:
    """Junction deve aceitar medico_id, estabelecimento_id e duracao."""
    vinculo = MedicoEstabelecimento(
        medico_id=1,
        estabelecimento_id=2,
        duracao_consulta_min=45,
        ativo=True,
    )
    assert vinculo.medico_id == 1
    assert vinculo.estabelecimento_id == 2
    assert vinculo.duracao_consulta_min == 45


def test_medico_estabelecimento_tem_unique_constraint() -> None:
    """Deve existir UniqueConstraint em (medico_id, estabelecimento_id)."""
    constraints = {c.name for c in MedicoEstabelecimento.__table__.constraints}
    assert "uq_medico_estabelecimento" in constraints


def test_medico_pode_ter_duracao_diferente_por_unidade() -> None:
    """O mesmo médico pode ter 30min na unidade A e 45min na unidade B."""
    vinculo_asa_sul = MedicoEstabelecimento(
        medico_id=1,
        estabelecimento_id=1,
        duracao_consulta_min=30,
        ativo=True,
    )
    vinculo_asa_norte = MedicoEstabelecimento(
        medico_id=1,
        estabelecimento_id=2,
        duracao_consulta_min=45,
        ativo=True,
    )
    assert vinculo_asa_sul.duracao_consulta_min != vinculo_asa_norte.duracao_consulta_min
