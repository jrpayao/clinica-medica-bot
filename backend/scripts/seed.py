"""Script de seed do banco de dados MedBot.

Popula o banco com dados realistas para testar a jornada multi-tenant:
- 1 Rede (holding)
- 2 Estabelecimentos: Hospital São Lucas (id=1) + Clínica Vida (id=2), com licença ATIVA
- Especialidades distribuídas por estabelecimento
- Profissionais com vínculo N:N (Dr. Carlos atende em ambas as unidades)
- Slots dos próximos 7 dias úteis por estabelecimento
- Clientes separados por estabelecimento, com carteirinha de convênio
- Convênios com planos e catálogo de serviços por estabelecimento
- Atendimentos de hoje e dos próximos dias (dashboards e agenda com dados)
- Usuários internos: ADMIN_GLOBAL + admins + recepcionistas por estabelecimento

Uso:
    cd backend
    uv run python scripts/seed.py
"""
# ruff: noqa: T201, E501 — script de linha de comando: print() é a saída do resumo

import asyncio
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.atendimento import MotivoCancelamento
from app.models.avaliacao import Avaliacao, AvaliacaoCanal
from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.models.reagendamento import ReagendamentoOferta, ReagendamentoStatus
from app.services.ia.resumo_triagem import categorizar_sintomas, resumo_por_regra
from app.core.security import hash_password
from app.models import (
    Atendimento,
    AtendimentoCanal,
    AtendimentoStatus,
    AtendimentoStatusHistorico,
    AtendimentoTipo,
    AtendimentoUrgencia,
    Cliente,
    ClienteConvenio,
    Convenio,
    ConvenioPlano,
    Especialidade,
    EstabelecimentoSaude,
    Licenca,
    LicencaStatus,
    ModalidadePagamento,
    Profissional,
    ProfissionalEstabelecimento,
    RedeEstabelecimentos,
    Slot,
    SlotStatus,
    TipoAtendimento,
    TipoEstabelecimento,
    Usuario,
    UsuarioRole,
)

log = structlog.get_logger("seed")


# ============================================================
# Dados dos estabelecimentos
# ============================================================

REDE = {
    "nome": "Grupo Saúde Premium S/A",
    "cnpj_holding": "00000000000100",
}

ESTABELECIMENTO_1 = {
    "nome": "Hospital São Lucas",
    "cnpj": "11111111000101",
    "slug": "hospital-sao-lucas",
    "tipo": TipoEstabelecimento.HOSPITAL,
    "plano": "enterprise",
    "cidade": "São Paulo",
    "estado": "SP",
    "telefone": "1130001000",
    "email": "contato@hosp-sao-lucas.com",
}

ESTABELECIMENTO_2 = {
    "nome": "Clínica Vida Saúde",
    "cnpj": "22222222000102",
    "slug": "clinica-vida",
    "tipo": TipoEstabelecimento.CLINICA,
    "plano": "pro",
    "cidade": "Campinas",
    "estado": "SP",
    "telefone": "1932002000",
    "email": "contato@clinica-vida.com",
}

# ============================================================
# Especialidades — distribuídas por estabelecimento
# ============================================================

ESPECIALIDADES_EST1 = [
    {"nome": "Clínica Geral",     "cor_hex": "#4A90E2", "icone": "stethoscope", "descricao": "Atendimento geral e triagem"},
    {"nome": "Cardiologia",       "cor_hex": "#E24A4A", "icone": "heart",        "descricao": "Doenças do coração e sistema cardiovascular"},
    {"nome": "Neurologia",        "cor_hex": "#9B4AE2", "icone": "brain",        "descricao": "Doenças do sistema nervoso"},
    {"nome": "Ortopedia",         "cor_hex": "#4AE2D4", "icone": "bone",         "descricao": "Doenças do sistema musculoesquelético"},
]

ESPECIALIDADES_EST2 = [
    {"nome": "Clínica Geral",     "cor_hex": "#4A90E2", "icone": "stethoscope", "descricao": "Atendimento geral e triagem"},
    {"nome": "Dermatologia",      "cor_hex": "#E2A34A", "icone": "skin",         "descricao": "Doenças da pele, cabelo e unhas"},
    {"nome": "Gastroenterologia", "cor_hex": "#4AE27A", "icone": "stomach",      "descricao": "Doenças do sistema digestivo"},
]

