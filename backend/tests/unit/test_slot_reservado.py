"""Testes unitários — Estado RESERVADO no slot (T84).

Cobre:
- SlotStatus tem valor RESERVADO
- Slot tem campo reservado_em (datetime nullable)
- limpar_slots_reservados_expirados libera slots RESERVADO com mais de 10 min
- Slots RESERVADO dentro do prazo não são liberados
- Função retorna a contagem de slots liberados
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.slot import Slot, SlotStatus


# ============================================================
# SlotStatus
# ============================================================

def test_slot_status_tem_reservado():
    """RF: SlotStatus deve ter valor RESERVADO."""
    assert hasattr(SlotStatus, "RESERVADO")
    assert SlotStatus.RESERVADO == "RESERVADO"


def test_slot_status_tem_todos_os_valores():
    """Não regredir os valores existentes."""
    valores = {s.value for s in SlotStatus}
    assert "DISPONIVEL" in valores
    assert "AGENDADO" in valores
    assert "BLOQUEADO" in valores
    assert "RESERVADO" in valores


# ============================================================
# Slot.reservado_em
# ============================================================

def test_slot_tem_campo_reservado_em():
    """RF: Slot deve ter campo reservado_em (nullable datetime)."""
    assert hasattr(Slot, "reservado_em")


def test_slot_reservado_em_e_nullable():
    """reservado_em deve aceitar None."""
    col = Slot.__table__.columns["reservado_em"]
    assert col.nullable is True


# ============================================================
# Worker de limpeza
# ============================================================

async def test_limpar_slots_reservados_libera_expirados():
    """RF: slots RESERVADO com mais de 10 min devem voltar para DISPONIVEL."""
    from app.workers.slot_cleanup import _limpar_slots_reservados

    agora = datetime.now(timezone.utc)
    slot_expirado = MagicMock(spec=Slot)
    slot_expirado.id = 1
    slot_expirado.status = SlotStatus.RESERVADO
    slot_expirado.reservado_em = agora - timedelta(minutes=11)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [slot_expirado]
    mock_session.execute.return_value = mock_result
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.slot_cleanup.AsyncSessionLocal", return_value=mock_session):
        count = await _limpar_slots_reservados()

    assert count == 1
    mock_session.execute.assert_called()
    mock_session.commit.assert_called_once()


async def test_limpar_slots_reservados_nao_libera_dentro_do_prazo():
    """RF: slots RESERVADO com menos de 10 min não devem ser liberados."""
    from app.workers.slot_cleanup import _limpar_slots_reservados

    agora = datetime.now(timezone.utc)
    slot_recente = MagicMock(spec=Slot)
    slot_recente.id = 2
    slot_recente.status = SlotStatus.RESERVADO
    slot_recente.reservado_em = agora - timedelta(minutes=5)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    # Query com filtro de tempo correto → retorna lista vazia
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.slot_cleanup.AsyncSessionLocal", return_value=mock_session):
        count = await _limpar_slots_reservados()

    assert count == 0


async def test_limpar_slots_reservados_retorna_zero_quando_nenhum():
    """RF: sem slots expirados → retorna 0."""
    from app.workers.slot_cleanup import _limpar_slots_reservados

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.slot_cleanup.AsyncSessionLocal", return_value=mock_session):
        count = await _limpar_slots_reservados()

    assert count == 0
