"""Testa a jornada completa do usuário MedBot.

Cobre:
  1. Estado do banco pós-seed
  2. Login admin (email+senha)
  3. Listagem de especialidades e médicos
  4. Login de paciente (fluxo SMS via Redis)
  5. Consulta de agenda disponível
  6. Agendamento de consulta
  7. Jornada do bot via WebSocket
  8. Verificações finais no banco

Uso:
    cd backend
    uv run python scripts/testar_jornada.py
"""

import asyncio
import json
import sys

import httpx
import websockets
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, "/home/payao/projetos/chatbot-ai-medical/backend")
from app.core.config import settings

BASE = "http://localhost:8100/v1"
WS_BASE = "ws://localhost:8100/v1"

BOLD = "\033[1m"
GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
GRAY = "\033[0;90m"
NC = "\033[0m"


def section(titulo: str) -> None:
    print(f"\n{BOLD}{CYAN}{'═'*55}{NC}")
    print(f"{BOLD}{CYAN} {titulo}{NC}")
    print(f"{BOLD}{CYAN}{'═'*55}{NC}")


def step(msg: str) -> None:
    print(f"\n{YELLOW}▶ {msg}{NC}")


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓ {msg}{NC}")


def err(msg: str) -> None:
    print(f"{RED}  ✗ {msg}{NC}")


def info(msg: str) -> None:
    print(f"{GRAY}    {msg}{NC}")