# ============================================================
# Profissionais — esp_idx relativo ao estabelecimento principal
# ============================================================

# Hospital São Lucas (est1) — esp_idx relativo a ESPECIALIDADES_EST1
PROFISSIONAIS_EST1 = [
    {"nome": "Dr. Carlos Mendes",   "registro": "CRM-SP-12345", "esp_idx": 0, "email": "carlos.mendes@medbot.com",   "duracao": 30},
    {"nome": "Dra. Ana Paula Lima", "registro": "CRM-SP-23456", "esp_idx": 0, "email": "ana.lima@medbot.com",         "duracao": 30},
    {"nome": "Dr. Roberto Farias",  "registro": "CRM-SP-34567", "esp_idx": 1, "email": "roberto.farias@medbot.com",  "duracao": 45},
    {"nome": "Dr. Paulo Saraiva",   "registro": "CRM-SP-56789", "esp_idx": 2, "email": "paulo.saraiva@medbot.com",   "duracao": 45},
    {"nome": "Dr. Ricardo Nunes",   "registro": "CRM-SP-89012", "esp_idx": 3, "email": "ricardo.nunes@medbot.com",   "duracao": 40},
]

# Clínica Vida (est2) — esp_idx relativo a ESPECIALIDADES_EST2
# Dr. Carlos Mendes (PROFISSIONAIS_EST1[0]) atende em AMBAS as unidades
PROFISSIONAIS_EST2 = [
    {"nome": "Dra. Juliana Torres",  "registro": "CRM-SP-67890", "esp_idx": 1, "email": "juliana.torres@medbot.com", "duracao": 30},
    {"nome": "Dr. Fernando Alves",   "registro": "CRM-SP-78901", "esp_idx": 2, "email": "fernando.alves@medbot.com", "duracao": 40},
]

# ============================================================
# Clientes — separados por estabelecimento
# ============================================================

CLIENTES_EST1 = [
    {"nome": "João da Silva Santos",   "cpf": "12345678901", "data_nascimento": date(1985, 3, 15), "telefone": "11999990001", "email": "joao.silva@email.com",   "convenio": "Unimed"},
    {"nome": "Maria Aparecida Souza",  "cpf": "23456789012", "data_nascimento": date(1972, 7, 22), "telefone": "11999990002", "email": "maria.souza@email.com",  "convenio": "Bradesco Saúde"},
    {"nome": "Antônio Carlos Pereira", "cpf": "56789012345", "data_nascimento": date(1960, 1, 9),  "telefone": "11999990005", "email": "antonio.pereira@email.com", "convenio": "Amil"},
    {"nome": "Beatriz Martins Costa",  "cpf": "67890123456", "data_nascimento": date(1998, 9, 2),  "telefone": "11999990006", "email": "beatriz.costa@email.com", "convenio": None},
]

CLIENTES_EST2 = [
    {"nome": "Pedro Henrique Oliveira", "cpf": "34567890123", "data_nascimento": date(1995, 11, 8), "telefone": "11999990003", "email": "pedro.oliveira@email.com", "convenio": None},
    {"nome": "Camila Rodrigues Lima",   "cpf": "45678901234", "data_nascimento": date(1990, 5, 30), "telefone": "11999990004", "email": "camila.lima@email.com",    "convenio": "SulAmérica"},
    {"nome": "Luiz Fernando Barbosa",   "cpf": "78901234567", "data_nascimento": date(1981, 12, 17), "telefone": "11999990007", "email": "luiz.barbosa@email.com",  "convenio": "Unimed"},
    {"nome": "Fernanda Alves Ribeiro",  "cpf": "89012345678", "data_nascimento": date(2001, 4, 25), "telefone": "11999990008", "email": "fernanda.ribeiro@email.com", "convenio": "Amil"},
]

# ============================================================
# Convênios (com planos), catálogo de serviços e atendimentos de demo
# ============================================================

CONVENIOS = {
    "Unimed":             ["Nacional", "Estadual", "Empresarial"],
    "Bradesco Saúde":     ["Top Nacional", "Efetivo"],
    "SulAmérica":         ["Especial 100", "Exato"],
    "Amil":               ["Amil 400", "Amil 500"],
    "Porto Seguro Saúde": ["Prata", "Ouro"],
    "Hapvida":            ["Nosso Plano"],
}

