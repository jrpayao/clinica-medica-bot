"""Script de seed do banco de dados MedBot.

Popula o banco com dados realistas para testar a jornada multi-tenant:
- 1 Rede (holding)
- 2 Estabelecimentos: Hospital São Lucas (id=1) + Clínica Vida (id=2)
- Especialidades distribuídas por estabelecimento
- Médicos com vínculo N:N (Dr. Carlos atende em ambas as unidades)
- Slots dos próximos 7 dias úteis por estabelecimento
- Pacientes separados por estabelecimento
- Usuários internos: ADMIN_GLOBAL + admins + recepcionistas por estabelecimento

Uso:
    cd backend
    uv run python scripts/seed.py
"""

import asyncio
import sys
from datetime import date, datetime, time, timedelta

import structlog

sys.path.insert(0, "/home/payao/projetos/chatbot-ai-medical/backend")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.models.convenio import Convenio
from app.models.especialidade import Especialidade
from app.models.estabelecimento import EstabelecimentoSaude, TipoEstabelecimento
from app.models.medico import Medico
from app.models.medico_estabelecimento import MedicoEstabelecimento
from app.models.paciente import Paciente
from app.models.rede_estabelecimento import RedeEstabelecimentos
from app.models.slot import Slot, SlotStatus
from app.models.usuario import Usuario, UsuarioRole

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
}

