"""Testes unitários — AuditoriaService (T132)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.auditoria import TipoAuditoria
from app.services.auditoria_service import AuditoriaService


@pytest.fixture
def mock_db():
    return AsyncMock()


async def test_registrar_salva_evento(mock_db):
    """registrar() deve chamar db.add() e db.flush() com os dados corretos."""
    service = AuditoriaService(mock_db)

    await service.registrar(
        acao=TipoAuditoria.LOGIN,
        usuario_id=1,
        usuario_role="ADMIN_GLOBAL",
        estabelecimento_id=None,
        entidade=None,
        entidade_id=None,
        detalhes=None,
        ip_origem="127.0.0.1",
    )

    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()
    evento = mock_db.add.call_args[0][0]
    assert evento.acao == TipoAuditoria.LOGIN
    assert evento.usuario_id == 1
    assert evento.usuario_role == "ADMIN_GLOBAL"
    assert evento.ip_origem == "127.0.0.1"


async def test_registrar_nao_propaga_excecao(mock_db):
    """registrar() deve absorver exceções — nunca quebrar o fluxo principal."""
    mock_db.add.side_effect = Exception("db error")
    service = AuditoriaService(mock_db)

    # Não deve levantar exceção
    await service.registrar(
        acao=TipoAuditoria.ACESSO_CLINICA,
        usuario_id=1,
        usuario_role="ADMIN_GLOBAL",
        estabelecimento_id=5,
        entidade=None,
        entidade_id=None,
        detalhes=None,
        ip_origem=None,
    )


async def test_listar_retorna_eventos(mock_db):
    """listar() deve executar query e retornar lista de AuditoriaAcao."""
    from app.models.auditoria import AuditoriaAcao

    evento = MagicMock(spec=AuditoriaAcao)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [evento]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = AuditoriaService(mock_db)
    resultado = await service.listar(limit=10, offset=0)

    assert len(resultado) == 1
    assert resultado[0] is evento