# "profs" = índices na lista de profissionais da unidade
CATALOGO_EST1 = [
    {"nome": "Consulta Clínica Geral", "descricao": "Avaliação clínica inicial",            "duracao": 30, "preco": "180.00", "profs": [0, 1]},
    {"nome": "Consulta de Retorno",    "descricao": "Retorno em até 30 dias",               "duracao": 20, "preco": "0.00",   "profs": [0, 1, 2, 3, 4]},
    {"nome": "Eletrocardiograma",      "descricao": "ECG de repouso com laudo",             "duracao": 30, "preco": "120.00", "profs": [2]},
    {"nome": "Avaliação Neurológica",  "descricao": "Consulta com exame neurológico",       "duracao": 45, "preco": "320.00", "profs": [3]},
    {"nome": "Infiltração Articular",  "descricao": "Procedimento ortopédico ambulatorial", "duracao": 40, "preco": "450.00", "profs": [4]},
]

# Na Clínica: [0] Dr. Carlos (compartilhado), [1] Dra. Juliana, [2] Dr. Fernando
CATALOGO_EST2 = [
    {"nome": "Consulta Clínica Geral",     "descricao": "Avaliação clínica inicial",         "duracao": 30, "preco": "160.00", "profs": [0]},
    {"nome": "Consulta Dermatológica",     "descricao": "Avaliação de pele, cabelo e unhas", "duracao": 30, "preco": "250.00", "profs": [1]},
    {"nome": "Limpeza de Pele",            "descricao": "Procedimento estético",             "duracao": 60, "preco": "190.00", "profs": [1]},
    {"nome": "Mapeamento de Pintas",       "descricao": "Dermatoscopia digital",             "duracao": 45, "preco": "380.00", "profs": [1]},
    {"nome": "Consulta Gastroenterologia", "descricao": "Avaliação do sistema digestivo",    "duracao": 40, "preco": "280.00", "profs": [2]},
]

_S, _U, _C = AtendimentoStatus, AtendimentoUrgencia, AtendimentoCanal

# Uma lista por dia útil a partir do primeiro dia com slots: (status, urgência, canal)
ROTEIRO_ATENDIMENTOS = [
    [
        (_S.REALIZADA,      _U.BAIXA, _C.PORTAL),
        (_S.REALIZADA,      _U.MEDIA, _C.WHATSAPP),
        (_S.EM_ATENDIMENTO, _U.MEDIA, _C.PORTAL),
        (_S.PRESENTE,       _U.BAIXA, _C.INTERNO),
        (_S.CONFIRMADA,     _U.ALTA,  _C.WHATSAPP),
        (_S.CONFIRMADA,     _U.BAIXA, _C.PORTAL),
        (_S.AGENDADA,       _U.MEDIA, _C.PORTAL),
        (_S.AGENDADA,       _U.BAIXA, _C.WHATSAPP),
        (_S.CANCELADA,      _U.BAIXA, _C.PORTAL),
    ],
    [
        (_S.CONFIRMADA, _U.BAIXA, _C.PORTAL),
        (_S.AGENDADA,   _U.MEDIA, _C.WHATSAPP),
        (_S.AGENDADA,   _U.BAIXA, _C.PORTAL),
        (_S.AGENDADA,   _U.ALTA,  _C.WHATSAPP),
    ],
    [
        (_S.AGENDADA, _U.BAIXA, _C.PORTAL),
        (_S.AGENDADA, _U.MEDIA, _C.PORTAL),
    ],
]

TRIAGENS_HISTORICO = [
    ["dor de cabeça há 3 dias", "tontura leve"],
    ["febre e dor de garganta desde ontem"],
    ["tosse seca que não passa"],
    ["dor nas costas, região lombar"],
    ["quero fazer um check-up"],
    ["dor de cabeça forte e enjoo"],
    ["manchas na pele e coceira"],
    ["dor no joelho ao subir escadas"],
    ["ansiedade e insônia"],
    ["dor abdominal após refeições"],
    ["febre há dois dias"],
]

TRIAGENS = [
    ["dor de cabeça há 3 dias", "tontura leve"],
    ["manchas na pele", "coceira"],
    ["dor abdominal após refeições"],
    ["dor no joelho ao subir escadas"],
]

