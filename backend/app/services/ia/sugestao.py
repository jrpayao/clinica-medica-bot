"""Servico de sugestao de especialidade baseado em sintomas.

Mapeia sintomas a especialidades e busca slots disponiveis.
RF: Apos triagem, sugerir especialidade e apresentar horarios.
"""

from datetime import date, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.especialidade import Especialidade
from app.models.medico import Medico
from app.models.slot import Slot, SlotStatus

log = structlog.get_logger(__name__)

# Mapeamento sintoma → especialidade (heuristica)
MAPA_SINTOMA_ESPECIALIDADE: dict[str, str] = {
    "cabeca": "Neurologia",
    "enxaqueca": "Neurologia",
    "tontura": "Neurologia",
    "estomago": "Gastroenterologia",
    "barriga": "Gastroenterologia",
    "nausea": "Gastroenterologia",
    "vomito": "Gastroenterologia",
    "azia": "Gastroenterologia",
    "pele": "Dermatologia",
    "mancha": "Dermatologia",
    "alergia": "Dermatologia",
    "coceira": "Dermatologia",
    "costas": "Ortopedia",
    "joelho": "Ortopedia",
    "coluna": "Ortopedia",
    "fratura": "Ortopedia",
    "osso": "Ortopedia",
    "tosse": "Pneumologia",
    "pulmao": "Pneumologia",
    "respiracao": "Pneumologia",
    "gripe": "Pneumologia",
    "coracao": "Cardiologia",
    "pressao": "Cardiologia",
    "olho": "Oftalmologia",
    "visao": "Oftalmologia",
    "ouvido": "Otorrinolaringologia",
    "garganta": "Otorrinolaringologia",
    "nariz": "Otorrinolaringologia",
    "ansiedade": "Psiquiatria",
    "depressao": "Psiquiatria",
    "insonia": "Psiquiatria",
    "urina": "Urologia",
    "rim": "Urologia",
    "menstruacao": "Ginecologia",
    "gravidez": "Ginecologia",
}

ESPECIALIDADE_DEFAULT = "Clinica Geral"
MAX_SLOTS_SUGESTAO = 3


def sugerir_especialidade(sintomas: str) -> list[str]:
    """Sugere especialidades baseado nos sintomas descritos.

    Retorna lista de especialidades relevantes (sem duplicatas).
    Se nenhuma match, retorna Clinica Geral.
    """
    texto_lower = sintomas.lower()
    especialidades: list[str] = []

    for keyword, especialidade in MAPA_SINTOMA_ESPECIALIDADE.items():
        if keyword in texto_lower and especialidade not in especialidades:
            especialidades.append(especialidade)

    if not especialidades:
        especialidades.append(ESPECIALIDADE_DEFAULT)

    log.info(
        "especialidade_sugerida",
        sintomas_len=len(sintomas),
        sugestoes=especialidades,
    )
    return especialidades


async def buscar_slots_para_sugestao(
    db: AsyncSession,
    especialidade_nome: str,
    max_slots: int = MAX_SLOTS_SUGESTAO,
) -> list[Slot]:
    """Busca slots disponiveis para a especialidade sugerida.

    Retorna no maximo `max_slots` slots mais proximos.
    """
    hoje = date.today()
    limite = hoje + timedelta(days=30)

    query = (
        select(Slot)
        .join(Medico, Slot.medico_id == Medico.id)
        .join(Especialidade, Medico.especialidade_id == Especialidade.id)
        .where(
            Slot.status == SlotStatus.DISPONIVEL,
            Slot.data >= hoje,
            Slot.data <= limite,
            Especialidade.nome == especialidade_nome,
            Medico.ativo == True,  # noqa: E712
            Especialidade.ativo == True,  # noqa: E712
        )
        .order_by(Slot.data, Slot.hora_inicio)
        .limit(max_slots)
    )

    result = await db.execute(query)
    slots = list(result.scalars().all())

    log.info(
        "slots_sugestao",
        especialidade=especialidade_nome,
        slots_encontrados=len(slots),
    )
    return slots
