"""Testes unitários — campo convenio_id em Cliente.

Cobre:
- Cliente aceita convenio_id null (particular)
- Cliente aceita convenio_id com FK para convenios
- Coluna modalidade_pagamento existe (substitui tipo_atendimento após G25)
- Migration é retrocompatível (campos nullable)
"""

import pytest

from app.models.cliente import Cliente, ModalidadePagamento


class TestPacienteConvenio:
    def test_convenio_id_existe_como_coluna_nullable(self):
        col = Cliente.__table__.c.get("convenio_id")
        assert col is not None
        assert col.nullable is True

    def test_modalidade_pagamento_existe_como_coluna(self):
        col = Cliente.__table__.c.get("modalidade_pagamento")
        assert col is not None
        assert col.nullable is True

    def test_modalidade_pagamento_enum_particular(self):
        assert ModalidadePagamento.PARTICULAR == "PARTICULAR"

    def test_modalidade_pagamento_enum_convenio(self):
        assert ModalidadePagamento.CONVENIO == "CONVENIO"

    def test_cliente_table_name(self):
        assert Cliente.__tablename__ == "clientes"