# ============================================================
# Usuários internos
# ============================================================

USUARIOS = [
    # ADMIN_GLOBAL — plataforma (sem estabelecimento)
    {"nome": "Admin Master",        "email": "admin@medbot.com",         "senha": "Admin@123", "role": UsuarioRole.ADMIN_GLOBAL,          "est": None},
    # Admins por estabelecimento
    {"nome": "Admin Hospital",      "email": "admin@hosp-sao-lucas.com", "senha": "Admin@123", "role": UsuarioRole.ADMIN_ESTABELECIMENTO, "est": 1},
    {"nome": "Admin Clínica",       "email": "admin@clinica-vida.com",   "senha": "Admin@123", "role": UsuarioRole.ADMIN_ESTABELECIMENTO, "est": 2},
    # Recepcionistas por estabelecimento
    {"nome": "Recepcionista Carla", "email": "carla@hosp-sao-lucas.com", "senha": "Carla@123", "role": UsuarioRole.RECEPCIONISTA,         "est": 1},
    {"nome": "Recepcionista Bruno", "email": "bruno@clinica-vida.com",   "senha": "Bruno@123", "role": UsuarioRole.RECEPCIONISTA,         "est": 2},
]


def gerar_slots(profissional_id: int, duracao_min: int, estabelecimento_id: int, dias_uteis: int = 7) -> list[Slot]:
    """Gera slots (manhã e tarde) para os próximos N dias úteis, a partir de hoje."""
    slots: list[Slot] = []
    dia = date.today()
    gerados = 0

    while gerados < dias_uteis:
        if dia.weekday() < 5:
            for inicio_turno, fim_turno in [(time(8, 0), time(12, 0)), (time(14, 0), time(18, 0))]:
                atual = datetime.combine(dia, inicio_turno)
                limite = datetime.combine(dia, fim_turno)
                while atual + timedelta(minutes=duracao_min) <= limite:
                    fim = atual + timedelta(minutes=duracao_min)
                    slots.append(Slot(
                        profissional_id=profissional_id,
                        data=dia,
                        hora_inicio=atual.time(),
                        hora_fim=fim.time(),
                        status=SlotStatus.DISPONIVEL,
                        aceita_online=inicio_turno.hour >= 14,  # tarde: presencial ou por video
                        estabelecimento_id=estabelecimento_id,
                    ))
                    atual = fim
            gerados += 1
        dia += timedelta(days=1)

    return slots


async def _criar_profissionais(
    db: AsyncSession, dados_lista: list[dict], especialidades: list[Especialidade], est_id: int
) -> list[Profissional]:
    profissionais: list[Profissional] = []
    for dados in dados_lista:
        prof = Profissional(
            nome=dados["nome"],
            registro_profissional=dados["registro"],
            especialidade_id=especialidades[dados["esp_idx"]].id,
            email=dados["email"],
            duracao_atendimento_min=dados["duracao"],
            ativo=True,
        )
        db.add(prof)
        profissionais.append(prof)
    await db.flush()

    for prof, dados in zip(profissionais, dados_lista, strict=True):
        db.add(ProfissionalEstabelecimento(
            profissional_id=prof.id,
            estabelecimento_id=est_id,
            duracao_atendimento_min=dados["duracao"],
            ativo=True,
        ))
        db.add(Usuario(
            nome=prof.nome,
            email=dados["email"],
            senha_hash=hash_password("Medico@123"),
            role=UsuarioRole.MEDICO,
            profissional_id=prof.id,
            estabelecimento_id=est_id,
            ativo=True,
        ))
    await db.flush()
    return profissionais


def _triagem(relatos: list[str], canal) -> dict | None:
    """Resumo de triagem como o chat grava. Agendamento feito pela recepção não tem triagem."""
    if canal == _C.INTERNO:
        return None
    return {
        "texto": resumo_por_regra({"sintomas": relatos}),
        "origem": "regra",
        "sintomas": relatos,
        "categorias": categorizar_sintomas(relatos),
        "historico": [],
    }


