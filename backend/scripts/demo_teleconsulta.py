"""Cria uma teleconsulta de demonstração que começa em poucos minutos.

A sala de espera só abre 30 minutos antes do horário, então para testar a qualquer hora é preciso
um atendimento online marcado para "agora". Este script cria o horário, o atendimento e a sala.

Uso:
    cd backend
    uv run python scripts/demo_teleconsulta.py [email-do-profissional] [minutos-ate-o-inicio]

Padrão: carlos.mendes@medbot.com, começando em 10 minutos.
"""
# ruff: noqa: T201 — script de linha de comando: print() é a saída

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.tempo import agora_local, fuso_do_estabelecimento
from app.models import Atendimento, AtendimentoCanal, AtendimentoTipo, Cliente, Slot, SlotStatus, Usuario
from app.models.profissional import Profissional
from app.models.teleconsulta import Modalidade
from app.services import telemedicina_service as tele
from app.services.ia.resumo_triagem import categorizar_sintomas, resumo_por_regra

RELATO = ["Tosse seca há cinco dias", "piora à noite, sem febre"]


async def main(email: str, minutos: int) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        usuario = (await db.execute(select(Usuario).where(Usuario.email == email))).scalar_one_or_none()
        if usuario is None or usuario.profissional_id is None:
            raise SystemExit(f"Não há profissional com o login {email}. Rode o seed ou informe outro e-mail.")
        profissional = (
            await db.execute(select(Profissional).where(Profissional.id == usuario.profissional_id))
        ).scalar_one()
        unidade = usuario.estabelecimento_id
        cliente = (
            await db.execute(select(Cliente).where(Cliente.estabelecimento_id == unidade).order_by(Cliente.id).limit(1))
        ).scalar_one()

        inicio = (agora_local(await fuso_do_estabelecimento(db, unidade)) + timedelta(minutes=minutos)).replace(
            second=0, microsecond=0
        )
        slot = Slot(
            profissional_id=profissional.id,
            data=inicio.date(),
            hora_inicio=inicio.time(),
            hora_fim=(inicio + timedelta(minutes=30)).time(),
            status=SlotStatus.AGENDADO,
            aceita_online=True,
            estabelecimento_id=unidade,
        )
        db.add(slot)
        await db.flush()
        atendimento = Atendimento(
            slot_id=slot.id,
            cliente_id=cliente.id,
            profissional_id=profissional.id,
            especialidade_id=profissional.especialidade_id,
            tipo=AtendimentoTipo.EXTERNO,
            canal_origem=AtendimentoCanal.PORTAL,
            modalidade=Modalidade.ONLINE,
            triagem_resumo={
                "texto": resumo_por_regra({"sintomas": RELATO}),
                "origem": "regra",
                "sintomas": RELATO,
                "categorias": categorizar_sintomas(RELATO),
                "historico": [],
            },
            observacoes="Teleconsulta de demonstração.",
            estabelecimento_id=unidade,
        )
        db.add(atendimento)
        await db.flush()
        sala = await tele.criar_teleconsulta(db, atendimento)
        await db.commit()

        print(f"atendimento_id={atendimento.id}")
        print(f"token={sala.token_paciente}")
        print(f"\nTeleconsulta de {cliente.nome} com {profissional.nome} às {inicio.strftime('%H:%M')}.")
        print(f"  Paciente:     {tele.link_do_paciente(sala.token_paciente)}")
        print(f"  Profissional: http://localhost:4201/atender/{atendimento.id}  (login {email} / Medico@123)")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(
        main(
            sys.argv[1] if len(sys.argv) > 1 else "carlos.mendes@medbot.com",
            int(sys.argv[2]) if len(sys.argv) > 2 else 10,
        )
    )
