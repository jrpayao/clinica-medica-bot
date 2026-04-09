"""Importa todos os models para garantir que o mapper SQLAlchemy resolva
os relacionamentos lazy (strings em relationship()).

Ordem importa: base → entidades sem FK → entidades com FK → junction tables.
"""

from app.models.base import Base, TimestampMixin
from app.models.consulta import Consulta
from app.models.convenio import Convenio
from app.models.especialidade import Especialidade
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.licenca import Licenca, LicencaStatus
from app.models.medico import Medico
from app.models.medico_estabelecimento import MedicoEstabelecimento
from app.models.paciente import Paciente
from app.models.rede_estabelecimento import RedeEstabelecimentos
from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.models.sessao_chat import SessaoChat
from app.models.sessao_historico import SessaoHistorico
from app.models.auditoria import AuditoriaAcao, TipoAuditoria
from app.models.slot import Slot
from app.models.token_usage import TokenUsage
from app.models.usuario import Usuario

__all__ = [
    "Base",
    "TimestampMixin",
    "Convenio",
    "Especialidade",
    "RedeEstabelecimentos",
    "EstabelecimentoSaude",
    "Licenca",
    "LicencaStatus",
    "Medico",
    "MedicoEstabelecimento",
    "Paciente",
    "Slot",
    "Consulta",
    "FilaEspera",
    "FilaEsperaStatus",
    "SessaoChat",
    "SessaoHistorico",
    "AuditoriaAcao",
    "TipoAuditoria",
    "TokenUsage",
    "Usuario",
]