COMENTARIOS = {
    5: ["Atendimento excelente, muito atencioso.", "Fui atendido no horário.", None, None],
    4: ["Bom atendimento, só a espera foi um pouco longa.", None],
    3: ["Consulta rápida demais.", None],
    2: ["Esperei quase uma hora além do horário marcado."],
    1: ["Não consegui tirar minhas dúvidas."],
}
NOTAS = [5, 5, 5, 5, 5, 4, 4, 5, 3, 5, 4, 2, 5, 5, 1, 4, 5]


async def _criar_historico(
    db: AsyncSession, est_id: int, clientes: list[Cliente], carteirinhas: dict[int, ClienteConvenio]
) -> int:
    """Três semanas de atendimentos passados, com faltas, cancelamentos e avaliações, para os relatórios."""
    sorteio = random.Random(est_id)  # noqa: S311 — dados de demonstração, reproduzíveis
    profissionais = (await db.execute(
        select(Profissional)
        .join(ProfissionalEstabelecimento, ProfissionalEstabelecimento.profissional_id == Profissional.id)
        .where(ProfissionalEstabelecimento.estabelecimento_id == est_id)
        .order_by(Profissional.id)
    )).scalars().all()
    horarios = [time(8, 0), time(9, 0), time(10, 0), time(11, 0), time(14, 0), time(15, 0), time(16, 0)]
    desfechos = [_S.REALIZADA] * 8 + [_S.FALTA] + [_S.CANCELADA]
    origens = [MotivoCancelamento.PACIENTE, MotivoCancelamento.PACIENTE, MotivoCancelamento.MEDICO]
    canais = [_C.PORTAL, _C.PORTAL, _C.WHATSAPP, _C.INTERNO]

    total = n = 0
    dia = date.today() - timedelta(days=1)
    dias_uteis = 0
    while dias_uteis < 15:
        if dia.weekday() < 5:
            dias_uteis += 1
            for prof in profissionais:
                for hora in horarios:
                    ocupado = sorteio.random() < 0.62
                    slot = Slot(
                        profissional_id=prof.id, data=dia, hora_inicio=hora,
                        hora_fim=(datetime.combine(dia, hora) + timedelta(minutes=30)).time(),
                        status=SlotStatus.AGENDADO if ocupado else SlotStatus.DISPONIVEL,
                        estabelecimento_id=est_id,
                    )
                    db.add(slot)
                    if not ocupado:
                        continue
                    await db.flush()
                    n += 1
                    status = sorteio.choice(desfechos)
                    canal = sorteio.choice(canais)
                    cliente = clientes[n % len(clientes)]
                    carteirinha = carteirinhas.get(cliente.id)
                    quando = datetime.combine(dia, hora, tzinfo=UTC) + timedelta(hours=3, minutes=30)
                    atendimento = Atendimento(
                        slot_id=slot.id, cliente_id=cliente.id, profissional_id=prof.id,
                        especialidade_id=prof.especialidade_id,
                        tipo=AtendimentoTipo.INTERNO if canal == _C.INTERNO else AtendimentoTipo.EXTERNO,
                        status=status, urgencia=_U.BAIXA, canal_origem=canal,
                        triagem_resumo=_triagem(TRIAGENS_HISTORICO[n % len(TRIAGENS_HISTORICO)], canal),
                        cliente_convenio_id=carteirinha.id if carteirinha else None,
                        motivo_cancelamento=sorteio.choice(origens) if status == _S.CANCELADA else None,
                        estabelecimento_id=est_id,
                        created_at=quando - timedelta(days=3), updated_at=quando,
                    )
                    db.add(atendimento)
                    await db.flush()
                    db.add(AtendimentoStatusHistorico(
                        atendimento_id=atendimento.id, status_novo=status, created_at=quando,
                        observacao="Carga inicial (seed)",
                    ))
                    if status == _S.CANCELADA:
                        slot.status = SlotStatus.DISPONIVEL
                    if status == _S.REALIZADA and sorteio.random() < 0.7:
                        nota = NOTAS[(n + prof.id) % len(NOTAS)]
                        atendimento.avaliacao_solicitada_em = quando + timedelta(hours=24)
                        db.add(Avaliacao(
                            atendimento_id=atendimento.id, cliente_id=cliente.id, profissional_id=prof.id,
                            estabelecimento_id=est_id, nota=nota,
                            comentario=sorteio.choice(COMENTARIOS[nota]),
                            canal=AvaliacaoCanal.WHATSAPP, created_at=quando + timedelta(hours=26),
                        ))
                    total += 1
        dia -= timedelta(days=1)
    await db.flush()
    return total


