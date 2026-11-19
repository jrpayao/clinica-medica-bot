"""Servico principal do chatbot IA.

Orquestra todos os modulos de IA seguindo a arquitetura em
docs/medbot_arquitetura.md:

  Mensagem → Emergencia? → Classificar → Rotear → LLM → Validar → Salvar Estado
"""

import json
import re
import uuid

import redis.asyncio as aioredis
import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agenda_service import AgendaService
from app.services.ia import billing
from app.services.ia.dados_paciente import localizar_por_nome, mascarar_cpf, normalizar_cpf
from app.services.ia.prompts import ESPECIALIDADES_WHITELIST, obter_params_llm, obter_prompt_conversa, obter_prompt_sistema
from app.services.ia.robustez import (
    FALLBACK_MESSAGE,
    extrair_json_llm,
    validar_especialidade,
    verificar_limite_perguntas,
)
from app.services.ia.router import obter_api_key, obter_base_url, selecionar_modelo
from app.services.ia.state_machine import (
    ChatEstado,
    estado_inicial,
    pode_transitar,
)
from app.services.ia.triagem import MENSAGEM_EMERGENCIA, detectar_emergencia

log = structlog.get_logger(__name__)

CHAT_SESSION_TTL = 1800  # 30 minutos

# Mapeamento estado → feature key para roteamento de modelos
_ESTADO_FEATURE: dict[str, str] = {
    # Fluxo guiado (v2)
    ChatEstado.START: "saudacao",
    ChatEstado.COLETANDO_NOME: "coleta_dados",
    ChatEstado.COLETANDO_CONVENIO: "coleta_dados",
    ChatEstado.OUVINDO_SINTOMAS: "coleta_dados",
    ChatEstado.SUGERINDO_ESPECIALIDADE: "triagem_clinica",
    ChatEstado.APRESENTANDO_SLOTS: "agendamento",
    ChatEstado.COLETANDO_CONTATO: "agendamento",
    ChatEstado.CONFIRMANDO: "agendamento",
    ChatEstado.FINALIZADO: "agendamento",
    # Fluxo legado (v1)
    ChatEstado.COLETANDO_SINTOMAS: "coleta_dados",
    ChatEstado.TRIAGEM: "triagem_clinica",
    ChatEstado.SUGESTAO_ESPECIALIDADE: "triagem_clinica",
    ChatEstado.ESCOLHA_ESPECIALIDADE: "agendamento",
    ChatEstado.ESCOLHA_MEDICO: "agendamento",
    ChatEstado.ESCOLHA_HORARIO: "agendamento",
    ChatEstado.CONFIRMACAO: "agendamento",
}

# Estados onde o BioMistral retorna JSON estruturado
_ESTADOS_TRIAGEM_JSON: set[str] = {
    ChatEstado.TRIAGEM,
    ChatEstado.SUGESTAO_ESPECIALIDADE,
}

# Frases com que o paciente costuma anteceder o próprio nome
_PREFIXO_NOME = re.compile(
    r"^\s*(?:ol[áa][,!.]?\s+|oi[,!.]?\s+)?"
    r"(?:(?:o\s+)?meu\s+nome\s+(?:é|e)|me\s+chamo|eu\s+me\s+chamo|(?:eu\s+)?sou|aqui\s+(?:é|e)|pode\s+me\s+chamar\s+de)"
    r"\s+(?:o\s+|a\s+)?",
    re.IGNORECASE,
)


RESPOSTA_PLANO_NAO_SEI = "Não sei informar"
RESPOSTA_SEM_CARTEIRINHA = "Não tenho em mãos"


def descrever_pagamento(dados_coletados: dict) -> str:
    """'Unimed — plano Especial', 'Unimed' ou 'Particular', conforme o que o paciente informou."""
    if dados_coletados.get("tipo_atendimento") != "CONVENIO" or not dados_coletados.get("convenio"):
        return "Particular"
    if dados_coletados.get("plano"):
        return f"{dados_coletados['convenio']} — plano {dados_coletados['plano']}"
    return dados_coletados["convenio"]


def descrever_horario(slot: dict) -> str:
    """Horário escolhido, por extenso. O nome do profissional já traz o tratamento cadastrado."""
    return f"{slot['data']} às {slot['hora_inicio']} com {slot['profissional_nome']}"


def extrair_nome_informado(mensagem: str) -> str:
    """Isola o nome quando o paciente responde com uma frase.

    "Meu nome é Pedro Oliveira." → "Pedro Oliveira"
    """
    nome = _PREFIXO_NOME.sub("", mensagem.strip(), count=1)
    return nome.strip(" .,!;:") or mensagem.strip()


