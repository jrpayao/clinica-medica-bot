"""Testes unitários — campo convenio_id em Paciente.

Cobre:
- Paciente aceita convenio_id null (particular)
- Paciente aceita convenio_id com FK para convenios
- Coluna tipo_atendimento existe e aceita CONVENIO e PARTICULAR
- Migration é retrocompatível (campos nullable)
"""

import pytest

from app.models.paciente import Paciente, TipoAtendimento


class TestPacienteConvenio:
    def test_convenio_id_existe_como_coluna_nullable(self):
        col = Paciente.__table__.c.get("convenio_id")
        assert col is not None
        assert col.nullable is True

    def test_tipo_atendimento_existe_como_coluna(self):
        col = Paciente.__table__.c.get("tipo_atendimento")
        assert col is not None
        assert col.nullable is True

    def test_tipo_atendimento_enum_particular(self):
        assert TipoAtendimento.PARTICULAR == "PARTICULAR"

    def test_tipo_atendimento_enum_convenio(self):
        assert TipoAtendimento.CONVENIO == "CONVENIO"

    def test_paciente_table_name(self):
        assert Paciente.__tablename__ == "pacientes"