async def _criar_fila_e_pendencias(db: AsyncSession, est_id: int, clientes: list[Cliente]) -> None:
    """Lista de espera com três pessoas e uma remarcação que pede contato da recepção."""
    especialidades = (await db.execute(
        select(Especialidade.id).where(Especialidade.estabelecimento_id == est_id).order_by(Especialidade.id)
    )).scalars().all()
    agora = datetime.now(UTC)
    for n, cliente in enumerate(clientes[:3]):
        db.add(FilaEspera(
            cliente_id=cliente.id, estabelecimento_id=est_id,
            especialidade_id=especialidades[n % len(especialidades)],
            status=FilaEsperaStatus.AGUARDANDO, created_at=agora - timedelta(days=3 - n, hours=2 * n),
        ))
    cancelado = (await db.execute(
        select(Atendimento)
        .join(Slot, Atendimento.slot_id == Slot.id)
        .where(
            Atendimento.estabelecimento_id == est_id,
            Atendimento.status == _S.CANCELADA,
            Atendimento.motivo_cancelamento == MotivoCancelamento.MEDICO,
        )
        .order_by(Slot.data.desc())
        .limit(1)
    )).scalar_one_or_none()
    if cancelado is not None:
        db.add(ReagendamentoOferta(
            atendimento_id=cancelado.id, cliente_id=cancelado.cliente_id, estabelecimento_id=est_id,
            slot_ids=[], status=ReagendamentoStatus.EXPIRADA, enviado_em=agora - timedelta(hours=5),
        ))
    await db.flush()


