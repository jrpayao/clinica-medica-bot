"""Importa todos os models para garantir que o mapper SQLAlchemy resolva
os relacionamentos lazy (strings em relationship()).

Ordem importa: base → entidades sem FK → entidades com FK → junction tables.
"""

from app.models.atendimento import (
    Atendimento,
    AtendimentoCanal,
    AtendimentoStatus,
    AtendimentoTipo,
    AtendimentoUrgencia,
)
from app.models.atendimento_historico import AtendimentoStatusHistorico
from app.models.auditoria import AuditoriaAcao, TipoAuditoria
from app.models.base import Base, TimestampMixin
from app.models.cliente import Cliente, ModalidadePagamento
from app.models.cliente_convenio import ClienteConvenio
from app.models.convenio import Convenio
from app.models.convenio_plano import ConvenioPlano
from app.models.especialidade import Especialidade
from app.models.estabelecimento import EstabelecimentoSaude, TipoEstabelecimento
from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.models.licenca import Licenca, LicencaStatus
from app.models.profissional import Profissional
from app.models.profissional_estabelecimento import ProfissionalEstabelecimento
from app.models.rede_estabelecimento import RedeEstabelecimentos
from app.models.sessao_chat import SessaoChat
from app.models.sessao_historico import SessaoHistorico
from app.models.slot import Slot, SlotStatus
from app.models.tipo_atendimento import TipoAtendimento, profissional_tipo_atendimentos
from app.models.token_usage import TokenUsage
from app.models.usuario import Usuario, UsuarioRole

__all__ = [
    "Atendimento",
    "AtendimentoCanal",
    "AtendimentoStatus",
    "AtendimentoTipo",
    "AtendimentoUrgencia",
    "AtendimentoStatusHistorico",
    "AuditoriaAcao",
    "TipoAuditoria",
    "Base",
    "TimestampMixin",
    "Cliente",
    "ModalidadePagamento",
    "ClienteConvenio",
    "Convenio",
    "ConvenioPlano",
    "Especialidade",
    "EstabelecimentoSaude",
    "TipoEstabelecimento",
    "FilaEspera",
    "FilaEsperaStatus",
    "Licenca",
    "LicencaStatus",
    "Profissional",
    "ProfissionalEstabelecimento",
    "RedeEstabelecimentos",
    "SessaoChat",
    "SessaoHistorico",
    "Slot",
    "SlotStatus",
    "TipoAtendimento",
    "TokenUsage",
    "Usuario",
    "UsuarioRole",
]
