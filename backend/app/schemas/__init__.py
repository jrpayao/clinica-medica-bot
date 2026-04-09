from app.schemas.atendimento import (
    AtendimentoCancelar,
    AtendimentoCreate,
    AtendimentoFiltros,
    AtendimentoOut,
    AtendimentoResumo,
    DisponibilidadeQuery,
    SlotResponse,
    TransicaoStatusRequest,
)
from app.schemas.auth import *  # noqa: F401, F403
from app.schemas.cliente import (
    ClienteBase,
    ClienteCreate,
    ClienteOut,
    ClienteUpdate,
)
from app.schemas.convenio import *  # noqa: F401, F403
from app.schemas.especialidade import *  # noqa: F401, F403
from app.schemas.estabelecimento import *  # noqa: F401, F403
from app.schemas.licenca import *  # noqa: F401, F403
from app.schemas.profissional import (
    GerarSlotsRequest,
    ProfissionalBase,
    ProfissionalCreate,
    ProfissionalOut,
    ProfissionalResponse,
    ProfissionalResumo,
    ProfissionalUpdate,
)