ESTABELECIMENTO_2 = {
    "nome": "Clínica Vida Saúde",
    "cnpj": "22222222000102",
    "slug": "clinica-vida",
    "tipo": TipoEstabelecimento.CLINICA,
    "plano": "pro",
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
# Médicos — esp_idx relativo ao estabelecimento principal
# ============================================================

# Hospital São Lucas (est1) — esp_idx relativo a ESPECIALIDADES_EST1
MEDICOS_EST1 = [
    {"nome": "Dr. Carlos Mendes",   "crm": "CRM-SP-12345", "esp_idx": 0, "email": "carlos.mendes@medbot.com",   "duracao": 30},
    {"nome": "Dra. Ana Paula Lima", "crm": "CRM-SP-23456", "esp_idx": 0, "email": "ana.lima@medbot.com",         "duracao": 30},
    {"nome": "Dr. Roberto Farias",  "crm": "CRM-SP-34567", "esp_idx": 1, "email": "roberto.farias@medbot.com",  "duracao": 45},
    {"nome": "Dr. Paulo Saraiva",   "crm": "CRM-SP-56789", "esp_idx": 2, "email": "paulo.saraiva@medbot.com",   "duracao": 45},
    {"nome": "Dr. Ricardo Nunes",   "crm": "CRM-SP-89012", "esp_idx": 3, "email": "ricardo.nunes@medbot.com",   "duracao": 40},
]

# Clínica Vida (est2) — esp_idx relativo a ESPECIALIDADES_EST2
MEDICOS_EST2 = [
    # Dr. Carlos Mendes atende em AMBAS as unidades (médico_idx=0 de est1)
    {"nome": "Dra. Juliana Torres",  "crm": "CRM-SP-67890", "esp_idx": 1, "email": "juliana.torres@medbot.com", "duracao": 30},
    {"nome": "Dr. Fernando Alves",   "crm": "CRM-SP-78901", "esp_idx": 2, "email": "fernando.alves@medbot.com", "duracao": 40},
]

# ============================================================
# Pacientes — separados por estabelecimento
# ============================================================

PACIENTES_EST1 = [
    {"nome": "João da Silva Santos",   "cpf": "12345678901", "data_nascimento": date(1985, 3, 15), "telefone": "11999990001", "email": "joao.silva@email.com",  "convenio": "Unimed"},
    {"nome": "Maria Aparecida Souza",  "cpf": "23456789012", "data_nascimento": date(1972, 7, 22), "telefone": "11999990002", "email": "maria.souza@email.com",  "convenio": "Bradesco Saúde"},
]

PACIENTES_EST2 = [
    {"nome": "Pedro Henrique Oliveira","cpf": "34567890123", "data_nascimento": date(1995, 11, 8), "telefone": "11999990003", "email": "pedro.oliveira@email.com","convenio": None},
    {"nome": "Camila Rodrigues Lima",  "cpf": "45678901234", "data_nascimento": date(1990, 5, 30), "telefone": "11999990004", "email": "camila.lima@email.com",   "convenio": "SulAmérica"},
]

# ============================================================
# Usuários internos
# ============================================================

def gerar_usuarios(est1_id: int, est2_id: int, medicos_est1: list, medicos_est2: list) -> list[dict]:
    return [
        # ADMIN_GLOBAL — plataforma (sem estabelecimento_id)
        {"nome": "Admin Master",         "email": "admin@medbot.com",       "senha": "Admin@123",    "role": UsuarioRole.ADMIN_GLOBAL,          "medico_id": None, "est_id": None},
        # Admins por estabelecimento
        {"nome": "Admin Hospital",       "email": "admin@hosp-sao-lucas.com","senha": "Admin@123",   "role": UsuarioRole.ADMIN_ESTABELECIMENTO,  "medico_id": None, "est_id": est1_id},
        {"nome": "Admin Clínica",        "email": "admin@clinica-vida.com",  "senha": "Admin@123",   "role": UsuarioRole.ADMIN_ESTABELECIMENTO,  "medico_id": None, "est_id": est2_id},
        # Recepcionistas por estabelecimento
        {"nome": "Recepcionista Carla",  "email": "carla@hosp-sao-lucas.com","senha": "Carla@123",   "role": UsuarioRole.RECEPCIONISTA,          "medico_id": None, "est_id": est1_id},
        {"nome": "Recepcionista Bruno",  "email": "bruno@clinica-vida.com",  "senha": "Bruno@123",   "role": UsuarioRole.RECEPCIONISTA,          "medico_id": None, "est_id": est2_id},
    ]


def gerar_slots_medico(medico_id: int, duracao_min: int, estabelecimento_id: int, dias_ahead: int = 7) -> list[Slot]:
    """Gera slots para os próximos N dias úteis."""
    slots = []
    hoje = date.today()

    for delta in range(dias_ahead + 14):
        dia = hoje + timedelta(days=delta)
        if dia.weekday() >= 5:
            continue

        for hora_inicio_turno, hora_fim_turno in [(time(8, 0), time(12, 0)), (time(14, 0), time(18, 0))]:
            hora_atual = hora_inicio_turno
            while hora_atual < hora_fim_turno:
                dt_inicio = datetime.combine(dia, hora_atual)
                dt_fim = dt_inicio + timedelta(minutes=duracao_min)
                if dt_fim.time() <= hora_fim_turno:
                    slots.append(Slot(
                        medico_id=medico_id,
                        data=dia,
                        hora_inicio=hora_atual,
                        hora_fim=dt_fim.time(),
                        status=SlotStatus.DISPONIVEL,
                        estabelecimento_id=estabelecimento_id,
                    ))
                hora_atual = (datetime.combine(dia, hora_atual) + timedelta(minutes=duracao_min)).time()

        if len({s.data for s in slots}) >= dias_ahead:
            break

    return slots


async def seed(db: AsyncSession) -> None:
    log.info("seed_iniciando")

    # ────────────────────────────────────────────────────────
    # 0. Limpar dados (ordem respeita FK)
    # ────────────────────────────────────────────────────────
    for tabela in ["token_usage", "sessoes_chat", "consultas", "slots",
                   "usuarios", "pacientes", "medico_estabelecimentos",
                   "medicos", "especialidades", "convenios", "licencas",
                   "estabelecimentos", "redes_estabelecimentos"]:
        await db.execute(text(f"DELETE FROM {tabela}"))  # noqa: S608
    # Resetar sequences
    for seq in ["medicos_id_seq", "especialidades_id_seq", "slots_id_seq",
                "consultas_id_seq", "sessoes_chat_id_seq", "usuarios_id_seq",
                "pacientes_id_seq", "convenios_id_seq", "licencas_id_seq",
                "estabelecimentos_id_seq", "redes_estabelecimentos_id_seq"]:
        await db.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))
    await db.commit()
    log.info("seed_banco_limpo")

    # ────────────────────────────────────────────────────────
    # 1. Rede (holding)
    # ────────────────────────────────────────────────────────
    rede = RedeEstabelecimentos(**REDE, ativo=True)
    db.add(rede)
    await db.flush()

    # ────────────────────────────────────────────────────────
    # 2. Estabelecimentos
    # ────────────────────────────────────────────────────────
    est1 = EstabelecimentoSaude(**ESTABELECIMENTO_1, ativo=True, rede_id=rede.id)
    est2 = EstabelecimentoSaude(**ESTABELECIMENTO_2, ativo=True, rede_id=rede.id)
    db.add(est1)
    db.add(est2)
    await db.flush()
    log.info("seed_estabelecimentos", est1=est1.nome, est2=est2.nome)

    # ────────────────────────────────────────────────────────
    # 3. Especialidades por estabelecimento
    # ────────────────────────────────────────────────────────
    esps_est1: list[Especialidade] = []
    for dados in ESPECIALIDADES_EST1:
        esp = Especialidade(**dados, estabelecimento_id=est1.id, ativo=True)
        db.add(esp)
        esps_est1.append(esp)

    esps_est2: list[Especialidade] = []
    for dados in ESPECIALIDADES_EST2:
        esp = Especialidade(**dados, estabelecimento_id=est2.id, ativo=True)
        db.add(esp)
        esps_est2.append(esp)

    await db.flush()
    log.info("seed_especialidades", est1=len(esps_est1), est2=len(esps_est2))

    # ────────────────────────────────────────────────────────
    # 4. Médicos do Hospital (est1)
    # ────────────────────────────────────────────────────────
    medicos_est1: list[Medico] = []
    for dados in MEDICOS_EST1:
        esp = esps_est1[dados["esp_idx"]]
        medico = Medico(
            nome=dados["nome"],
            crm=dados["crm"],
            especialidade_id=esp.id,
            email=dados["email"],
            duracao_consulta_min=dados["duracao"],
            ativo=True,
        )
        db.add(medico)
        medicos_est1.append(medico)

    await db.flush()

    for idx, medico in enumerate(medicos_est1):
        vinculo = MedicoEstabelecimento(
            medico_id=medico.id,
            estabelecimento_id=est1.id,
            duracao_consulta_min=MEDICOS_EST1[idx]["duracao"],
            ativo=True,
        )
        db.add(vinculo)

    # ────────────────────────────────────────────────────────
    # 5. Médicos da Clínica (est2)
    # ────────────────────────────────────────────────────────
    medicos_est2: list[Medico] = []
    for dados in MEDICOS_EST2:
        esp = esps_est2[dados["esp_idx"]]
        medico = Medico(
            nome=dados["nome"],
            crm=dados["crm"],
            especialidade_id=esp.id,
            email=dados["email"],
            duracao_consulta_min=dados["duracao"],
            ativo=True,
        )
        db.add(medico)
        medicos_est2.append(medico)

    await db.flush()

    for idx, medico in enumerate(medicos_est2):
        vinculo = MedicoEstabelecimento(
            medico_id=medico.id,
            estabelecimento_id=est2.id,
            duracao_consulta_min=MEDICOS_EST2[idx]["duracao"],
            ativo=True,
        )
        db.add(vinculo)

    # Dr. Carlos Mendes (medicos_est1[0]) também atende na Clínica Vida
    vinculo_carlos_clinica = MedicoEstabelecimento(
        medico_id=medicos_est1[0].id,
        estabelecimento_id=est2.id,
        duracao_consulta_min=30,
        ativo=True,
    )
    db.add(vinculo_carlos_clinica)

    await db.flush()
    log.info("seed_medicos", est1=len(medicos_est1), est2=len(medicos_est2), compartilhados=1)

    # ────────────────────────────────────────────────────────
    # 6. Slots — 7 dias úteis por médico por estabelecimento
    # ────────────────────────────────────────────────────────
    total_slots = 0

    for idx, medico in enumerate(medicos_est1):
        slots = gerar_slots_medico(medico.id, MEDICOS_EST1[idx]["duracao"], est1.id)
        for s in slots:
            db.add(s)
        total_slots += len(slots)

    for idx, medico in enumerate(medicos_est2):
        slots = gerar_slots_medico(medico.id, MEDICOS_EST2[idx]["duracao"], est2.id)
        for s in slots:
            db.add(s)
        total_slots += len(slots)

    # Dr. Carlos também tem slots na Clínica
    slots_carlos_clinica = gerar_slots_medico(medicos_est1[0].id, 30, est2.id)
    for s in slots_carlos_clinica:
        db.add(s)
    total_slots += len(slots_carlos_clinica)

    await db.flush()
    log.info("seed_slots", total=total_slots)

    # ────────────────────────────────────────────────────────
    # 7. Pacientes por estabelecimento
    # ────────────────────────────────────────────────────────
    pacientes_est1: list[Paciente] = []
    for dados in PACIENTES_EST1:
        p = Paciente(**dados, estabelecimento_id=est1.id, ativo=True)
        db.add(p)
        pacientes_est1.append(p)

    pacientes_est2: list[Paciente] = []
    for dados in PACIENTES_EST2:
        p = Paciente(**dados, estabelecimento_id=est2.id, ativo=True)
        db.add(p)
        pacientes_est2.append(p)

    await db.flush()
    log.info("seed_pacientes", est1=len(pacientes_est1), est2=len(pacientes_est2))

    # ────────────────────────────────────────────────────────
    # 8. Convênios por estabelecimento
    # ────────────────────────────────────────────────────────
    NOMES_CONVENIOS = ["Unimed", "Bradesco Saúde", "SulAmérica", "Amil", "Porto Seguro Saúde", "Hapvida"]
    for nome in NOMES_CONVENIOS:
        db.add(Convenio(nome=nome, ativo=True, estabelecimento_id=est1.id))
        db.add(Convenio(nome=nome, ativo=True, estabelecimento_id=est2.id))
    await db.flush()
    log.info("seed_convenios", total=len(NOMES_CONVENIOS) * 2)

    # ────────────────────────────────────────────────────────
    # 9. Usuários internos
    # ────────────────────────────────────────────────────────
    for dados in gerar_usuarios(est1.id, est2.id, medicos_est1, medicos_est2):
        u = Usuario(
            nome=dados["nome"],
            email=dados["email"],
            senha_hash=hash_password(dados["senha"]),
            role=dados["role"],
            medico_id=dados["medico_id"],
            estabelecimento_id=dados["est_id"],
            ativo=True,
        )
        db.add(u)

    # Usuários dos médicos do Hospital
    for idx, medico in enumerate(medicos_est1):
        u = Usuario(
            nome=medico.nome,
            email=MEDICOS_EST1[idx]["email"],
            senha_hash=hash_password("Medico@123"),
            role=UsuarioRole.MEDICO,
            medico_id=medico.id,
            estabelecimento_id=est1.id,
            ativo=True,
        )
        db.add(u)

    # Usuários dos médicos da Clínica
    for idx, medico in enumerate(medicos_est2):
        u = Usuario(
            nome=medico.nome,
            email=MEDICOS_EST2[idx]["email"],
            senha_hash=hash_password("Medico@123"),
            role=UsuarioRole.MEDICO,
            medico_id=medico.id,
            estabelecimento_id=est2.id,
            ativo=True,
        )
        db.add(u)

    await db.flush()

    # ────────────────────────────────────────────────────────
    # 10. Commit final
    # ────────────────────────────────────────────────────────
    await db.commit()
    log.info("seed_concluido")

    # ────────────────────────────────────────────────────────
    # Resumo
    # ────────────────────────────────────────────────────────
    sep = "=" * 65
    print(f"\n{sep}")
    print("  SEED CONCLUIDO COM SUCESSO — Multi-tenant MedBot")
    print(sep)

    print(f"\n  REDE: {rede.nome} (CNPJ: {rede.cnpj_holding})")

    print(f"\n  ESTABELECIMENTO 1 — {est1.nome} [id={est1.id}] [{est1.tipo.value}]")
    print(f"    Especialidades ({len(esps_est1)}): {', '.join(e.nome for e in esps_est1)}")
    print(f"    Medicos ({len(medicos_est1)}): {', '.join(m.nome for m in medicos_est1)}")
    print(f"    Pacientes ({len(pacientes_est1)}): {', '.join(p.nome for p in pacientes_est1)}")

    print(f"\n  ESTABELECIMENTO 2 — {est2.nome} [id={est2.id}] [{est2.tipo.value}]")
    print(f"    Especialidades ({len(esps_est2)}): {', '.join(e.nome for e in esps_est2)}")
    print(f"    Medicos ({len(medicos_est2) + 1}): {', '.join(m.nome for m in medicos_est2)} + Dr. Carlos Mendes (compartilhado)")
    print(f"    Pacientes ({len(pacientes_est2)}): {', '.join(p.nome for p in pacientes_est2)}")

    print(f"\n  SLOTS GERADOS: {total_slots}")

    print("\n  LOGINS:")
    print("    [ADMIN_GLOBAL]         admin@medbot.com         / Admin@123")
    print("    [ADMIN_EST1]           admin@hosp-sao-lucas.com / Admin@123")
    print("    [ADMIN_EST2]           admin@clinica-vida.com   / Admin@123")
    print("    [RECEP_EST1]           carla@hosp-sao-lucas.com / Carla@123")
    print("    [RECEP_EST2]           bruno@clinica-vida.com   / Bruno@123")
    print("    [MEDICO]               qualquer email de medico / Medico@123")

    print("\n  PACIENTES (SMS — codigo fica no Redis):")
    for p in pacientes_est1 + pacientes_est2:
        est_nome = est1.nome if p.estabelecimento_id == est1.id else est2.nome
        print(f"    CPF: {p.cpf} ({p.nome[:20]}) — {est_nome}")

    print(f"\n{sep}\n")


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
