"""Chat público — paciente anônimo e webhook do WhatsApp não têm JWT.

Regressão: o router de chat estava atrás de `verificar_licenca_ativa`, que exige
token. O portal recebia 401 em POST /v1/chat/sessao e o webhook era rejeitado.
A licença continua valendo, mas é checada pelo estabelecimento da sessão.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.dependencies import get_current_user, validar_licenca_do_estabelecimento
from app.api.v1.router import api_router
from app.models.licenca import Licenca, LicencaStatus


def _dependencias(dependant) -> set:
    chamadas = {dependant.call}
    for sub in dependant.dependencies:
        chamadas |= _dependencias(sub)
    return chamadas


@pytest.mark.parametrize("caminho", ["/chat/sessao", "/chat/encerrar", "/chat/webhook/whatsapp"])
def test_rotas_publicas_do_chat_nao_exigem_jwt(caminho: str):
    rota = next(r for r in api_router.routes if getattr(r, "path", None) == caminho)

    assert get_current_user not in _dependencias(rota.dependant)


def _licenca(status: LicencaStatus, expira_em_dias: int) -> Licenca:
    return Licenca(
        estabelecimento_id=1,
        plano="pro",
        status=status,
        modalidade="mensal",
        licenca_expira_em=datetime.now(UTC) + timedelta(days=expira_em_dias),
        motivo_suspensao="inadimplência",
    )


async def _validar(licenca: Licenca | None) -> Licenca:
    with patch(
        "app.services.licenca_service.LicencaService.buscar_por_estabelecimento",
        new=AsyncMock(return_value=licenca),
    ):
        return await validar_licenca_do_estabelecimento(MagicMock(), 1)


async def test_licenca_ativa_libera_o_estabelecimento():
    licenca = _licenca(LicencaStatus.ATIVA, expira_em_dias=30)

    assert await _validar(licenca) is licenca


async def test_estabelecimento_sem_licenca_recebe_402():
    with pytest.raises(HTTPException) as erro:
        await _validar(None)

    assert erro.value.status_code == 402


async def test_licenca_expirada_recebe_402():
    with pytest.raises(HTTPException) as erro:
        await _validar(_licenca(LicencaStatus.ATIVA, expira_em_dias=-1))

    assert erro.value.status_code == 402


async def test_licenca_suspensa_recebe_403():
    with pytest.raises(HTTPException) as erro:
        await _validar(_licenca(LicencaStatus.SUSPENSA, expira_em_dias=30))

    assert erro.value.status_code == 403
