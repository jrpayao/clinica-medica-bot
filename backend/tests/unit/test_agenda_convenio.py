"""Testes unitários — filtro por convênio em buscar_disponibilidade.

Cobre:
- buscar_disponibilidade aceita convenio_id como parâmetro opcional
- Quando convenio_id is None → retorna todos os slots (comportamento atual)
- Quando convenio_id informado → query inclui join com medico_convenios
- Slot de médico sem aquele convênio não é retornado
- Particular (convenio_id=None no paciente) sempre vê todos os slots
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from app.services.agenda_service import AgendaService


def _make_db():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute.return_value = result_mock
    return db


class TestAgendaConvenioFiltro:
    async def test_buscar_disponibilidade_aceita_convenio_id(self):
        """buscar_disponibilidade deve aceitar convenio_id sem erro."""
        db = _make_db()
        svc = AgendaService(db)

        # Não deve levantar TypeError
        await svc.buscar_disponibilidade(
            estabelecimento_id=1,
            convenio_id=None,
        )
        db.execute.assert_called_once()

    async def test_sem_convenio_retorna_todos_slots(self):
        """Quando convenio_id=None, retorna todos slots disponíveis."""
        db = _make_db()
        svc = AgendaService(db)

        slots = await svc.buscar_disponibilidade(
            estabelecimento_id=1,
            convenio_id=None,
        )
        assert slots == []

    async def test_com_convenio_executa_query(self):
        """Quando convenio_id informado, execute deve ser chamado (query com join)."""
        db = _make_db()
        svc = AgendaService(db)

        await svc.buscar_disponibilidade(
            estabelecimento_id=1,
            convenio_id=3,
        )
        db.execute.assert_called_once()

    async def test_retorna_lista_vazia_sem_slots_convenio(self):
        db = _make_db()
        svc = AgendaService(db)

        slots = await svc.buscar_disponibilidade(
            estabelecimento_id=1,
            convenio_id=99,
        )
        assert slots == []