async def db_query(engine, sql: str) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(text(sql))
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    client = httpx.AsyncClient(base_url=BASE, timeout=30)

    try:
        # ────────────────────────────────────────────────────────
        section("ETAPA 0 — Estado do banco pós-seed")
        # ────────────────────────────────────────────────────────
        step("Contagem por tabela")
        contagens = await db_query(engine, """
            SELECT tabela, total FROM (
                SELECT 'especialidades' AS tabela, COUNT(*)::int AS total FROM especialidades
                UNION ALL SELECT 'medicos',      COUNT(*) FROM medicos
                UNION ALL SELECT 'slots',        COUNT(*) FROM slots
                UNION ALL SELECT 'pacientes',    COUNT(*) FROM pacientes
                UNION ALL SELECT 'usuarios',     COUNT(*) FROM usuarios
                UNION ALL SELECT 'consultas',    COUNT(*) FROM consultas
                UNION ALL SELECT 'sessoes_chat', COUNT(*) FROM sessoes_chat
            ) t ORDER BY tabela
        """)
        for row in contagens:
            info(f"{row['tabela']:<20} {row['total']:>5} registros")

        # ────────────────────────────────────────────────────────
        section("ETAPA 1 — Login admin")
        # ────────────────────────────────────────────────────────
        step("POST /auth/login — admin@medbot.com / Admin@123")
        resp = await client.post("/auth/login", json={"email": "admin@medbot.com", "senha": "Admin@123"})
        assert resp.status_code == 200, f"Falha no login: {resp.text}"
        admin_token = resp.json()["access_token"]
        ok(f"Token obtido: {admin_token[:30]}...")

        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        # ────────────────────────────────────────────────────────
        section("ETAPA 2 — Listar especialidades e médicos")
        # ────────────────────────────────────────────────────────
        step("GET /especialidades/")
        resp = await client.get("/especialidades/", headers=headers_admin)
        especialidades = resp.json()
        ok(f"{len(especialidades)} especialidades cadastradas")
        for e in especialidades:
            info(f"[{e['id']}] {e['nome']}  {e['cor_hex']}")

        step("GET /medicos/")
        resp = await client.get("/medicos/", headers=headers_admin)
        medicos = resp.json()
        ok(f"{len(medicos)} médicos cadastrados")
        for m in medicos[:5]:
            info(f"[{m['id']}] {m['nome']}  CRM: {m['crm']}  duração: {m['duracao_consulta_min']}min")
        if len(medicos) > 5:
            info(f"  ... e mais {len(medicos) - 5}")

        # ────────────────────────────────────────────────────────
        section("ETAPA 3 — Login de paciente (fluxo SMS)")
        # ────────────────────────────────────────────────────────
        CPF = "12345678901"
        step(f"POST /auth/sms/request — CPF {CPF[:3]}.***.***-{CPF[-2:]}")

        # Limpar rate limit para conseguir solicitar
        import redis as redis_sync  # noqa: PLC0415
        r = redis_sync.from_url("redis://localhost:6379")
        r.delete(f"sms:rate:{CPF}")

        resp = await client.post("/auth/sms/request", json={"cpf": CPF})
        assert resp.status_code == 200, f"Erro SMS request: {resp.text}"
        ok(resp.json()["mensagem"])

        # Ler código direto do Redis (ambiente dev)
        codigo_sms = r.get(f"sms:code:{CPF}")
        assert codigo_sms, "Código SMS não encontrado no Redis"
        codigo_sms = codigo_sms.decode().strip()
        ok(f"Código SMS no Redis: {codigo_sms}")

        step(f"POST /auth/sms/verify — código {codigo_sms}")
        resp = await client.post("/auth/sms/verify", json={"cpf": CPF, "codigo": codigo_sms})
        assert resp.status_code == 200, f"Erro SMS verify: {resp.text}"
        paciente_token = resp.json()["access_token"]
        ok(f"Token do paciente: {paciente_token[:30]}...")
        headers_paciente = {"Authorization": f"Bearer {paciente_token}"}

        # Obter paciente_id
        pacientes_db = await db_query(engine, f"SELECT id, nome FROM pacientes WHERE cpf='{CPF}'")
        paciente_id = pacientes_db[0]["id"]
        paciente_nome = pacientes_db[0]["nome"]
        ok(f"Paciente autenticado: [{paciente_id}] {paciente_nome}")

        # ────────────────────────────────────────────────────────
        section("ETAPA 4 — Consultar agenda disponível")
        # ────────────────────────────────────────────────────────
        step("GET /agenda/disponivel?especialidade_id=2 (Cardiologia)")
        resp = await client.get(
            "/agenda/disponivel",
            params={"especialidade_id": 2},
            headers=headers_admin,
        )
        slots = resp.json()
        ok(f"{len(slots)} slots disponíveis de Cardiologia")
        for s in slots[:4]:
            info(f"[slot {s['id']}] {s['data']}  {s['hora_inicio']} – {s['hora_fim']}")

        if not slots:
            err("Nenhum slot disponível — não é possível continuar")
            return

        slot = slots[0]
        slot_id = slot["id"]
        medico_id = slot["medico_id"]

        # Pegar especialidade do médico
        medico_db = await db_query(engine, f"SELECT especialidade_id FROM medicos WHERE id={medico_id}")
        especialidade_id = medico_db[0]["especialidade_id"]

        # ────────────────────────────────────────────────────────
        section("ETAPA 5 — Agendar consulta")
        # ────────────────────────────────────────────────────────
        step(f"POST /agenda/consultas — slot={slot_id}, paciente={paciente_id}")
        payload_consulta = {
            "slot_id": slot_id,
            "paciente_id": paciente_id,
            "medico_id": medico_id,
            "especialidade_id": especialidade_id,
            "tipo": "EXTERNO",
            "canal_origem": "PORTAL",
            "urgencia": "MEDIA",
            "triagem_resumo": {
                "sintomas": "dor no peito ao esforço",
                "origem": "bot",
            },
        }
        resp = await client.post("/agenda/consultas", json=payload_consulta, headers=headers_admin)
        if resp.status_code in (200, 201):
            consulta = resp.json()
            consulta_id = consulta["id"]
            ok(f"Consulta agendada! ID: {consulta_id}")
            info(f"Status: {consulta['status']}")
            info(f"Urgência: {consulta['urgencia']}")
            info(f"Canal: {consulta['canal_origem']}")
        else:
            err(f"Falha ao agendar: {resp.status_code} — {resp.text}")
            consulta_id = None

        # ────────────────────────────────────────────────────────
        section("ETAPA 6 — Jornada do Bot via WebSocket")
        # ────────────────────────────────────────────────────────
        step("POST /chat/sessao — criando sessão")
        resp = await client.post("/chat/sessao", json={"canal": "PORTAL"})
        assert resp.status_code == 201, f"Erro ao criar sessão: {resp.text}"
        session_token = resp.json()["session_token"]
        ok(f"Sessão criada: {session_token}")

        # Verificar sessão no banco
        sessao_db = await db_query(engine, f"SELECT * FROM sessoes_chat WHERE session_token='{session_token}'")
        if sessao_db:
            ok(f"Sessão salva no banco: estado={sessao_db[0].get('estado', sessao_db[0].get('etapa', '?'))}")

        step(f"Conectando WebSocket: /v1/chat/ws/{session_token[:8]}...")
        mensagens_teste = [
            "Oi! Estou sentindo dor no peito ao fazer esforço físico",
            "A dor apareceu há 2 semanas, é uma dor aperto no centro do peito",
            "Tenho 45 anos, tenho pressão alta controlada",
        ]

        ws_url = f"{WS_BASE}/chat/ws/{session_token}"
        try:
            async with websockets.connect(ws_url, ping_interval=None) as ws:
                ok("WebSocket conectado!")
                for i, msg in enumerate(mensagens_teste, 1):
                    info(f"\n  [{i}] Usuário → {msg}")
                    await ws.send(json.dumps({"mensagem": msg}))

                    try:
                        resposta_raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        resposta = json.loads(resposta_raw)
                        bot_msg = resposta.get("resposta", resposta.get("mensagem", str(resposta)))
                        estado = resposta.get("estado", resposta.get("etapa", "?"))
                        emergencia = resposta.get("emergencia_detectada", False)

                        info(f"  Bot ({estado}) → {str(bot_msg)[:300]}")
                        if emergencia:
                            print(f"  {RED}⚠ EMERGÊNCIA DETECTADA — SAMU 192{NC}")
                    except asyncio.TimeoutError:
                        err(f"Timeout aguardando resposta para mensagem {i}")
                        break
        except Exception as e:
            err(f"Erro no WebSocket: {e}")

        # ────────────────────────────────────────────────────────
        section("ETAPA 7 — Verificações finais no banco")
        # ────────────────────────────────────────────────────────
        step("Estado geral do banco após a jornada")
        contagens_final = await db_query(engine, """
            SELECT tabela, total FROM (
                SELECT 'especialidades' AS tabela, COUNT(*)::int AS total FROM especialidades
                UNION ALL SELECT 'medicos',             COUNT(*) FROM medicos
                UNION ALL SELECT 'slots total',         COUNT(*) FROM slots
                UNION ALL SELECT 'slots agendados',     COUNT(*) FROM slots WHERE status='AGENDADO'
                UNION ALL SELECT 'slots disponíveis',   COUNT(*) FROM slots WHERE status='DISPONIVEL'
                UNION ALL SELECT 'pacientes',           COUNT(*) FROM pacientes
                UNION ALL SELECT 'usuarios',            COUNT(*) FROM usuarios
                UNION ALL SELECT 'consultas',           COUNT(*) FROM consultas
                UNION ALL SELECT 'sessoes_chat',        COUNT(*) FROM sessoes_chat
            ) t ORDER BY tabela
        """)
        for row in contagens_final:
            info(f"{row['tabela']:<25} {row['total']:>5} registros")

        step("Detalhe das consultas agendadas")
        consultas_db = await db_query(engine, """
            SELECT
                c.id,
                p.nome AS paciente,
                m.nome AS medico,
                e.nome AS especialidade,
                s.data,
                s.hora_inicio,
                c.status,
                c.urgencia,
                c.canal_origem
            FROM consultas c
            JOIN slots s ON c.slot_id = s.id
            JOIN medicos m ON s.medico_id = m.id
            JOIN especialidades e ON m.especialidade_id = e.id
            JOIN pacientes p ON c.paciente_id = p.id
            ORDER BY c.id
        """)
        if consultas_db:
            for c in consultas_db:
                ok(f"Consulta [{c['id']}]")
                info(f"  Paciente:     {c['paciente']}")
                info(f"  Médico:       {c['medico']}")
                info(f"  Especialidade:{c['especialidade']}")
                info(f"  Data/Hora:    {c['data']} às {str(c['hora_inicio'])[:5]}")
                info(f"  Status:       {c['status']}")
                info(f"  Urgência:     {c['urgencia']}")
                info(f"  Canal:        {c['canal_origem']}")
        else:
            info("Nenhuma consulta agendada.")

        step("Sessões de chat no banco (auditoria)")
        sessoes = await db_query(engine, """
            SELECT session_token, canal, status, created_at
            FROM sessoes_chat
            ORDER BY created_at DESC
            LIMIT 5
        """)
        if sessoes:
            for s in sessoes:
                token_str = str(s['session_token'])
                info(f"[{token_str[:8]}...]  status={s['status']}  canal={s['canal']}")
        else:
            info("Nenhuma sessão no banco (sessões vivem no Redis durante a conversa).")

        step("Sessão do bot no Redis (estado em tempo real)")
        r = redis_sync.from_url("redis://localhost:6379")
        session_raw = r.get(f"chat:session:{session_token}")
        if session_raw:
            session_data = json.loads(session_raw)
            ok("Sessão encontrada no Redis!")
            info(f"  Token:  {session_token[:8]}...")
            info(f"  Estado: {session_data.get('estado', '?')}")
            info(f"  Canal:  {session_data.get('canal', '?')}")
            dados = session_data.get('dados_coletados', {})
            sintomas = dados.get('sintomas', [])
            especialidade = dados.get('especialidade', None)
            perguntas = dados.get('perguntas_coleta', 0)
            info(f"  Sintomas coletados: {sintomas}")
            info(f"  Especialidade sugerida: {especialidade or 'ainda não definida'}")
            info(f"  Perguntas feitas: {perguntas}")
            msgs = session_data.get('mensagens', [])
            info(f"  Mensagens no histórico: {len(msgs)}")
        else:
            info("Sessão expirada ou não encontrada no Redis.")

        # ────────────────────────────────────────────────────────
        print(f"\n{BOLD}{GREEN}{'='*55}{NC}")
        print(f"{BOLD}{GREEN} JORNADA COMPLETA TESTADA COM SUCESSO{NC}")
        print(f"{BOLD}{GREEN}{'='*55}{NC}\n")

    finally:
        await client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
