"""Fábrica de dados para testes que usam o banco real (fixture db_session, com rollback ao final)."""

import itertools
import uuid
from datetime import date, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento, AtendimentoCanal, AtendimentoStatus, AtendimentoTipo
from app.models.cliente import Cliente
from app.models.convenio import Convenio
from app.models.especialidade import Especialidade
from app.models.estabelecimento import EstabelecimentoSaude, TipoEstabelecimento
from app.models.licenca import Licenca, LicencaStatus
from app.models.profissional import Profissional
from app.models.profissional_estabelecimento import ProfissionalEstabelecimento
from app.models.slot import Slot, SlotStatus

_seq = itertools.count(1)

# Unidades criadas pelo teste em andamento (zerado a cada teste em conftest.py)
UNIDADES_DO_TESTE: list[int] = []


async def nas_unidades_do_teste(rotina, *args, **kwargs):
    """Roda uma rotina de job só nas unidades criadas pelo teste, somando os resultados.

    O banco de desenvolvimento tem dados de demonstração; sem isto, o job os alcançaria também.
    """
    total = None
    for unidade in list(UNIDADES_DO_TESTE):
        parcial = await rotina(*args, estabelecimento_id=unidade, **kwargs)
        if total is None:
            total = parcial
        elif isinstance(parcial, dict):
            total = {chave: total[chave] + valor for chave, valor in parcial.items()}
        else:
            total += parcial
    return total


def _unico(tamanho: int) -> str:
    return str(uuid.uuid4().int)[:tamanho]


def cpf_valido() -> str:
    """CPF com dígitos verificadores corretos."""
    base = [int(c) for c in _unico(9)]
    for _ in range(2):
        soma = sum(d * p for d, p in zip(base, range(len(base) + 1, 1, -1)))
        base.append((soma * 10) % 11 % 10)
    return "".join(map(str, base))


async def criar_estabelecimento(db: AsyncSession, **campos) -> EstabelecimentoSaude:
    est = EstabelecimentoSaude(
        nome=campos.pop("nome", "Clínica Teste"),
        cnpj=_unico(14),
        slug=f"teste-{uuid.uuid4().hex[:12]}",
        tipo=TipoEstabelecimento.CLINICA,
        email=campos.pop("email", "recepcao@teste.com"),
        **campos,
    )
    db.add(est)
    await db.flush()
    UNIDADES_DO_TESTE.append(est.id)
    db.add(Licenca(estabelecimento_id=est.id, plano="pro", status=LicencaStatus.ATIVA))
    await db.flush()
    return est


def cabecalho(est: EstabelecimentoSaude, role: str = "ADMIN_ESTABELECIMENTO", **extras) -> dict:
    """Authorization de um usuario da unidade, para chamadas HTTP nos testes."""
    from app.core.security import create_access_token

    token = create_access_token({"sub": "1", "role": role, "estabelecimento_id": est.id, **extras})
    return {"Authorization": f"Bearer {token}"}


async def criar_especialidade(db: AsyncSession, est: EstabelecimentoSaude, nome="Cardiologia") -> Especialidade:
    esp = Especialidade(nome=nome, estabelecimento_id=est.id)
    db.add(esp)
    await db.flush()
    return esp


async def criar_profissional(
    db: AsyncSession, est: EstabelecimentoSaude, esp: Especialidade, nome="Dra. Ana Lima", **campos
) -> Profissional:
    prof = Profissional(
        nome=nome,
        registro_profissional=f"T{_unico(10)}",
        especialidade_id=esp.id,
        telefone=campos.pop("telefone", "11988880000"),
        email=campos.pop("email", "ana@teste.com"),
        **campos,
    )
    db.add(prof)
    await db.flush()
    db.add(ProfissionalEstabelecimento(profissional_id=prof.id, estabelecimento_id=est.id))
    await db.flush()
    return prof


async def criar_convenio(db: AsyncSession, est: EstabelecimentoSaude, nome="Unimed") -> Convenio:
    conv = Convenio(nome=nome, estabelecimento_id=est.id)
    db.add(conv)
    await db.flush()
    return conv


async def criar_cliente(db: AsyncSession, est: EstabelecimentoSaude, nome="Maria Souza", **campos) -> Cliente:
    cliente = Cliente(
        nome=nome,
        cpf=campos.pop("cpf", None) or cpf_valido(),
        telefone=campos.pop("telefone", f"119{_unico(8)}"),
        email=campos.pop("email", "maria@teste.com"),
        estabelecimento_id=est.id,
        **campos,
    )
    db.add(cliente)
    await db.flush()
    return cliente


async def criar_slot(
    db: AsyncSession,
    est: EstabelecimentoSaude,
    prof: Profissional,
    dias: int = 3,
    hora: time | None = None,
    status: SlotStatus = SlotStatus.DISPONIVEL,
    data: date | None = None,
) -> Slot:
    """Slot futuro por padrão; cada chamada sem `hora` usa um horário diferente."""
    if hora is None:
        n = next(_seq)
        hora = time(8 + (n // 2) % 10, 30 * (n % 2))
    inicio = hora
    fim = time(inicio.hour + (inicio.minute + 30) // 60, (inicio.minute + 30) % 60)
    slot = Slot(
        profissional_id=prof.id,
        data=data or (date.today() + timedelta(days=dias)),
        hora_inicio=inicio,
        hora_fim=fim,
        status=status,
        estabelecimento_id=est.id,
    )
    db.add(slot)
    await db.flush()
    return slot


async def criar_atendimento(
    db: AsyncSession,
    slot: Slot,
    cliente: Cliente,
    prof: Profissional,
    status: AtendimentoStatus = AtendimentoStatus.AGENDADA,
    **campos,
) -> Atendimento:
    slot.status = SlotStatus.AGENDADO
    atendimento = Atendimento(
        slot_id=slot.id,
        cliente_id=cliente.id,
        profissional_id=prof.id,
        especialidade_id=prof.especialidade_id,
        tipo=AtendimentoTipo.EXTERNO,
        status=status,
        canal_origem=campos.pop("canal_origem", AtendimentoCanal.PORTAL),
        estabelecimento_id=slot.estabelecimento_id,
        **campos,
    )
    db.add(atendimento)
    await db.flush()
    return atendimento


class RedisFalso:
    """Redis em memória com o subconjunto usado pelos serviços (get/set/delete)."""

    def __init__(self) -> None:
        self.dados: dict[str, str] = {}
        self.ttl: dict[str, int | None] = {}

    async def get(self, chave: str):
        return self.dados.get(chave)

    async def set(self, chave: str, valor: str, ex: int | None = None):
        self.dados[chave] = valor
        self.ttl[chave] = ex
        return True

    async def delete(self, *chaves: str):
        for chave in chaves:
            self.dados.pop(chave, None)
        return len(chaves)


class Caixa:
    """Coleta mensagens enviadas (WhatsApp ou e-mail) no lugar do provedor real."""

    def __init__(self, sucesso: bool = True) -> None:
        self.sucesso = sucesso
        self.enviadas: list[tuple] = []

    async def __call__(self, *args, **kwargs) -> bool:
        self.enviadas.append(args or tuple(kwargs.values()))
        return self.sucesso

    @property
    def textos(self) -> list[str]:
        return [str(envio[-1]) for envio in self.enviadas]
