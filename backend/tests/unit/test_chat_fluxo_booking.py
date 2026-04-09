"""Testes unitários — Fluxo de booking pós-slot (T85.5).

Cobre (TDAD retroativo — código já implementado, testes escritos após):
- APRESENTANDO_SLOTS + confirmar:ID → COLETANDO_CONTATO + pede telefone
- COLETANDO_CONTATO step=telefone → salva telefone, pede e-mail
- COLETANDO_CONTATO step=email → salva e-mail, mostra resumo, avança CONFIRMANDO
- CONFIRMANDO + "Sim" → cria Consulta no banco, retorna confirmacao
- CONFIRMANDO + "Não" → cancela, vai FINALIZADO sem criar consulta
- Prompt dinâmico usa especialidades da sessão (não lista hardcoded)
- _extrair_especialidade_do_texto usa lista da sessão como prioridade
- "nutricionista" → fallback para Clinica Geral quando não existe na sessão
- Sessão sem especialidades → usa ESPECIALIDADES_WHITELIST como fallback
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.services.ia.chat_service import ChatService
from app.services.ia.state_machine import ChatEstado
from app.services.ia.prompts import obter_prompt_conversa, ESPECIALIDADES_WHITELIST


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_service():
    db = AsyncMock()
    redis = AsyncMock()
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return ChatService(db=db, redis=redis)


def _session(
    estado: str = "START",
    dados: dict | None = None,
    especialidades: list[str] | None = None,
    slots_temp: list[dict] | None = None,
) -> bytes:
    data = {
        "token": "test-token",
        "canal": "PORTAL",
        "estabelecimento_id": 1,
        "mensagens": [],
        "estado": estado,
        "especialidades": especialidades or ["Clínica Geral", "Cardiologia", "Neurologia", "Ortopedia"],
        "slots_temp": slots_temp or [],
        "dados_coletados": dados or _dados_padrao(),
    }
    return json.dumps(data).encode()


def _dados_padrao(
    nome: str = "Claudio Payao",
    especialidade: str | None = "Ortopedia",
    slot_id: int | None = None,
    contato_step: str = "telefone",
    telefone: str | None = None,
    email: str | None = None,
) -> dict:
    return {
        "nome": nome,
        "convenio_id": None,
        "tipo_atendimento": "PARTICULAR",
        "telefone": telefone,
        "email": email,
        "slot_id_selecionado": slot_id,
        "contato_step": contato_step,
        "sintomas": [],
        "especialidade": especialidade,
        "medico": None,
        "horario": None,
        "perguntas_coleta": 0,
    }


_SLOT_TEMP = {
    "id": 42,
    "data": "08/04/2026",
    "hora_inicio": "09:00",
    "hora_fim": "09:40",
    "medico_nome": "Dr. Ricardo Nunes",
}


# ──────────────────────────────────────────────────────────────────────────────
# Bloco 1 — Seleção de slot (APRESENTANDO_SLOTS + confirmar:ID)
# ──────────────────────────────────────────────────────────────────────────────

class TestSlotSelecionado:
    async def test_confirmar_slot_avanca_para_coletando_contato(self):
        """QUANDO usuário confirma slot, DEVE mover para COLETANDO_CONTATO."""
        svc = _make_service()
        svc.redis.get = AsyncMock(
            return_value=_session(
                ChatEstado.APRESENTANDO_SLOTS,
                _dados_padrao(slot_id=None),
                slots_temp=[_SLOT_TEMP],
            )
        )

        resultado = await svc.processar_mensagem("test-token", "confirmar:42")

        assert resultado["estado"] == ChatEstado.COLETANDO_CONTATO
        assert resultado["emergencia"] is False
        assert resultado["sessao_expirada"] is False

    async def test_confirmar_slot_salva_slot_id_na_sessao(self):
        """Slot ID deve ser persistido em dados_coletados."""
        svc = _make_service()
        svc.redis.get = AsyncMock(
            return_value=_session(
                ChatEstado.APRESENTANDO_SLOTS,
                _dados_padrao(slot_id=None),
                slots_temp=[_SLOT_TEMP],
            )
        )

        await svc.processar_mensagem("test-token", "confirmar:42")

        saved = json.loads(svc.redis.set.call_args[0][1])
        assert saved["dados_coletados"]["slot_id_selecionado"] == 42

    async def test_confirmar_slot_pede_telefone(self):
        """Resposta ao confirmar slot deve pedir o telefone."""
        svc = _make_service()
        svc.redis.get = AsyncMock(
            return_value=_session(
                ChatEstado.APRESENTANDO_SLOTS,
                _dados_padrao(slot_id=None),
                slots_temp=[_SLOT_TEMP],
            )
        )

        resultado = await svc.processar_mensagem("test-token", "confirmar:42")

        assert "telefone" in resultado["resposta"].lower()

    async def test_confirmar_slot_invalido_retorna_erro(self):
        """Mensagem confirmar sem ID numérico válido → resposta de erro, sem crash."""
        svc = _make_service()
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.APRESENTANDO_SLOTS, _dados_padrao(slot_id=None))
        )

        resultado = await svc.processar_mensagem("test-token", "confirmar:abc")

        assert resultado["estado"] == ChatEstado.APRESENTANDO_SLOTS
        assert resultado["sessao_expirada"] is False

    async def test_confirmar_slot_exibe_nome_e_horario_na_resposta(self):
        """Resposta deve mencionar o horário selecionado (info do slot_temp)."""
        svc = _make_service()
        svc.redis.get = AsyncMock(
            return_value=_session(
                ChatEstado.APRESENTANDO_SLOTS,
                _dados_padrao(slot_id=None),
                slots_temp=[_SLOT_TEMP],
            )
        )

        resultado = await svc.processar_mensagem("test-token", "confirmar:42")

        # Deve mencionar data/hora ou nome do médico
        resposta = resultado["resposta"]
        assert "09:00" in resposta or "Ricardo Nunes" in resposta or "08/04" in resposta


# ──────────────────────────────────────────────────────────────────────────────
# Bloco 2 — Coleta de contato (COLETANDO_CONTATO)
# ──────────────────────────────────────────────────────────────────────────────

class TestColetaContato:
    async def test_step_telefone_salva_telefone_e_pede_email(self):
        """Step=telefone: salva número e avança para pedir e-mail."""
        svc = _make_service()
        dados = _dados_padrao(slot_id=42, contato_step="telefone")
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.COLETANDO_CONTATO, dados, slots_temp=[_SLOT_TEMP])
        )

        resultado = await svc.processar_mensagem("test-token", "(11) 99999-1234")

        assert resultado["estado"] == ChatEstado.COLETANDO_CONTATO  # ainda coletando (email)
        assert "e-mail" in resultado["resposta"].lower() or "email" in resultado["resposta"].lower()

        saved = json.loads(svc.redis.set.call_args[0][1])
        assert saved["dados_coletados"]["telefone"] == "(11) 99999-1234"
        assert saved["dados_coletados"]["contato_step"] == "email"

    async def test_step_email_salva_email_e_avanca_confirmando(self):
        """Step=email: salva e-mail, mostra resumo, avança para CONFIRMANDO."""
        svc = _make_service()
        dados = _dados_padrao(slot_id=42, contato_step="email", telefone="(11) 99999-1234")
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.COLETANDO_CONTATO, dados, slots_temp=[_SLOT_TEMP])
        )

        resultado = await svc.processar_mensagem("test-token", "claudio@example.com")

        assert resultado["estado"] == ChatEstado.CONFIRMANDO

        saved = json.loads(svc.redis.set.call_args[0][1])
        assert saved["dados_coletados"]["email"] == "claudio@example.com"

    async def test_step_email_resumo_contem_dados_coletados(self):
        """Resumo deve listar nome, especialidade, horário, telefone e e-mail."""
        svc = _make_service()
        dados = _dados_padrao(
            nome="Claudio Payao",
            especialidade="Ortopedia",
            slot_id=42,
            contato_step="email",
            telefone="(11) 99999-1234",
        )
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.COLETANDO_CONTATO, dados, slots_temp=[_SLOT_TEMP])
        )

        resultado = await svc.processar_mensagem("test-token", "claudio@example.com")

        resposta = resultado["resposta"]
        assert "Claudio Payao" in resposta
        assert "Ortopedia" in resposta
        assert "(11) 99999-1234" in resposta
        assert "claudio@example.com" in resposta

    async def test_step_email_resposta_pede_confirmacao(self):
        """Resumo deve pedir confirmação explícita ('Sim')."""
        svc = _make_service()
        dados = _dados_padrao(slot_id=42, contato_step="email", telefone="11999991234")
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.COLETANDO_CONTATO, dados, slots_temp=[_SLOT_TEMP])
        )

        resultado = await svc.processar_mensagem("test-token", "teste@email.com")

        resposta = resultado["resposta"].lower()
        assert "sim" in resposta or "confirmar" in resposta


# ──────────────────────────────────────────────────────────────────────────────
# Bloco 3 — Criação do agendamento (CONFIRMANDO)
# ──────────────────────────────────────────────────────────────────────────────

class TestCriarAgendamento:
    def _mock_db_para_agendamento(self, db: AsyncMock) -> None:
        """Configura mocks de DB para simular Slot, Medico, Paciente e Consulta."""
        from unittest.mock import MagicMock

        slot_mock = MagicMock()
        slot_mock.id = 42
        slot_mock.medico_id = 10
        slot_mock.status = "DISPONIVEL"
        slot_mock.estabelecimento_id = 1

        medico_mock = MagicMock()
        medico_mock.id = 10
        medico_mock.especialidade_id = 4

        paciente_mock = MagicMock()
        paciente_mock.id = 99

        consulta_mock = MagicMock()
        consulta_mock.id = 200

        # scalars chain para diferentes queries
        def execute_side_effect(stmt):
            result = AsyncMock()
            sql = str(stmt)
            if "slots" in sql.lower():
                result.scalar_one_or_none = MagicMock(return_value=slot_mock)
            elif "medico" in sql.lower():
                result.scalar_one_or_none = MagicMock(return_value=medico_mock)
            elif "paciente" in sql.lower():
                result.scalar_one_or_none = MagicMock(return_value=None)  # paciente novo
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)
        db.flush = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 99))
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

    async def test_confirmacao_sim_retorna_estado_finalizado(self):
        """'Sim' em CONFIRMANDO deve retornar estado FINALIZADO."""
        svc = _make_service()
        dados = _dados_padrao(
            slot_id=42, contato_step="email",
            telefone="11999991234", email="claudio@test.com",
        )
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.CONFIRMANDO, dados, slots_temp=[_SLOT_TEMP])
        )
        self._mock_db_para_agendamento(svc.db)

        with patch("app.services.agenda_service.AgendaService.agendar_consulta", new_callable=AsyncMock) as mock_agendar:
            mock_consulta = MagicMock()
            mock_consulta.id = 200
            mock_agendar.return_value = mock_consulta

            resultado = await svc.processar_mensagem("test-token", "Sim")

        assert resultado["estado"] == ChatEstado.FINALIZADO

    async def test_confirmacao_sim_retorna_chave_confirmacao(self):
        """Resposta de confirmação deve conter chave 'confirmacao' para o frontend."""
        svc = _make_service()
        dados = _dados_padrao(
            slot_id=42, contato_step="email",
            telefone="11999991234", email="claudio@test.com",
        )
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.CONFIRMANDO, dados, slots_temp=[_SLOT_TEMP])
        )
        self._mock_db_para_agendamento(svc.db)

        with patch("app.services.agenda_service.AgendaService.agendar_consulta", new_callable=AsyncMock) as mock_agendar:
            mock_consulta = MagicMock()
            mock_consulta.id = 200
            mock_agendar.return_value = mock_consulta

            resultado = await svc.processar_mensagem("test-token", "Sim, confirmo")

        assert "confirmacao" in resultado
        assert resultado["confirmacao"] is not None

    async def test_confirmacao_nao_cancela_sem_criar_consulta(self):
        """'Não' em CONFIRMANDO deve cancelar sem chamar agendar_consulta."""
        svc = _make_service()
        dados = _dados_padrao(slot_id=42, telefone="11999991234", email="t@t.com")
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.CONFIRMANDO, dados, slots_temp=[_SLOT_TEMP])
        )

        with patch("app.services.agenda_service.AgendaService.agendar_consulta", new_callable=AsyncMock) as mock_agendar:
            resultado = await svc.processar_mensagem("test-token", "não, cancelar")

        mock_agendar.assert_not_called()
        assert resultado["estado"] == ChatEstado.FINALIZADO

    async def test_confirmacao_resposta_contem_horario(self):
        """Resposta de confirmação deve mencionar o horário marcado."""
        svc = _make_service()
        dados = _dados_padrao(
            slot_id=42, contato_step="email",
            telefone="11999991234", email="claudio@test.com",
        )
        svc.redis.get = AsyncMock(
            return_value=_session(ChatEstado.CONFIRMANDO, dados, slots_temp=[_SLOT_TEMP])
        )
        self._mock_db_para_agendamento(svc.db)

        with patch("app.services.agenda_service.AgendaService.agendar_consulta", new_callable=AsyncMock) as mock_agendar:
            mock_consulta = MagicMock()
            mock_consulta.id = 200
            mock_agendar.return_value = mock_consulta

            resultado = await svc.processar_mensagem("test-token", "sim")

        assert "09:00" in resultado["resposta"] or "08/04" in resultado["resposta"]


# ──────────────────────────────────────────────────────────────────────────────
# Bloco 4 — Prompt dinâmico com especialidades do banco
# ──────────────────────────────────────────────────────────────────────────────

class TestPromptDinamico:
    def test_obter_prompt_conversa_lista_especialidades_fornecidas(self):
        """obter_prompt_conversa(lista) deve incluir somente as especialidades passadas."""
        especialidades = ["Clínica Geral", "Cardiologia", "Ortopedia"]
        prompt = obter_prompt_conversa(especialidades)

        assert "Clínica Geral" in prompt
        assert "Cardiologia" in prompt
        assert "Ortopedia" in prompt
        # Especialidades que NÃO foram passadas não devem aparecer
        assert "Neurologia" not in prompt
        assert "Ginecologia" not in prompt

    def test_obter_prompt_conversa_sem_lista_usa_whitelist(self):
        """Sem lista → usa ESPECIALIDADES_WHITELIST como fallback."""
        prompt = obter_prompt_conversa(None)
        for esp in ESPECIALIDADES_WHITELIST:
            assert esp in prompt

    def test_obter_prompt_conversa_lista_vazia_usa_whitelist(self):
        """Lista vazia → fallback para ESPECIALIDADES_WHITELIST."""
        prompt = obter_prompt_conversa([])
        # Deve ter ao menos as especialidades básicas
        assert "Clinica Geral" in prompt or "Clínica Geral" in prompt

    def test_prompt_nao_instrui_despedida(self):
        """Prompt NÃO deve instruir o LLM a se despedir (pode proibir, não instruir)."""
        prompt = obter_prompt_conversa(["Clínica Geral"])
        prompt_lower = prompt.lower()
        # Essas frases instruem despedida — não devem existir
        assert "end the conversation with" not in prompt_lower
        assert "kind closing message" not in prompt_lower
        assert "diga boa sorte" not in prompt_lower
        assert "diga até mais" not in prompt_lower


# ──────────────────────────────────────────────────────────────────────────────
# Bloco 5 — Extração de especialidade com lista da sessão
# ──────────────────────────────────────────────────────────────────────────────

class TestExtracaoEspecialidade:
    def setup_method(self):
        self.svc = _make_service()
        self.lista_sessao = ["Clínica Geral", "Cardiologia", "Neurologia", "Ortopedia"]

    def test_extrai_especialidade_exata_da_lista_sessao(self):
        """Nome exato da lista da sessão é detectado no texto."""
        texto = "Recomendo uma consulta com Ortopedia."
        resultado = self.svc._extrair_especialidade_do_texto(texto, self.lista_sessao)
        assert resultado == "Ortopedia"

    def test_extrai_especialidade_case_insensitive(self):
        """Detecção é case-insensitive."""
        texto = "Recomendo uma consulta com CARDIOLOGIA para avaliação."
        resultado = self.svc._extrair_especialidade_do_texto(texto, self.lista_sessao)
        assert resultado == "Cardiologia"

    def test_sinonimo_ortopedista_mapeia_para_ortopedia(self):
        """'ortopedista' → 'Ortopedia' quando disponível na sessão."""
        texto = "Você precisa ver um ortopedista."
        resultado = self.svc._extrair_especialidade_do_texto(texto, self.lista_sessao)
        assert resultado == "Ortopedia"

    def test_nutricionista_mapeia_para_clinica_geral_disponivel(self):
        """'nutricionista' → fallback para 'Clínica Geral' (disponível na sessão)."""
        texto = "Recomendo que você consulte um nutricionista para orientação alimentar."
        resultado = self.svc._extrair_especialidade_do_texto(texto, self.lista_sessao)
        assert resultado == "Clínica Geral"

    def test_especialidade_inexistente_na_sessao_usa_fallback(self):
        """Especialidade mencionada que não existe na sessão → usa Clínica Geral da lista."""
        lista_restrita = ["Clínica Geral", "Cardiologia"]
        texto = "Recomendo consultar um neurologista."
        resultado = self.svc._extrair_especialidade_do_texto(texto, lista_restrita)
        # Neurologia não está na lista, mas Clínica Geral sim → fallback
        assert resultado == "Clínica Geral"

    def test_sem_especialidade_no_texto_retorna_none(self):
        """Texto sem especialidade reconhecível → retorna None."""
        texto = "Entendo que você está com desconforto. Há quanto tempo está sentindo isso?"
        resultado = self.svc._extrair_especialidade_do_texto(texto, self.lista_sessao)
        assert resultado is None

    def test_sem_lista_sessao_usa_whitelist(self):
        """Sem lista de sessão → cai para ESPECIALIDADES_WHITELIST."""
        texto = "Recomendo uma consulta com Ginecologia."
        resultado = self.svc._extrair_especialidade_do_texto(texto, None)
        assert resultado == "Ginecologia"


# ──────────────────────────────────────────────────────────────────────────────
# Bloco 6 — criar_sessao carrega especialidades do banco
# ──────────────────────────────────────────────────────────────────────────────

class TestCriarSessaoEspecialidades:
    async def test_criar_sessao_salva_especialidades_do_banco(self):
        """criar_sessao() deve consultar banco e salvar especialidades na sessão."""
        from unittest.mock import MagicMock

        svc = _make_service()

        # MagicMock (síncrono) para o resultado — scalars().all() não é async em SQLAlchemy 2.0
        esp_result = MagicMock()
        esp_result.scalars.return_value.all.return_value = [
            "Clínica Geral", "Cardiologia", "Ortopedia"
        ]
        svc.db.execute = AsyncMock(return_value=esp_result)

        await svc.criar_sessao(canal="PORTAL", estabelecimento_id=1)

        saved_raw = svc.redis.set.call_args[0][1]
        saved = json.loads(saved_raw)
        assert "especialidades" in saved
        assert len(saved["especialidades"]) == 3

    async def test_criar_sessao_sem_estabelecimento_id_lista_vazia(self):
        """Sem estabelecimento_id → especialidades = []."""
        svc = _make_service()

        await svc.criar_sessao(canal="PORTAL", estabelecimento_id=None)

        saved_raw = svc.redis.set.call_args[0][1]
        saved = json.loads(saved_raw)
        assert saved["especialidades"] == []