async def _criar_atendimentos(
    db: AsyncSession,
    est_id: int,
    clientes: list[Cliente],
    carteirinhas: dict[int, ClienteConvenio],
) -> int:
    """Cria atendimentos espalhados ao longo dos primeiros dias com slots."""
    slots = (await db.execute(
        select(Slot)
        .where(Slot.estabelecimento_id == est_id)
        .order_by(Slot.data, Slot.hora_inicio, Slot.profissional_id)
    )).scalars().all()
    especialidade_por_prof = dict((await db.execute(
        select(Profissional.id, Profissional.especialidade_id)
    )).all())
    dias = sorted({s.data for s in slots})

    total = 0
    for dia, roteiro in zip(dias, ROTEIRO_ATENDIMENTOS, strict=False):
        do_dia = [s for s in slots if s.data == dia]
        passo = max(len(do_dia) // (len(roteiro) + 1), 1)
        for n, (status, urgencia, canal) in enumerate(roteiro):
            slot = do_dia[min(n * passo, len(do_dia) - 1)]
            cliente = clientes[n % len(clientes)]
            carteirinha = carteirinhas.get(cliente.id)
            atendimento = Atendimento(
                slot_id=slot.id,
                cliente_id=cliente.id,
                profissional_id=slot.profissional_id,
                especialidade_id=especialidade_por_prof[slot.profissional_id],
                tipo=AtendimentoTipo.INTERNO if canal == _C.INTERNO else AtendimentoTipo.EXTERNO,
                status=status,
                urgencia=urgencia,
                canal_origem=canal,
                triagem_resumo=_triagem(TRIAGENS[n % len(TRIAGENS)], canal),
                cliente_convenio_id=carteirinha.id if carteirinha else None,
                estabelecimento_id=est_id,
            )
            db.add(atendimento)
            await db.flush()
            db.add(AtendimentoStatusHistorico(
                atendimento_id=atendimento.id,
                status_anterior=None,
                status_novo=status,
                observacao="Carga inicial (seed)",
            ))
            if status != _S.CANCELADA:
                slot.status = SlotStatus.AGENDADO
            total += 1
    await db.flush()
    return total


async def seed(db: AsyncSession) -> None:
    log.info("seed_iniciando")

    # ── 0. Limpar todas as tabelas de domínio ───────────────
    tabelas = (await db.execute(text(
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
    ))).scalars().all()
    await db.execute(text(
        f"TRUNCATE TABLE {', '.join(tabelas)} RESTART IDENTITY CASCADE"  # noqa: S608
    ))
    await db.commit()
    log.info("seed_banco_limpo", tabelas=len(tabelas))

    # ── 1. Rede + estabelecimentos + licenças ───────────────
    rede = RedeEstabelecimentos(**REDE, ativo=True)
    db.add(rede)
    await db.flush()

    est1 = EstabelecimentoSaude(**ESTABELECIMENTO_1, ativo=True, rede_id=rede.id)
    est2 = EstabelecimentoSaude(**ESTABELECIMENTO_2, ativo=True, rede_id=rede.id)
    db.add_all([est1, est2])
    await db.flush()

    # Sem licença válida as rotas de domínio respondem 402
    agora = datetime.now(UTC)
    db.add_all([
        Licenca(
            estabelecimento_id=est1.id, plano="enterprise", status=LicencaStatus.ATIVA,
            modalidade="anual", licenca_expira_em=agora + timedelta(days=300),
        ),
        Licenca(
            estabelecimento_id=est2.id, plano="pro", status=LicencaStatus.ATIVA,
            modalidade="mensal", licenca_expira_em=agora + timedelta(days=24),
        ),
    ])
    await db.flush()
    log.info("seed_estabelecimentos", est1=est1.nome, est2=est2.nome)

    # ── 2. Especialidades ───────────────────────────────────
    esps_est1 = [Especialidade(**d, estabelecimento_id=est1.id, ativo=True) for d in ESPECIALIDADES_EST1]
    esps_est2 = [Especialidade(**d, estabelecimento_id=est2.id, ativo=True) for d in ESPECIALIDADES_EST2]
    db.add_all(esps_est1 + esps_est2)
    await db.flush()

    # ── 3. Profissionais (+ vínculo + usuário de login) ─────
    profs_est1 = await _criar_profissionais(db, PROFISSIONAIS_EST1, esps_est1, est1.id)
    profs_est2 = await _criar_profissionais(db, PROFISSIONAIS_EST2, esps_est2, est2.id)

    # Dr. Carlos Mendes também atende na Clínica Vida
    carlos = profs_est1[0]
    db.add(ProfissionalEstabelecimento(
        profissional_id=carlos.id, estabelecimento_id=est2.id,
        duracao_atendimento_min=30, ativo=True,
    ))
    profs_clinica = [carlos, *profs_est2]
    await db.flush()
    log.info("seed_profissionais", est1=len(profs_est1), est2=len(profs_est2), compartilhados=1)

    # ── 4. Slots ────────────────────────────────────────────
    slots: list[Slot] = []
    for prof, dados in zip(profs_est1, PROFISSIONAIS_EST1, strict=True):
        slots += gerar_slots(prof.id, dados["duracao"], est1.id)
    for prof, dados in zip(profs_est2, PROFISSIONAIS_EST2, strict=True):
        slots += gerar_slots(prof.id, dados["duracao"], est2.id)
    slots += gerar_slots(carlos.id, 30, est2.id)
    db.add_all(slots)
    await db.flush()
    log.info("seed_slots", total=len(slots))

    # ── 5. Convênios com planos ─────────────────────────────
    convenios: dict[int, dict[str, Convenio]] = {est1.id: {}, est2.id: {}}
    for nome, planos in CONVENIOS.items():
        for est in (est1, est2):
            conv = Convenio(nome=nome, ativo=True, estabelecimento_id=est.id)
            conv.planos = [ConvenioPlano(nome=p, ativo=True) for p in planos]
            db.add(conv)
            convenios[est.id][nome] = conv
    await db.flush()

    # ── 6. Clientes + carteirinha principal ─────────────────
    clientes_est1 = [Cliente(**d, estabelecimento_id=est1.id, ativo=True) for d in CLIENTES_EST1]
    clientes_est2 = [Cliente(**d, estabelecimento_id=est2.id, ativo=True) for d in CLIENTES_EST2]
    db.add_all(clientes_est1 + clientes_est2)
    await db.flush()

    carteirinhas: dict[int, ClienteConvenio] = {}
    for idx, cliente in enumerate(clientes_est1 + clientes_est2):
        if not cliente.convenio:
            cliente.modalidade_pagamento = ModalidadePagamento.PARTICULAR
            continue
        conv = convenios[cliente.estabelecimento_id][cliente.convenio]
        cliente.convenio_id = conv.id
        cliente.modalidade_pagamento = ModalidadePagamento.CONVENIO
        carteirinha = ClienteConvenio(
            cliente_id=cliente.id,
            convenio_id=conv.id,
            plano_id=conv.planos[0].id,
            numero_carteirinha=f"{880000 + idx}-{cliente.cpf[-4:]}",
            nome_titular=cliente.nome,
            principal=True,
            ativo=True,
        )
        db.add(carteirinha)
        carteirinhas[cliente.id] = carteirinha
    await db.flush()
    log.info("seed_clientes", est1=len(clientes_est1), est2=len(clientes_est2))

    # ── 7. Catálogo de serviços + vínculos com profissionais ─
    for est, itens, profs in ((est1, CATALOGO_EST1, profs_est1), (est2, CATALOGO_EST2, profs_clinica)):
        for item in itens:
            tipo = TipoAtendimento(
                estabelecimento_id=est.id,
                nome=item["nome"],
                descricao=item["descricao"],
                duracao_min=item["duracao"],
                preco=Decimal(item["preco"]),
                ativo=True,
            )
            tipo.profissionais = [profs[i] for i in item["profs"]]
            db.add(tipo)
    await db.flush()

    # ── 8. Atendimentos de demo ─────────────────────────────
    total_atendimentos = await _criar_atendimentos(db, est1.id, clientes_est1, carteirinhas)
    total_atendimentos += await _criar_atendimentos(db, est2.id, clientes_est2, carteirinhas)
    for est, lista in ((est1, clientes_est1), (est2, clientes_est2)):
        total_atendimentos += await _criar_historico(db, est.id, lista, carteirinhas)
        await _criar_fila_e_pendencias(db, est.id, lista)
    log.info("seed_atendimentos", total=total_atendimentos)

    # ── 9. Usuários internos ────────────────────────────────
    est_ids = {None: None, 1: est1.id, 2: est2.id}
    for dados in USUARIOS:
        db.add(Usuario(
            nome=dados["nome"],
            email=dados["email"],
            senha_hash=hash_password(dados["senha"]),
            role=dados["role"],
            estabelecimento_id=est_ids[dados["est"]],
            ativo=True,
        ))

    await db.commit()
    log.info("seed_concluido")

    # ── Resumo ──────────────────────────────────────────────
    sep = "=" * 65
    print(f"\n{sep}")
    print("  SEED CONCLUIDO COM SUCESSO — Multi-tenant MedBot")
    print(sep)
    print(f"\n  REDE: {rede.nome} (CNPJ: {rede.cnpj_holding})")

    for est, esps, profs, clientes in (
        (est1, esps_est1, profs_est1, clientes_est1),
        (est2, esps_est2, profs_clinica, clientes_est2),
    ):
        print(f"\n  {est.nome} [id={est.id}] [{est.tipo.value}] — licença ATIVA ({est.plano})")
        print(f"    Especialidades ({len(esps)}): {', '.join(e.nome for e in esps)}")
        print(f"    Profissionais ({len(profs)}): {', '.join(p.nome for p in profs)}")
        print(f"    Clientes ({len(clientes)}): {', '.join(c.nome for c in clientes)}")

    print(f"\n  SLOTS: {len(slots)} | ATENDIMENTOS: {total_atendimentos} | CONVENIOS: {len(CONVENIOS) * 2}")

    print("\n  LOGINS:")
    print("    [ADMIN_GLOBAL]  admin@medbot.com         / Admin@123")
    print("    [ADMIN_EST1]    admin@hosp-sao-lucas.com / Admin@123")
    print("    [ADMIN_EST2]    admin@clinica-vida.com   / Admin@123")
    print("    [RECEP_EST1]    carla@hosp-sao-lucas.com / Carla@123")
    print("    [RECEP_EST2]    bruno@clinica-vida.com   / Bruno@123")
    print("    [MEDICO]        e-mail do profissional   / Medico@123")

    print("\n  CLIENTES (login por CPF + SMS — codigo fica no Redis):")
    for cliente in clientes_est1 + clientes_est2:
        est_nome = est1.nome if cliente.estabelecimento_id == est1.id else est2.nome
        print(f"    CPF: {cliente.cpf} ({cliente.nome[:22]}) — {est_nome}")

    print(f"\n{sep}\n")


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
