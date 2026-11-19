"""A auditoria precisa ser alimentada pelas ações sensíveis do ADMIN_GLOBAL.

Regressão: `AuditoriaService.registrar` nunca era chamado, então a tela de
Auditoria ficava sempre vazia.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.models.auditoria import TipoAuditoria

_ADMIN = {"sub": "1", "role": "ADMIN_GLOBAL", "email": "admin@medbot.com"}


def _request(ip: str = "10.0.0.7") -> MagicMock:
    request = MagicMock()
    request.client.host = ip
    return request


async def test_entrar_em_uma_clinica_registra_acesso():
    from app.api.v1.endpoints.estabelecimentos import (
        SelecionarEstabelecimentoSchema,
        selecionar_estabelecimento,
    )

    est = MagicMock(ativo=True)
    est.nome = "Clínica Vida Saúde"
    with (
        patch(
            "app.api.v1.endpoints.estabelecimentos.EstabelecimentoService.buscar_por_id",
            new=AsyncMock(return_value=est),
        ),
        patch(
            "app.services.auditoria_service.AuditoriaService.registrar", new=AsyncMock()
        ) as registrar,
    ):
        await selecionar_estabelecimento(
            dados=SelecionarEstabelecimentoSchema(estabelecimento_id=2),
            request=_request(),
            db=AsyncMock(),
            current_user=_ADMIN,
        )

    registrar.assert_awaited_once()
    evento = registrar.await_args.kwargs
    assert evento["acao"] == TipoAuditoria.ACESSO_CLINICA
    assert evento["estabelecimento_id"] == 2
    assert evento["usuario_id"] == 1
    assert evento["ip_origem"] == "10.0.0.7"


async def test_alterar_licenca_registra_evento():
    from app.api.v1.endpoints.licenca import gerenciar_licenca
    from app.models.licenca import LicencaStatus
    from app.schemas.licenca import AdminLicencaUpdate

    licenca = MagicMock(id=9, plano="pro", status=LicencaStatus.SUSPENSA)
    svc = "app.api.v1.endpoints.licenca.LicencaService"
    with (
        patch(f"{svc}.suspender", new=AsyncMock(return_value=licenca)),
        patch(f"{svc}.contar_medicos_ativos", new=AsyncMock(return_value=1)),
        patch(f"{svc}.contar_consultas_mes", new=AsyncMock(return_value=1)),
        patch(f"{svc}.calcular_dias_restantes", return_value=10),
        patch("app.api.v1.endpoints.licenca.LicencaResponse.model_validate", return_value=MagicMock()),
        patch(
            "app.services.auditoria_service.AuditoriaService.registrar", new=AsyncMock()
        ) as registrar,
    ):
        await gerenciar_licenca(
            estabelecimento_id=2,
            dados=AdminLicencaUpdate(status=LicencaStatus.SUSPENSA, motivo_suspensao="inadimplência"),
            request=_request(),
            current_user=_ADMIN,
            db=AsyncMock(),
        )

    registrar.assert_awaited_once()
    evento = registrar.await_args.kwargs
    assert evento["acao"] == TipoAuditoria.LICENCA_ALTERADA
    assert evento["estabelecimento_id"] == 2
    assert evento["entidade"] == "licenca"