# Estado inicial de dados coletados
_DADOS_COLETADOS_INICIAL: dict = {
    # Fluxo guiado (v2)
    "nome": None,
    "cpf": None,
    "convenio_id": None,
    "convenio": None,
    "plano_id": None,
    "plano": None,
    "convenio_step": None,  # None | "plano" (convênio escolhido, falta o plano)
    "tipo_atendimento": None,
    "telefone": None,
    "email": None,
    "slot_id_selecionado": None,
    "numero_carteirinha": None,
    "contato_step": "cpf",  # "cpf" | "carteirinha" (só convênio) | "telefone" | "email"
    # Legado + compartilhados
    "sintomas": [],
    "especialidade": None,
    "medico": None,
    "horario": None,
    "perguntas_coleta": 0,
}


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        redis: aioredis.Redis,
    ) -> None:
        self.db = db
        self.redis = redis

    def _criar_llm(self, modelo: str, feature: str = "saudacao") -> ChatOpenAI:
        """Cria instancia do LLM com parametros corretos para o modelo/feature."""
        params = obter_params_llm(modelo)
        temperature = params.pop("temperature", 0.3)
        model_kwargs = params  # top_p, repeat_penalty, etc.

        return ChatOpenAI(
            model=modelo,
            openai_api_key=obter_api_key(),
            openai_api_base=obter_base_url(),
            temperature=temperature,
            max_tokens=500,
            model_kwargs=model_kwargs if model_kwargs else {},
        )

    async def criar_sessao(self, canal: str = "PORTAL", estabelecimento_id: int | None = None) -> str:
        """Cria nova sessao de chat com token unico.

        Armazena o estabelecimento_id e as especialidades disponíveis no Redis
        para que o WebSocket (sem auth) construa prompts dinâmicos e aplique
        isolamento row-level corretamente.
        """
        from app.models.especialidade import Especialidade
        from sqlalchemy import select

        session_token = str(uuid.uuid4())

        # Buscar especialidades reais do estabelecimento no banco
        especialidades: list[str] = []
        if estabelecimento_id:
            result = await self.db.execute(
                select(Especialidade.nome)
                .where(
                    Especialidade.estabelecimento_id == estabelecimento_id,
                    Especialidade.ativo == True,  # noqa: E712
                )
                .order_by(Especialidade.nome)
            )
            especialidades = list(result.scalars().all())

        convenios = await self._carregar_convenios(estabelecimento_id) if estabelecimento_id else []

        session_data = {
            "token": session_token,
            "canal": canal,
            "estabelecimento_id": estabelecimento_id,
            "especialidades": especialidades,  # lista real da clínica
            "convenios": convenios,  # convênios aceitos, com os planos de cada um
            "mensagens": [],
            "estado": estado_inicial(),  # ChatEstado.START
            "dados_coletados": dict(_DADOS_COLETADOS_INICIAL),
        }

        await self.redis.set(
            f"chat:session:{session_token}",
            json.dumps(session_data),
            ex=CHAT_SESSION_TTL,
        )

        log.info("sessao_chat_criada", token=session_token[:8] + "...", canal=canal)
        return session_token

    async def _carregar_convenios(self, estabelecimento_id: int) -> list[dict]:
        """Convênios ativos da unidade com seus planos ativos, para os botões do chat."""
        from sqlalchemy import select

        from app.models.convenio import Convenio
        from app.models.convenio_plano import ConvenioPlano

        linhas = (
            await self.db.execute(
                select(Convenio.id, Convenio.nome, ConvenioPlano.id, ConvenioPlano.nome)
                .outerjoin(
                    ConvenioPlano,
                    (ConvenioPlano.convenio_id == Convenio.id) & (ConvenioPlano.ativo == True),  # noqa: E712
                )
                .where(
                    Convenio.estabelecimento_id == estabelecimento_id,
                    Convenio.ativo == True,  # noqa: E712
                )
                .order_by(Convenio.nome, ConvenioPlano.nome)
            )
        ).all()

        por_id: dict[int, dict] = {}
        for conv_id, conv_nome, plano_id, plano_nome in linhas:
            convenio = por_id.setdefault(conv_id, {"id": conv_id, "nome": conv_nome, "planos": []})
            if plano_id is not None:
                convenio["planos"].append({"id": plano_id, "nome": plano_nome})
        return list(por_id.values())

    @staticmethod
    def _extras_de_interface(estado: str, dados_coletados: dict, convenios_sessao: list[dict]) -> dict:
        """Botões que acompanham a pergunta do convênio: operadoras aceitas ou planos da escolhida."""
        if estado != ChatEstado.COLETANDO_CONVENIO or not convenios_sessao:
            return {}
        if dados_coletados.get("convenio_step") == "plano":
            escolhido = next(
                (c for c in convenios_sessao if c["id"] == dados_coletados.get("convenio_id")), None
            )
            planos = [p["nome"] for p in (escolhido or {}).get("planos", [])]
            return {"quick_replies": [*planos, RESPOSTA_PLANO_NAO_SEI]}
        return {"convenios": [{"id": c["id"], "nome": c["nome"]} for c in convenios_sessao]}

    async def _carregar_sessao(self, session_token: str) -> dict | None:
        """Carrega sessao do Redis."""
        data = await self.redis.get(f"chat:session:{session_token}")
        if data is None:
            return None
        return json.loads(data)

    async def _salvar_sessao(self, session_token: str, session_data: dict) -> None:
        """Salva sessao no Redis com TTL renovado."""
        await self.redis.set(
            f"chat:session:{session_token}",
            json.dumps(session_data),
            ex=CHAT_SESSION_TTL,
        )

    # Sinônimos comuns que o LLM usa mas não estão na whitelist canonical
    _SINONIMOS_ESPECIALIDADE: dict[str, str] = {
        "medicina geral": "Clinica Geral",
        "clínico geral": "Clinica Geral",
        "clinico geral": "Clinica Geral",
        "clínica geral": "Clinica Geral",
        "clinica geral": "Clinica Geral",
        "médico geral": "Clinica Geral",
        "medico geral": "Clinica Geral",
        "nutricionista": "Clinica Geral",
        "nutricionist": "Clinica Geral",
        "nutrição": "Clinica Geral",
        "nutricao": "Clinica Geral",
        "endocrinologista": "Clinica Geral",
        "médico de família": "Medicina de Familia",
        "medico de familia": "Medicina de Familia",
        "médico da família": "Medicina de Familia",
        "medicina de família": "Medicina de Familia",
        "ortopedista": "Ortopedia",
        "cardiologista": "Cardiologia",
        "neurologista": "Neurologia",
        "dermatologista": "Dermatologia",
        "gastroenterologista": "Gastroenterologia",
        "pneumologista": "Pneumologia",
        "oftalmologista": "Oftalmologia",
        "otorrinolaringologista": "Otorrinolaringologia",
        "psiquiatra": "Psiquiatria",
        "urologista": "Urologia",
        "ginecologista": "Ginecologia",
        "infectologista": "Infectologia",
    }

    def _extrair_especialidade_do_texto(
        self, texto: str, especialidades_sessao: list[str] | None = None
    ) -> str | None:
        """Detecta especialidade mencionada no texto livre do LLM.

        Prioridade:
        1. Especialidades reais da sessão (banco de dados do estabelecimento)
        2. Sinônimos mapeados para o nome canônico da sessão
        3. Whitelist estática como fallback
        """
        texto_lower = texto.lower()
        lista = especialidades_sessao or ESPECIALIDADES_WHITELIST

        # 1. Verificar especialidades reais da sessão (nome exato ou parcial)
        for esp in lista:
            if esp.lower() in texto_lower:
                return esp

        # 2. Verificar sinônimos → mapear para nome canônico da sessão se possível
        for sinonimo, canonical in self._SINONIMOS_ESPECIALIDADE.items():
            if sinonimo in texto_lower:
                # Checar se o canonical existe na lista da sessão
                for esp in lista:
                    if esp.lower() == canonical.lower() or canonical.lower() in esp.lower():
                        return esp
                # Se não existir na sessão, usar Clínica Geral como fallback
                for esp in lista:
                    if "cl" in esp.lower() and "ger" in esp.lower():
                        return esp
                # Último recurso: primeiro item da lista
                if lista:
                    return lista[0]

        return None

    def _extrair_especialidade_original_do_texto(self, texto: str) -> str | None:
        """Retorna o nome do profissional mencionado no texto (antes do mapeamento).

        Usado para comunicar ao paciente quando a especialidade foi adaptada.
        Ex: 'nutricionista' → 'nutricionista' (nome original mencionado pelo LLM)
        """
        texto_lower = texto.lower()
        for sinonimo in self._SINONIMOS_ESPECIALIDADE:
            if sinonimo in texto_lower:
                return sinonimo
        return None

    def _determinar_proximo_estado(
        self,
        estado_atual: str,
        dados_coletados: dict,
        json_resposta: dict | None,
        resposta_texto: str = "",
        especialidades_sessao: list[str] | None = None,
    ) -> str:
        """Determina o proximo estado com base no estado atual e resposta do LLM.

        Fluxo guiado v2 (estados gerenciados aqui):
        - START              → COLETANDO_NOME: sempre na primeira mensagem
        - OUVINDO_SINTOMAS   → SUGERINDO_ESPECIALIDADE: quando LLM menciona especialidade no texto
        - SUGERINDO_ESPECIALIDADE → APRESENTANDO_SLOTS: transição imediata (slots buscados em _buscar_slots)

        Fluxo legado v1 (retrocompatibilidade):
        - COLETANDO_SINTOMAS → TRIAGEM: quando perguntas_coleta >= MAX ou fase=sugestao
        - TRIAGEM            → SUGESTAO_ESPECIALIDADE: quando BioMistral retorna fase=sugestao

        Estados de coleta de dados (COLETANDO_NOME, COLETANDO_CONVENIO) são
        tratados em _resposta_direta_fluxo_guiado sem passar por aqui.
        Estados de booking (COLETANDO_CONTATO, CONFIRMANDO, FINALIZADO) avançam
        via lógica dedicada no processamento de confirmação de slot.
        """
        if estado_atual == ChatEstado.START:
            if pode_transitar(ChatEstado.START, ChatEstado.COLETANDO_NOME):
                return ChatEstado.COLETANDO_NOME

        # Fluxo guiado v2: detectar recomendação de especialidade no texto livre
        if estado_atual == ChatEstado.OUVINDO_SINTOMAS:
            esp = self._extrair_especialidade_do_texto(resposta_texto, especialidades_sessao)
            if esp:
                dados_coletados["especialidade"] = esp
                # Salvar nome original mencionado (p.ex. "nutricionista") para adaptar mensagem
                esp_original = self._extrair_especialidade_original_do_texto(resposta_texto)
                if esp_original and esp_original.lower() != esp.lower():
                    dados_coletados["especialidade_original"] = esp_original
                else:
                    dados_coletados.pop("especialidade_original", None)
                if pode_transitar(ChatEstado.OUVINDO_SINTOMAS, ChatEstado.SUGERINDO_ESPECIALIDADE):
                    return ChatEstado.SUGERINDO_ESPECIALIDADE
            return estado_atual

        if estado_atual == ChatEstado.SUGERINDO_ESPECIALIDADE:
            if pode_transitar(ChatEstado.SUGERINDO_ESPECIALIDADE, ChatEstado.APRESENTANDO_SLOTS):
                return ChatEstado.APRESENTANDO_SLOTS
            return estado_atual

        if estado_atual == ChatEstado.COLETANDO_SINTOMAS:
            total_perguntas = dados_coletados.get("perguntas_coleta", 0)
            fase_llm = json_resposta.get("fase") if json_resposta else None
            deve_avancar = (
                not verificar_limite_perguntas(total_perguntas)
                or fase_llm == "sugestao"
            )
            if deve_avancar and pode_transitar(
                ChatEstado.COLETANDO_SINTOMAS, ChatEstado.TRIAGEM
            ):
                return ChatEstado.TRIAGEM

        if estado_atual == ChatEstado.TRIAGEM:
            fase_llm = json_resposta.get("fase") if json_resposta else None
            if fase_llm == "sugestao" and pode_transitar(
                ChatEstado.TRIAGEM, ChatEstado.SUGESTAO_ESPECIALIDADE
            ):
                return ChatEstado.SUGESTAO_ESPECIALIDADE

        return estado_atual  # sem transicao automatica para estados de booking

    def _resposta_direta_fluxo_guiado(
        self,
        estado_atual: str,
        mensagem: str,
        dados_coletados: dict,
        convenios_sessao: list[dict] | None = None,
    ) -> tuple[str, str] | None:
        """Retorna (resposta, proximo_estado) para estados com resposta direta (sem LLM).

        Retorna None quando o estado requer LLM.
        """
        if estado_atual == ChatEstado.START:
            # Sempre resposta direta no estado inicial — nunca chamar LLM aqui
            return (
                "Olá! Sou o MedBot, assistente de agendamento médico. "
                "Para começar, qual é o seu nome completo?",
                ChatEstado.COLETANDO_NOME,
            )

        if estado_atual == ChatEstado.COLETANDO_NOME:
            nome_atual = dados_coletados.get("nome")
            msg_stripped = mensagem.strip()
            # Mensagem curta ou saudacao generica → pedir nome
            saudacoes = {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "hello", "hi"}
            e_saudacao = msg_stripped.lower() in saudacoes or len(msg_stripped) <= 2
            if nome_atual is None and e_saudacao:
                return ("Qual é o seu nome completo?", ChatEstado.COLETANDO_NOME)
            if nome_atual is None and not e_saudacao:
                # Considera a mensagem como o nome informado
                nome_informado = extrair_nome_informado(msg_stripped)
                dados_coletados["nome"] = nome_informado
                return (
                    f"Obrigado, {nome_informado.split()[0]}! Você possui convênio médico ou plano de saúde?",
                    ChatEstado.COLETANDO_CONVENIO,
                )
            # Nome ja coletado — avancar
            return ("Você possui convênio médico ou plano de saúde?", ChatEstado.COLETANDO_CONVENIO)

        if estado_atual == ChatEstado.COLETANDO_CONVENIO and dados_coletados.get("convenio_step") == "plano":
            # Convênio já escolhido: a resposta é o plano (ou "não sei", que não vira particular)
            escolhido = next(
                (c for c in (convenios_sessao or []) if c["id"] == dados_coletados.get("convenio_id")), None
            )
            plano = localizar_por_nome(mensagem, (escolhido or {}).get("planos", []))
            dados_coletados["plano_id"] = plano["id"] if plano else None
            dados_coletados["plano"] = plano["nome"] if plano else None
            dados_coletados["convenio_step"] = None
            return (
                "Anotado. Agora me conte o que está sentindo para que possamos encontrar o especialista certo.",
                ChatEstado.OUVINDO_SINTOMAS,
            )

        if estado_atual == ChatEstado.COLETANDO_CONVENIO:
            msg_lower = mensagem.lower().strip()
            palavras_negacao = (
                "nao", "não", "particular", "sem convenio", "sem plano",
                "nenhum", "nenhuma", "n tenho", "não tenho", "nao tenho",
            )
            saudacoes = ("oi", "olá", "ola", "ola!", "oi!", "bom dia", "boa tarde", "boa noite", "tudo bem", "tudo bom")
            particular = any(p in msg_lower for p in palavras_negacao)
            e_saudacao = any(msg_lower == s or msg_lower.startswith(s) for s in saudacoes)
            if particular:
                dados_coletados["tipo_atendimento"] = "PARTICULAR"
                return (
                    "Certo, atendimento particular. Me conte o que está sentindo.",
                    ChatEstado.OUVINDO_SINTOMAS,
                )
            if e_saudacao or len(msg_lower) <= 2:
                nome = dados_coletados.get("nome", "").split()[0] if dados_coletados.get("nome") else ""
                saudacao = f"{nome}, você" if nome else "Você"
                return (
                    f"{saudacao} possui convênio médico ou plano de saúde?",
                    ChatEstado.COLETANDO_CONVENIO,
                )
            # Unidade com convênios cadastrados: só aceita os da lista
            if convenios_sessao:
                convenio = localizar_por_nome(mensagem, convenios_sessao)
                if convenio is None:
                    aceitos = ", ".join(c["nome"] for c in convenios_sessao)
                    return (
                        f"Não encontrei esse convênio entre os que atendemos aqui: {aceitos}. "
                        "Escolha um deles ou siga como particular.",
                        ChatEstado.COLETANDO_CONVENIO,
                    )
                dados_coletados["tipo_atendimento"] = "CONVENIO"
                dados_coletados["convenio_id"] = convenio["id"]
                dados_coletados["convenio"] = convenio["nome"]
                if convenio.get("planos"):
                    dados_coletados["convenio_step"] = "plano"
                    return (f"Qual é o seu plano {convenio['nome']}?", ChatEstado.COLETANDO_CONVENIO)
                return (
                    f"Perfeito, {convenio['nome']}. Agora me conte o que está sentindo "
                    "para que possamos encontrar o especialista certo.",
                    ChatEstado.OUVINDO_SINTOMAS,
                )

            # Unidade sem convênios cadastrados: registra o que o paciente informou
            dados_coletados["tipo_atendimento"] = "CONVENIO"
            dados_coletados["convenio"] = mensagem.strip()
            nome = dados_coletados.get("nome", "").split()[0] if dados_coletados.get("nome") else ""
            saudacao = f"Perfeito, {nome}!" if nome else "Perfeito!"
            return (
                f"{saudacao} Agora me conte o que está sentindo para que possamos encontrar o especialista certo.",
                ChatEstado.OUVINDO_SINTOMAS,
            )

        # SUGERINDO_ESPECIALIDADE: usuário confirma que quer agendar → mostrar slots (sem LLM)
        if estado_atual == ChatEstado.SUGERINDO_ESPECIALIDADE:
            msg_lower = mensagem.lower()
            nao_quer = any(p in msg_lower for p in (
                "nao", "não", "urgente", "pronto", "emergencia", "emergência", "samu"
            ))
            if nao_quer:
                return (
                    "Entendido. Se precisar de atendimento urgente, procure um pronto-socorro ou ligue para o SAMU 192. Posso ajudar com mais alguma coisa?",
                    ChatEstado.FINALIZADO,
                )
            # Qualquer outra resposta = quer agendar → avançar para APRESENTANDO_SLOTS
            esp = dados_coletados.get("especialidade", "Clínica Geral")
            return (
                f"Ótimo! Aqui estão os horários disponíveis com {esp}:",
                ChatEstado.APRESENTANDO_SLOTS,
            )

        # OUVINDO_SINTOMAS: usuário diz explicitamente que quer agendar (antes do LLM sugerir)
        if estado_atual == ChatEstado.OUVINDO_SINTOMAS:
            msg_lower = mensagem.lower()
            quer_agendar = any(p in msg_lower for p in (
                "quero agendar", "gostaria de agendar", "marcar consulta",
                "agendar consulta", "fazer agendamento",
            ))
            if quer_agendar and dados_coletados.get("especialidade"):
                esp = dados_coletados["especialidade"]
                return (
                    f"Ótimo! Aqui estão os horários disponíveis com {esp}:",
                    ChatEstado.APRESENTANDO_SLOTS,
                )

        return None

    async def processar_mensagem(
        self,
        session_token: str,
        mensagem: str,
        session_id_db: int | None = None,
    ) -> dict:
        """Processa mensagem seguindo o fluxo arquitetural completo.

        Fluxo:
        1. Carregar sessao
        2. EMERGENCIA? → retornar SAMU sem LLM (Regra de Ouro)
        3. Determinar feature/modelo baseado no estado
        4. Chamar LLM com prompt e parametros corretos
        5. Para estados de triagem: extrair JSON, validar especialidade
        6. Verificar limite de perguntas
        7. Determinar proximo estado
        8. Registrar billing
        9. Salvar sessao atualizada
        10. Retornar resposta formatada
        """
        # 1. Carregar sessao
        session_data = await self._carregar_sessao(session_token)
        if session_data is None:
            return {
                "resposta": "Sessao expirada. Por favor, inicie uma nova conversa.",
                "sessao_expirada": True,
                "emergencia": False,
            }

        estado_atual = session_data.get("estado", ChatEstado.START)
        mensagens = session_data.get("mensagens", [])
        dados_coletados = session_data.get("dados_coletados", dict(_DADOS_COLETADOS_INICIAL))
        especialidades_sessao: list[str] = session_data.get("especialidades", [])
        convenios_sessao: list[dict] = session_data.get("convenios") or []

        # 2. REGRA DE OURO: emergencia sempre verificada ANTES do LLM
        if detectar_emergencia(mensagem):
            log.warning(
                "emergencia_detectada_chat",
                token=session_token[:8] + "...",
                estado=estado_atual,
            )
            mensagens.append({"role": "user", "content": mensagem})
            mensagens.append({"role": "assistant", "content": MENSAGEM_EMERGENCIA})
            session_data["mensagens"] = mensagens
            await self._salvar_sessao(session_token, session_data)

            return {
                "resposta": MENSAGEM_EMERGENCIA,
                "estado": estado_atual,
                "emergencia": True,
                "sessao_expirada": False,
            }

        # 3a. Estados assíncronos do fluxo guiado (requerem acesso ao DB)
        if estado_atual == ChatEstado.APRESENTANDO_SLOTS and mensagem.startswith("confirmar:"):
            return await self._processar_slot_selecionado(
                session_token, session_data, mensagem, dados_coletados, mensagens
            )

        if estado_atual == ChatEstado.COLETANDO_CONTATO:
            return await self._processar_coleta_contato(
                session_token, session_data, mensagem, dados_coletados, mensagens
            )

        if estado_atual == ChatEstado.CONFIRMANDO:
            return await self._processar_criar_agendamento(
                session_token, session_data, mensagem, dados_coletados, mensagens
            )

        # 3b. Fluxo guiado: estados com resposta direta (sem LLM)
        resposta_direta = self._resposta_direta_fluxo_guiado(
            estado_atual, mensagem, dados_coletados, convenios_sessao
        )
        if resposta_direta is not None:
            resposta_texto, proximo_estado = resposta_direta
            mensagens.append({"role": "user", "content": mensagem})
            mensagens.append({"role": "assistant", "content": resposta_texto})
            session_data["mensagens"] = mensagens
            session_data["estado"] = proximo_estado
            session_data["dados_coletados"] = dados_coletados
            await self._salvar_sessao(session_token, session_data)
            resultado_direto: dict = {
                "resposta": resposta_texto,
                "estado": proximo_estado,
                "modelo_usado": None,
                "emergencia": False,
                "fallback": False,
                "sessao_expirada": False,
                **self._extras_de_interface(proximo_estado, dados_coletados, convenios_sessao),
            }
            # Buscar slots quando avança para APRESENTANDO_SLOTS via resposta direta
            if proximo_estado == ChatEstado.APRESENTANDO_SLOTS:
                slots = await self._buscar_slots(session_data, dados_coletados)
                if slots:
                    session_data["slots_temp"] = slots
                    await self._salvar_sessao(session_token, session_data)
                    resultado_direto["slots_sugeridos"] = slots
                else:
                    resultado_direto["resposta"] = (
                        resposta_texto
                        + "\n\nNo momento não encontrei horários disponíveis. "
                        "Entre em contato com a recepção para verificar disponibilidade."
                    )
            return resultado_direto

        # 3. Determinar feature e modelo para este estado
        feature = _ESTADO_FEATURE.get(estado_atual, "saudacao")
        modelo = selecionar_modelo(feature)
        # Prompt dinâmico com especialidades reais da clínica para estado de conversa
        if feature not in ("triagem_clinica", "rag_protocolo"):
            system_prompt = obter_prompt_conversa(especialidades_sessao or None)
        else:
            system_prompt = obter_prompt_sistema(feature)

        # 4. Construir historico e chamar LLM
        messages = [SystemMessage(content=system_prompt)]
        for msg in mensagens:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=mensagem))

        llm = self._criar_llm(modelo, feature=feature)
        resposta_ai = await llm.ainvoke(messages)

        resposta_texto = resposta_ai.content
        token_usage = resposta_ai.response_metadata.get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)

        # 5. Estados de triagem: extrair JSON, validar especialidade
        json_resposta: dict | None = None
        fallback_ativado = False

        if estado_atual in _ESTADOS_TRIAGEM_JSON:
            json_resposta = extrair_json_llm(resposta_texto)

            if json_resposta is None:
                # JSON invalido — usar fallback sem propagar erro ao paciente
                log.warning("triagem_json_invalido", estado=estado_atual)
                fallback_ativado = True
                resposta_texto = FALLBACK_MESSAGE
            else:
                # Validar especialidades retornadas pelo LLM
                especialidades_llm = json_resposta.get("especialidades", [])
                if especialidades_llm:
                    especialidade_validada = validar_especialidade(especialidades_llm[0])
                    dados_coletados["especialidade"] = especialidade_validada
                    # Normalizar no JSON tambem
                    json_resposta["especialidades"] = [especialidade_validada]

                # Formatar resposta para o paciente
                if json_resposta.get("fase") == "coleta" and json_resposta.get("pergunta"):
                    resposta_texto = json_resposta["pergunta"]
                elif json_resposta.get("fase") == "sugestao":
                    esp = dados_coletados.get("especialidade", "Clinica Geral")
                    just = json_resposta.get("justificativa", "")
                    resposta_texto = (
                        f"Com base nos seus sintomas, a especialidade indicada e: **{esp}**.\n"
                        f"{just}\n\nDeseja agendar com essa especialidade?"
                    )

        # 6. Incrementar contador de perguntas em COLETANDO_SINTOMAS
        if estado_atual == ChatEstado.COLETANDO_SINTOMAS:
            dados_coletados["perguntas_coleta"] = dados_coletados.get("perguntas_coleta", 0) + 1

        # 7. Determinar proximo estado
        proximo_estado = self._determinar_proximo_estado(
            estado_atual, dados_coletados, json_resposta, resposta_texto,
            especialidades_sessao=especialidades_sessao,
        )

        # 8. Registrar billing (obrigatorio)
        if session_id_db:
            feature_billing = "TRIAGEM" if feature == "triagem_clinica" else "GERAL"
            await billing.registrar_uso(
                db=self.db,
                session_id=session_id_db,
                modelo=modelo,
                feature=feature_billing,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estabelecimento_id=session_data.get("estabelecimento_id"),
            )

        # 9. Salvar sessao atualizada
        mensagens.append({"role": "user", "content": mensagem})
        mensagens.append({"role": "assistant", "content": resposta_texto})
        session_data["mensagens"] = mensagens
        session_data["estado"] = proximo_estado
        session_data["dados_coletados"] = dados_coletados

        await self._salvar_sessao(session_token, session_data)

        log.info(
            "mensagem_processada",
            token=session_token[:8] + "...",
            estado_de=estado_atual,
            estado_para=proximo_estado,
            modelo=modelo,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        resultado: dict = {
            "resposta": resposta_texto,
            "estado": proximo_estado,
            "modelo_usado": modelo,
            "emergencia": False,
            "fallback": fallback_ativado,
            "sessao_expirada": False,
        }

        # 10. Se avançou para SUGERINDO_ESPECIALIDADE via LLM: substituir texto do LLM por
        # mensagem direta e ir reto para APRESENTANDO_SLOTS com os slots disponíveis.
        if proximo_estado == ChatEstado.SUGERINDO_ESPECIALIDADE:
            esp = dados_coletados.get("especialidade", "Clínica Geral")
            esp_original = dados_coletados.get("especialidade_original")
            slots = await self._buscar_slots(session_data, dados_coletados)
            if slots:
                if esp_original and esp_original.lower() != esp.lower():
                    intro = (
                        f"Para o seu caso, o ideal seria um **{esp_original}**, "
                        f"mas esta clínica oferece **{esp}**, que pode ajudá-lo com orientação e encaminhamento. "
                        "Aqui estão os horários disponíveis:"
                    )
                else:
                    intro = f"Com base nos seus sintomas, recomendo uma consulta com **{esp}**. Aqui estão os horários disponíveis:"
                resposta_texto = intro
                proximo_estado = ChatEstado.APRESENTANDO_SLOTS
                session_data["slots_temp"] = slots
                resultado["slots_sugeridos"] = slots
            else:
                resposta_texto = (
                    f"Com base nos seus sintomas, recomendo uma consulta com **{esp}**. "
                    "No momento não encontrei horários disponíveis. "
                    "Entre em contato com a recepção para verificar disponibilidade."
                )
                proximo_estado = ChatEstado.FINALIZADO

            # Atualizar resposta e estado no resultado e na sessão
            resultado["resposta"] = resposta_texto
            resultado["estado"] = proximo_estado
            session_data["estado"] = proximo_estado
            # Corrigir última mensagem do assistente no histórico
            if mensagens and mensagens[-1]["role"] == "assistant":
                mensagens[-1]["content"] = resposta_texto
                session_data["mensagens"] = mensagens
            await self._salvar_sessao(session_token, session_data)

        elif proximo_estado == ChatEstado.APRESENTANDO_SLOTS:
            slots = await self._buscar_slots(session_data, dados_coletados)
            if slots:
                session_data["slots_temp"] = slots
                await self._salvar_sessao(session_token, session_data)
                resultado["slots_sugeridos"] = slots
            else:
                resultado["resposta"] = (
                    resposta_texto
                    + "\n\nNo momento não encontrei horários disponíveis para essa especialidade. "
                    "Por favor, entre em contato com a recepção para verificar disponibilidade."
                )

        return resultado

    async def _buscar_slots(self, session_data: dict, dados_coletados: dict) -> list[dict]:
        """Busca até 5 slots disponíveis na agenda para a especialidade detectada.

        Usa o estabelecimento_id salvo na sessão para garantir isolamento.
        Resolve o especialidade_id pelo nome (ilike) antes de consultar a agenda.
        Retorna lista serializada no formato esperado pelo frontend (SlotSugerido).
        """
        from app.models.especialidade import Especialidade
        from app.models.profissional import Profissional
        from sqlalchemy import select

        estabelecimento_id = session_data.get("estabelecimento_id")
        if not estabelecimento_id:
            return []

        especialidade_nome = dados_coletados.get("especialidade")

        # Resolver especialidade_id pelo nome
        especialidade_id = None
        if especialidade_nome:
            result = await self.db.execute(
                select(Especialidade).where(
                    Especialidade.nome.ilike(f"%{especialidade_nome}%"),
                    Especialidade.estabelecimento_id == estabelecimento_id,
                )
            )
            esp = result.scalar_one_or_none()
            if esp:
                especialidade_id = esp.id

        agenda = AgendaService(self.db)
        slots = await agenda.buscar_disponibilidade(
            estabelecimento_id=estabelecimento_id,
            especialidade_id=especialidade_id,
            convenio_id=dados_coletados.get("convenio_id"),
        )

        # Carregar nomes dos profissionais e serializar para o frontend
        result_slots = []
        for slot in slots[:5]:  # máximo 5 slots
            profissional_result = await self.db.execute(
                select(Profissional).where(Profissional.id == slot.profissional_id)
            )
            profissional = profissional_result.scalar_one_or_none()
            result_slots.append({
                "id": slot.id,
                "data": slot.data.strftime("%d/%m/%Y"),
                "hora_inicio": slot.hora_inicio.strftime("%H:%M"),
                "hora_fim": slot.hora_fim.strftime("%H:%M"),
                "profissional_nome": profissional.nome if profissional else "Profissional",
            })

        return result_slots

    async def _processar_slot_selecionado(
        self,
        session_token: str,
        session_data: dict,
        mensagem: str,
        dados_coletados: dict,
        mensagens: list,
    ) -> dict:
        """Usuário selecionou um slot. Pede telefone de contato."""
        try:
            slot_id = int(mensagem.split(":")[1])
        except (IndexError, ValueError):
            return {"resposta": "Slot inválido. Por favor, selecione um horário da lista.", "estado": ChatEstado.APRESENTANDO_SLOTS, "emergencia": False, "sessao_expirada": False}

        dados_coletados["slot_id_selecionado"] = slot_id
        dados_coletados["contato_step"] = "cpf"

        # Buscar info do slot para mostrar ao usuário
        slot_desc = "o horário selecionado"
        for s in session_data.get("slots_temp", []):
            if s["id"] == slot_id:
                slot_desc = descrever_horario(s)
                break

        nome = (dados_coletados.get("nome") or "").split()[0]
        saudacao = f"{nome}, " if nome else ""
        resposta = (
            f"Ótimo, {saudacao}você escolheu {slot_desc}.\n\n"
            "Para finalizar o agendamento, preciso de mais algumas informações.\n\n"
            "Qual é o seu **CPF**?"
        )

        mensagens.append({"role": "user", "content": mensagem})
        mensagens.append({"role": "assistant", "content": resposta})
        session_data["mensagens"] = mensagens
        session_data["estado"] = ChatEstado.COLETANDO_CONTATO
        session_data["dados_coletados"] = dados_coletados
        await self._salvar_sessao(session_token, session_data)

        return {
            "resposta": resposta,
            "estado": ChatEstado.COLETANDO_CONTATO,
            "emergencia": False,
            "sessao_expirada": False,
        }

    async def _processar_coleta_contato(
        self,
        session_token: str,
        session_data: dict,
        mensagem: str,
        dados_coletados: dict,
        mensagens: list,
    ) -> dict:
        """Coleta CPF, telefone e e-mail, um por vez."""
        step = dados_coletados.get("contato_step", "cpf")
        extras: dict = {}

        if step == "cpf":
            cpf = normalizar_cpf(mensagem)
            proximo_estado = ChatEstado.COLETANDO_CONTATO
            if cpf is None:
                resposta = "Não consegui validar esse CPF. Confira os 11 números e envie de novo, por favor."
            else:
                dados_coletados["cpf"] = cpf
                if dados_coletados.get("tipo_atendimento") == "CONVENIO" and dados_coletados.get("convenio_id"):
                    dados_coletados["contato_step"] = "carteirinha"
                    resposta = (
                        f"Obrigado! Qual é o **número da sua carteirinha** {dados_coletados.get('convenio') or ''}?"
                    ).replace(" ?", "?")
                    extras = {"quick_replies": [RESPOSTA_SEM_CARTEIRINHA]}
                else:
                    dados_coletados["contato_step"] = "telefone"
                    resposta = "Obrigado! Qual é o seu **telefone de contato**? (com DDD)"

        elif step == "carteirinha":
            numero = re.sub(r"[^0-9A-Za-z]", "", mensagem)
            tem_numero = any(c.isdigit() for c in numero) and len(numero) >= 5
            dados_coletados["numero_carteirinha"] = numero[:50] if tem_numero else None
            dados_coletados["contato_step"] = "telefone"
            proximo_estado = ChatEstado.COLETANDO_CONTATO
            resposta = (
                "Anotado! Qual é o seu **telefone de contato**? (com DDD)"
                if tem_numero
                else "Sem problema, a recepção confere no dia. Qual é o seu **telefone de contato**? (com DDD)"
            )

        elif step == "telefone":
            telefone = mensagem.strip()
            dados_coletados["telefone"] = telefone
            dados_coletados["contato_step"] = "email"

            resposta = f"Perfeito! Agora informe seu **e-mail** para receber a confirmação:"
            proximo_estado = ChatEstado.COLETANDO_CONTATO

        else:  # step == "email"
            email = mensagem.strip()
            dados_coletados["email"] = email

            # Montar resumo para confirmação
            nome = dados_coletados.get("nome") or "Paciente"
            telefone = dados_coletados.get("telefone") or "—"
            especialidade = dados_coletados.get("especialidade") or "Clínica Geral"
            slot_desc = "horário selecionado"
            for s in session_data.get("slots_temp", []):
                if s["id"] == dados_coletados.get("slot_id_selecionado"):
                    slot_desc = descrever_horario(s)
                    break

            resposta = (
                "Confira os dados do seu agendamento:\n\n"
                f"**Nome:** {nome}\n"
                f"**CPF:** {mascarar_cpf(dados_coletados.get('cpf'))}\n"
                f"**Atendimento:** {descrever_pagamento(dados_coletados)}\n"
                + (
                    f"**Carteirinha:** {dados_coletados['numero_carteirinha']}\n"
                    if dados_coletados.get("numero_carteirinha")
                    else ""
                )
                + f"**Especialidade:** {especialidade}\n"
                f"**Horário:** {slot_desc}\n"
                f"**Telefone:** {telefone}\n"
                f"**E-mail:** {email}\n\n"
                "Deseja confirmar o agendamento? Responda **Sim** para confirmar."
            )
            proximo_estado = ChatEstado.CONFIRMANDO

        mensagens.append({"role": "user", "content": mensagem})
        mensagens.append({"role": "assistant", "content": resposta})
        session_data["mensagens"] = mensagens
        session_data["estado"] = proximo_estado
        session_data["dados_coletados"] = dados_coletados
        await self._salvar_sessao(session_token, session_data)

        return {
            "resposta": resposta,
            "estado": proximo_estado,
            "emergencia": False,
            "sessao_expirada": False,
            **extras,
        }

    async def _processar_criar_agendamento(
        self,
        session_token: str,
        session_data: dict,
        mensagem: str,
        dados_coletados: dict,
        mensagens: list,
    ) -> dict:
        """Cria o agendamento no banco após confirmação do usuário."""
        from app.models.cliente import Cliente, ModalidadePagamento
        from app.schemas.atendimento import AtendimentoCreate
        from sqlalchemy import select

        msg_lower = mensagem.lower()
        nao_confirma = any(p in msg_lower for p in ("nao", "não", "cancelar", "cancel", "voltar", "errado"))

        if nao_confirma:
            resposta = "Agendamento cancelado. Se quiser remarcar, estou aqui para ajudar!"
            mensagens.append({"role": "user", "content": mensagem})
            mensagens.append({"role": "assistant", "content": resposta})
            session_data["mensagens"] = mensagens
            session_data["estado"] = ChatEstado.FINALIZADO
            session_data["dados_coletados"] = dados_coletados
            await self._salvar_sessao(session_token, session_data)
            return {"resposta": resposta, "estado": ChatEstado.FINALIZADO, "emergencia": False, "sessao_expirada": False}

        estabelecimento_id = session_data.get("estabelecimento_id")
        slot_id = dados_coletados.get("slot_id_selecionado")
        nome = dados_coletados.get("nome") or "Paciente"
        telefone = dados_coletados.get("telefone") or ""
        email = dados_coletados.get("email") or ""
        cpf = dados_coletados.get("cpf")

        if slot_id and estabelecimento_id and not cpf:
            # Sessão antiga ou canal que pulou a etapa: nunca gravar cadastro sem documento
            resposta = "Antes de confirmar, preciso do seu **CPF**."
            dados_coletados["contato_step"] = "cpf"
            mensagens.append({"role": "user", "content": mensagem})
            mensagens.append({"role": "assistant", "content": resposta})
            session_data["mensagens"] = mensagens
            session_data["estado"] = ChatEstado.COLETANDO_CONTATO
            session_data["dados_coletados"] = dados_coletados
            await self._salvar_sessao(session_token, session_data)
            return {"resposta": resposta, "estado": ChatEstado.COLETANDO_CONTATO, "emergencia": False, "sessao_expirada": False}

        if not slot_id or not estabelecimento_id:
            resposta = "Não consegui localizar o horário selecionado. Por favor, inicie uma nova conversa."
            mensagens.append({"role": "user", "content": mensagem})
            mensagens.append({"role": "assistant", "content": resposta})
            session_data["mensagens"] = mensagens
            session_data["estado"] = ChatEstado.FINALIZADO
            await self._salvar_sessao(session_token, session_data)
            return {"resposta": resposta, "estado": ChatEstado.FINALIZADO, "emergencia": False, "sessao_expirada": False}

        try:
            from app.models.profissional import Profissional
            from app.models.slot import Slot

            # Buscar slot para obter profissional_id
            slot_result = await self.db.execute(
                select(Slot).where(Slot.id == slot_id, Slot.estabelecimento_id == estabelecimento_id)
            )
            slot_obj = slot_result.scalar_one_or_none()
            if not slot_obj:
                raise ValueError(f"Slot {slot_id} não encontrado")

            # Buscar profissional para obter especialidade_id
            profissional_result = await self.db.execute(
                select(Profissional).where(Profissional.id == slot_obj.profissional_id)
            )
            profissional_obj = profissional_result.scalar_one_or_none()
            if not profissional_obj:
                raise ValueError(f"Profissional do slot {slot_id} não encontrado")

            # Buscar ou criar cliente pelo CPF dentro da unidade
            result = await self.db.execute(
                select(Cliente).where(
                    Cliente.cpf == cpf,
                    Cliente.estabelecimento_id == estabelecimento_id,
                ).limit(1)
            )
            cliente = result.scalar_one_or_none()

            if not cliente:
                cliente = Cliente(
                    cpf=cpf,
                    nome=nome,
                    telefone=telefone,
                    email=email,
                    convenio_id=dados_coletados.get("convenio_id"),
                    convenio=dados_coletados.get("convenio"),
                    modalidade_pagamento=(
                        ModalidadePagamento.CONVENIO
                        if dados_coletados.get("tipo_atendimento") == "CONVENIO"
                        else ModalidadePagamento.PARTICULAR
                    ),
                    estabelecimento_id=estabelecimento_id,
                )
                self.db.add(cliente)
                await self.db.flush()
                await self.db.refresh(cliente)
            else:
                # Completar contato que faltava no cadastro
                if email and not cliente.email:
                    cliente.email = email
                if telefone and not cliente.telefone:
                    cliente.telefone = telefone

            # Carteirinha informada no chat: reaproveita a mesma ou cadastra
            cliente_convenio_id = None
            numero_carteirinha = dados_coletados.get("numero_carteirinha")
            if numero_carteirinha and dados_coletados.get("convenio_id"):
                from app.models.cliente_convenio import ClienteConvenio

                result = await self.db.execute(
                    select(ClienteConvenio).where(
                        ClienteConvenio.cliente_id == cliente.id,
                        ClienteConvenio.convenio_id == dados_coletados["convenio_id"],
                        ClienteConvenio.numero_carteirinha == numero_carteirinha,
                    ).limit(1)
                )
                carteirinha = result.scalar_one_or_none()
                if not carteirinha:
                    result = await self.db.execute(
                        select(ClienteConvenio.id).where(
                            ClienteConvenio.cliente_id == cliente.id,
                            ClienteConvenio.principal == True,  # noqa: E712
                        ).limit(1)
                    )
                    carteirinha = ClienteConvenio(
                        cliente_id=cliente.id,
                        convenio_id=dados_coletados["convenio_id"],
                        plano_id=dados_coletados.get("plano_id"),
                        numero_carteirinha=numero_carteirinha,
                        nome_titular=nome,
                        principal=result.scalar_one_or_none() is None,
                    )
                    self.db.add(carteirinha)
                    await self.db.flush()
                    await self.db.refresh(carteirinha)
                cliente_convenio_id = carteirinha.id

            # Criar atendimento
            agenda = AgendaService(self.db)
            dados_atendimento = AtendimentoCreate(
                slot_id=slot_id,
                cliente_id=cliente.id,
                profissional_id=slot_obj.profissional_id,
                especialidade_id=profissional_obj.especialidade_id,
                cliente_convenio_id=cliente_convenio_id,
                observacoes=(
                    f"Agendado via chatbot. Especialidade: {dados_coletados.get('especialidade', '')}. "
                    f"Atendimento: {descrever_pagamento(dados_coletados)}"
                    + ("." if cliente_convenio_id else " (carteirinha a conferir na recepção).")
                ),
            )
            atendimento = await agenda.agendar_consulta(dados_atendimento, estabelecimento_id)
            await self.db.commit()

            # Buscar info do slot
            slot_desc = "seu horário"
            for s in session_data.get("slots_temp", []):
                if s["id"] == slot_id:
                    slot_desc = f"{s['data']} às {s['hora_inicio']}"
                    break

            protocolo = f"PROTO-{atendimento.id:06d}"
            resposta = (
                f"✅ **Agendamento confirmado!**\n\n"
                f"📋 **Protocolo:** {protocolo}\n"
                f"Sua consulta foi marcada para **{slot_desc}**.\n"
                f"Você receberá um lembrete no telefone **{telefone}**.\n\n"
                "Se precisar cancelar ou reagendar, informe o protocolo à recepção. "
                "Cuide-se bem!"
            )

            log.info(
                "agendamento_criado_via_chat",
                atendimento_id=atendimento.id,
                cliente_id=cliente.id,
                slot_id=slot_id,
                token=session_token[:8] + "...",
            )

        except Exception as e:
            log.error("erro_criar_agendamento_chat", erro=str(e), token=session_token[:8] + "...")
            await self.db.rollback()
            resposta = (
                "Não foi possível confirmar o agendamento automaticamente. "
                "Por favor, entre em contato com a recepção para finalizar. "
                f"Informe o horário selecionado e seus dados: {nome} / {telefone}."
            )

        mensagens.append({"role": "user", "content": mensagem})
        mensagens.append({"role": "assistant", "content": resposta})
        session_data["mensagens"] = mensagens
        session_data["estado"] = ChatEstado.FINALIZADO
        session_data["dados_coletados"] = dados_coletados
        await self._salvar_sessao(session_token, session_data)

        return {
            "resposta": resposta,
            "estado": ChatEstado.FINALIZADO,
            "confirmacao": {"mensagem": resposta},
            "emergencia": False,
            "sessao_expirada": False,
        }

    async def encerrar_sessao(
        self, session_token: str, status: str = "ENCERRADA"
    ) -> None:
        """Encerra sessao de chat."""
        await self.redis.delete(f"chat:session:{session_token}")
        log.info(
            "sessao_chat_encerrada",
            token=session_token[:8] + "...",
            status=status,
        )
