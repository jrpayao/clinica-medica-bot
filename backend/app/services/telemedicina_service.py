"""Telemedicina (G29): horários online, sala de vídeo, consentimento, sala de espera, registro e documentos.

Estado da teleconsulta = status do atendimento. O profissional conduz pelo mesmo fluxo do presencial
(PRESENTE → EM_ATENDIMENTO → REALIZADA); o paciente só recebe o endereço da sala depois de aceitar o
termo e de o profissional iniciar o atendimento.
"""

import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import structlog
from jose import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.tempo import agora_local, fuso_valido
from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.atendimento_historico import AtendimentoStatusHistorico
from app.models.cliente import Cliente
from app.models.especialidade import Especialidade
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.profissional import Profissional
from app.models.slot import Slot, SlotStatus
from app.models.teleconsulta import (
    DocumentoClinico,
    Modalidade,
    RegistroClinico,
    Teleconsulta,
    TipoDocumento,
)
from app.services import papel_timbrado_service
from app.services.documentos_pdf import gerar_pdf
from app.services.ia.resumo_triagem import texto_do_resumo
from app.services.mensageria import enviar_whatsapp
from app.services.notificacao_service import enviar_email
from app.services.recepcao_service import proximas_acoes

log = structlog.get_logger(__name__)

TERMO_VERSAO = "2026-11"
TERMO_TEXTO = (
    "Este atendimento será feito a distância, por vídeo, em tempo real.\n\n"
    "Ao continuar, você declara que:\n"
    "1. Concorda em ser atendido(a) por teleconsulta e sabe que pode pedir atendimento presencial a qualquer momento.\n"
    "2. Entende que a teleconsulta tem limites, pois não há exame físico, e que o profissional pode indicar "
    "atendimento presencial se julgar necessário.\n"
    "3. Está em local reservado e é a própria pessoa agendada, ou o responsável legal por ela.\n"
    "4. Autoriza o registro das informações deste atendimento no seu prontuário, tratadas conforme a "
    "Lei Geral de Proteção de Dados. A chamada de vídeo não é gravada.\n"
    "5. Em caso de emergência, deve ligar para o SAMU (192) ou procurar um pronto-socorro."
)

ENTRADA_ANTECIPADA_MIN = 30     # a sala de espera abre este tempo antes do horário
PRESENCA_VALIDA_S = 40          # o paciente "está na sala" se a página dele deu sinal neste intervalo
MAX_ITENS_RECEITA = 10
MAX_DIAS_ATESTADO = 90

_ENCERRADOS = {AtendimentoStatus.REALIZADA}
_CANCELADOS = {AtendimentoStatus.CANCELADA, AtendimentoStatus.FALTA}
_A_CHEGAR = {AtendimentoStatus.AGENDADA, AtendimentoStatus.CONFIRMADA}
_COM_DOCUMENTO = {AtendimentoStatus.EM_ATENDIMENTO, AtendimentoStatus.REALIZADA}


class TeleconsultaNaoEncontradaError(Exception):
    pass


class AtendimentoNaoEncontradoError(Exception):
    pass


class ConsentimentoPendenteError(Exception):
    pass


class OperacaoNaoPermitidaError(Exception):
    pass


class ConteudoInvalidoError(Exception):
    pass


# ── Sala e link ─────────────────────────────────────────────────────────────

def url_da_sala(sala: str, nome: str, moderador: bool = False) -> str:
    """Endereço da sala no servidor de vídeo, já com o nome de exibição.

    Com JITSI_APP_ID e JITSI_APP_SECRET (servidor próprio), a sala exige um JWT assinado aqui.
    """
    base = settings.jitsi_base_url.rstrip("/")
    url = f"{base}/{sala}"
    if settings.jitsi_app_id and settings.jitsi_app_secret:
        agora = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "aud": "jitsi",
                "iss": settings.jitsi_app_id,
                "sub": base.split("//")[-1],
                "room": sala,
                "nbf": int((agora - timedelta(minutes=1)).timestamp()),
                "exp": int((agora + timedelta(hours=3)).timestamp()),
                "context": {"user": {"name": nome, "moderator": "true" if moderador else "false"}},
            },
            settings.jitsi_app_secret,
            algorithm="HS256",
        )
        url += f"?jwt={token}"
    return (
        f"{url}#userInfo.displayName=%22{quote(nome)}%22"
        "&config.prejoinConfig.enabled=false&config.disableDeepLinking=true"
    )


def link_do_paciente(token: str) -> str:
    return f"{settings.portal_url.rstrip('/')}/teleconsulta/{token}"


async def criar_teleconsulta(db: AsyncSession, atendimento: Atendimento) -> Teleconsulta:
    """Cria a sala do atendimento online (ou devolve a que já existe)."""
    existente = (
        await db.execute(select(Teleconsulta).where(Teleconsulta.atendimento_id == atendimento.id))
    ).scalar_one_or_none()
    if existente is not None:
        return existente
    sala = Teleconsulta(
        atendimento_id=atendimento.id,
        sala=f"medbot-{secrets.token_hex(12)}",
        token_paciente=secrets.token_urlsafe(32),
    )
    db.add(sala)
    await db.flush()
    log.info("teleconsulta_criada", atendimento_id=atendimento.id)
    return sala


async def marcar_slots_online(
    db: AsyncSession,
    estabelecimento_id: int,
    data: date,
    aceita: bool,
    profissional_id: int | None = None,
    slot_ids: list[int] | None = None,
) -> int:
    """Marca (ou desmarca) como "aceita online" os horários livres do dia. Devolve quantos mudaram."""
    comando = (
        update(Slot)
        .where(
            Slot.estabelecimento_id == estabelecimento_id,
            Slot.data == data,
            Slot.status == SlotStatus.DISPONIVEL,
            Slot.aceita_online != aceita,
        )
        .values(aceita_online=aceita)
        .execution_options(synchronize_session="fetch")
    )
    if profissional_id is not None:
        comando = comando.where(Slot.profissional_id == profissional_id)
    if slot_ids is not None:
        comando = comando.where(Slot.id.in_(slot_ids))
    resultado = await db.execute(comando)
    return resultado.rowcount or 0


async def _contexto(db: AsyncSession, atendimento_id: int):
    """Atendimento com slot, cliente, profissional, unidade e especialidade."""
    return (
        await db.execute(
            select(Atendimento, Slot, Cliente, Profissional, EstabelecimentoSaude, Especialidade.nome)
            .join(Slot, Atendimento.slot_id == Slot.id)
            .join(Cliente, Atendimento.cliente_id == Cliente.id)
            .join(Profissional, Atendimento.profissional_id == Profissional.id)
            .join(EstabelecimentoSaude, Atendimento.estabelecimento_id == EstabelecimentoSaude.id)
            .join(Especialidade, Atendimento.especialidade_id == Especialidade.id)
            .where(Atendimento.id == atendimento_id)
        )
    ).first()


async def _email(destinatario: str, assunto: str, corpo: str) -> bool:
    return await enviar_email(destinatario=destinatario, assunto=assunto, corpo_html=corpo)


async def enviar_link(
    db: AsyncSession, atendimento: Atendimento, enviar_wa=enviar_whatsapp, enviar_mail=_email
) -> bool:
    """Envia ao paciente o link da teleconsulta por WhatsApp e e-mail."""
    sala = await criar_teleconsulta(db, atendimento)
    _, slot, cliente, profissional, unidade, _ = await _contexto(db, atendimento.id)
    primeiro_nome = cliente.nome.split()[0] if cliente.nome else ""
    quando = f"{slot.data.strftime('%d/%m/%Y')} às {slot.hora_inicio.strftime('%H:%M')}"
    link = link_do_paciente(sala.token_paciente)
    texto = (
        f"Olá, {primeiro_nome}! Sua teleconsulta com {profissional.nome} ({unidade.nome}) está marcada "
        f"para {quando}.\n\nNo horário, entre por este link: {link}\n\n"
        f"A sala de espera abre {ENTRADA_ANTECIPADA_MIN} minutos antes. Use um aparelho com câmera e microfone."
    )
    ok_wa = bool(cliente.telefone) and await enviar_wa(cliente.telefone, texto)
    ok_mail = bool(cliente.email) and await enviar_mail(
        cliente.email, "Link da sua teleconsulta", texto.replace("\n", "<br>")
    )
    if ok_wa or ok_mail:
        sala.link_enviado_em = datetime.now(timezone.utc)
        await db.flush()
    return bool(ok_wa or ok_mail)


# ── Paciente ────────────────────────────────────────────────────────────────

async def _por_token(db: AsyncSession, token: str) -> Teleconsulta:
    sala = (
        await db.execute(select(Teleconsulta).where(Teleconsulta.token_paciente == token))
    ).scalar_one_or_none()
    if sala is None:
        raise TeleconsultaNaoEncontradaError("Link de teleconsulta inválido")
    return sala


async def _documentos(db: AsyncSession, atendimento_id: int) -> list[DocumentoClinico]:
    return list(
        (
            await db.execute(
                select(DocumentoClinico)
                .where(DocumentoClinico.atendimento_id == atendimento_id)
                .order_by(DocumentoClinico.emitido_em, DocumentoClinico.id)
            )
        ).scalars().all()
    )


def _doc_resumido(doc: DocumentoClinico) -> dict:
    return {
        "id": doc.id,
        "tipo": doc.tipo.value,
        "emitido_em": doc.emitido_em.isoformat() if doc.emitido_em else None,
    }


async def situacao_do_paciente(db: AsyncSession, token: str, agora=agora_local) -> dict:
    """O que a página do paciente mostra: termo, sala de espera, sala de vídeo ou encerramento."""
    sala = await _por_token(db, token)
    atendimento, slot, cliente, profissional, unidade, especialidade = await _contexto(db, sala.atendimento_id)
    primeiro_nome = cliente.nome.split()[0] if cliente.nome else ""
    inicio = datetime.combine(slot.data, slot.hora_inicio)
    abre = inicio - timedelta(minutes=ENTRADA_ANTECIPADA_MIN)
    consentiu = sala.consentimento_em is not None

    if atendimento.status in _CANCELADOS:
        situacao = "CANCELADA"
    elif atendimento.status in _ENCERRADOS:
        situacao = "ENCERRADA"
    elif not consentiu:
        situacao = "AGUARDANDO_CONSENTIMENTO"
    elif atendimento.status == AtendimentoStatus.EM_ATENDIMENTO:
        situacao = "EM_ANDAMENTO"
    elif agora(fuso_valido(unidade.timezone)) < abre:
        situacao = "CEDO"
    else:
        situacao = "SALA_DE_ESPERA"

    return {
        "situacao": situacao,
        "paciente_nome": primeiro_nome,
        "profissional_nome": profissional.nome,
        "especialidade_nome": especialidade,
        "unidade_nome": unidade.nome,
        "unidade_telefone": unidade.telefone,
        "data": slot.data.strftime("%d/%m/%Y"),
        "hora": slot.hora_inicio.strftime("%H:%M"),
        "abre_as": abre.strftime("%H:%M"),
        "termo": {"versao": TERMO_VERSAO, "texto": TERMO_TEXTO} if not consentiu else None,
        "sala_url": url_da_sala(sala.sala, primeiro_nome) if situacao == "EM_ANDAMENTO" else None,
        "documentos": (
            [_doc_resumido(d) for d in await _documentos(db, atendimento.id)]
            if situacao in ("EM_ANDAMENTO", "ENCERRADA")
            else []
        ),
    }


async def registrar_consentimento(db: AsyncSession, token: str, ip: str | None) -> None:
    """Aceite do termo de teleconsulta. O primeiro aceite é o que fica registrado."""
    sala = await _por_token(db, token)
    if sala.consentimento_em is None:
        sala.consentimento_em = datetime.now(timezone.utc)
        sala.consentimento_ip = (ip or "")[:64] or None
        sala.termo_versao = TERMO_VERSAO
        await db.flush()
        log.info("teleconsulta_consentimento", atendimento_id=sala.atendimento_id, termo=TERMO_VERSAO)


async def registrar_presenca(db: AsyncSession, token: str, agora=agora_local) -> dict:
    """Sinal de que a página do paciente está aberta. Dentro da janela, faz o check-in do atendimento."""
    sala = await _por_token(db, token)
    if sala.consentimento_em is None:
        raise ConsentimentoPendenteError("Aceite o termo de teleconsulta antes de entrar")

    situacao = await situacao_do_paciente(db, token, agora=agora)
    if situacao["situacao"] in ("SALA_DE_ESPERA", "EM_ANDAMENTO"):
        momento = datetime.now(timezone.utc)
        sala.paciente_visto_em = momento
        sala.paciente_entrou_em = sala.paciente_entrou_em or momento
        atendimento = (
            await db.execute(select(Atendimento).where(Atendimento.id == sala.atendimento_id))
        ).scalar_one()
        if atendimento.status in _A_CHEGAR:
            db.add(
                AtendimentoStatusHistorico(
                    atendimento_id=atendimento.id,
                    status_anterior=atendimento.status,
                    status_novo=AtendimentoStatus.PRESENTE,
                    observacao="Paciente entrou na sala de espera online",
                )
            )
            atendimento.status = AtendimentoStatus.PRESENTE
        await db.flush()
    return situacao


async def pdf_do_documento_do_paciente(db: AsyncSession, token: str, documento_id: int) -> tuple[bytes, str]:
    sala = await _por_token(db, token)
    return await _pdf(db, documento_id, atendimento_id=sala.atendimento_id)


# ── Profissional ────────────────────────────────────────────────────────────

async def _do_profissional(
    db: AsyncSession, atendimento_id: int, profissional_id: int, estabelecimento_id: int
):
    contexto = await _contexto(db, atendimento_id)
    if (
        contexto is None
        or contexto[0].profissional_id != profissional_id
        or contexto[0].estabelecimento_id != estabelecimento_id
    ):
        raise AtendimentoNaoEncontradoError("Atendimento não encontrado")
    return contexto


async def sala_do_profissional(
    db: AsyncSession, atendimento_id: int, profissional_id: int, estabelecimento_id: int
) -> dict:
    """Tudo o que a tela de atendimento do profissional precisa: paciente, triagem, sala, registro e documentos."""
    atendimento, slot, cliente, profissional, _, especialidade = await _do_profissional(
        db, atendimento_id, profissional_id, estabelecimento_id
    )
    teleconsulta = None
    if atendimento.modalidade == Modalidade.ONLINE:
        sala = await criar_teleconsulta(db, atendimento)
        visto = sala.paciente_visto_em
        teleconsulta = {
            "sala_url": url_da_sala(sala.sala, profissional.nome, moderador=True),
            "link_paciente": link_do_paciente(sala.token_paciente),
            "consentimento": sala.consentimento_em is not None,
            "paciente_na_sala": bool(
                visto and (datetime.now(timezone.utc) - visto).total_seconds() <= PRESENCA_VALIDA_S
            ),
            "paciente_entrou_em": sala.paciente_entrou_em.isoformat() if sala.paciente_entrou_em else None,
            "link_enviado_em": sala.link_enviado_em.isoformat() if sala.link_enviado_em else None,
        }

    registro = (
        await db.execute(select(RegistroClinico).where(RegistroClinico.atendimento_id == atendimento.id))
    ).scalar_one_or_none()
    resumo = atendimento.triagem_resumo if isinstance(atendimento.triagem_resumo, dict) else {}
    texto = texto_do_resumo(resumo)

    return {
        "atendimento_id": atendimento.id,
        "status": atendimento.status.value,
        "acoes": proximas_acoes(atendimento.status, "MEDICO"),
        "modalidade": atendimento.modalidade.value,
        "data": str(slot.data),
        "hora_inicio": slot.hora_inicio.strftime("%H:%M"),
        "hora_fim": slot.hora_fim.strftime("%H:%M"),
        "especialidade_nome": especialidade,
        "cliente_id": cliente.id,
        "cliente_nome": cliente.nome,
        "cliente_telefone": cliente.telefone,
        "cliente_nascimento": str(cliente.data_nascimento) if cliente.data_nascimento else None,
        "observacoes": atendimento.observacoes,
        "triagem": (
            {
                "texto": texto,
                "origem": resumo.get("origem"),
                "categorias": resumo.get("categorias") or [],
                "historico": [h for h in (resumo.get("historico") or []) if isinstance(h, dict)],
            }
            if texto
            else None
        ),
        "teleconsulta": teleconsulta,
        "registro": {
            "queixa": registro.queixa if registro else None,
            "evolucao": registro.evolucao if registro else None,
            "conduta": registro.conduta if registro else None,
            "atualizado_em": registro.updated_at.isoformat() if registro and registro.updated_at else None,
        },
        "documentos": [
            {**_doc_resumido(d), "conteudo": d.conteudo, "codigo": d.codigo}
            for d in await _documentos(db, atendimento.id)
        ],
    }


def _limpo(texto: str | None) -> str | None:
    return (texto or "").strip() or None


async def salvar_registro(
    db: AsyncSession,
    atendimento_id: int,
    profissional_id: int,
    estabelecimento_id: int,
    queixa: str | None,
    evolucao: str | None,
    conduta: str | None,
) -> RegistroClinico:
    """Grava as anotações do profissional sobre o atendimento (cria ou atualiza)."""
    atendimento = (await _do_profissional(db, atendimento_id, profissional_id, estabelecimento_id))[0]
    if atendimento.status in _CANCELADOS:
        raise OperacaoNaoPermitidaError("Atendimento cancelado ou com falta não recebe registro")

    registro = (
        await db.execute(select(RegistroClinico).where(RegistroClinico.atendimento_id == atendimento_id))
    ).scalar_one_or_none()
    if registro is None:
        registro = RegistroClinico(
            atendimento_id=atendimento_id,
            profissional_id=profissional_id,
            estabelecimento_id=estabelecimento_id,
        )
        db.add(registro)
    registro.queixa, registro.evolucao, registro.conduta = _limpo(queixa), _limpo(evolucao), _limpo(conduta)
    registro.updated_at = datetime.now(timezone.utc)
    await db.flush()
    log.info("registro_clinico_salvo", atendimento_id=atendimento_id, profissional_id=profissional_id)
    return registro


def validar_conteudo(tipo: TipoDocumento, conteudo: dict) -> dict:
    """Confere e normaliza o conteúdo de uma receita ou de um atestado."""
    if not isinstance(conteudo, dict):
        raise ConteudoInvalidoError("Conteúdo inválido")

    if tipo == TipoDocumento.RECEITA:
        itens = conteudo.get("itens")
        if not isinstance(itens, list) or not (1 <= len(itens) <= MAX_ITENS_RECEITA):
            raise ConteudoInvalidoError(f"A receita precisa de 1 a {MAX_ITENS_RECEITA} itens")
        normalizados = []
        for item in itens:
            medicamento = _limpo(item.get("medicamento")) if isinstance(item, dict) else None
            posologia = _limpo(item.get("posologia")) if isinstance(item, dict) else None
            if not medicamento or not posologia:
                raise ConteudoInvalidoError("Cada item precisa do medicamento e de como usar")
            normalizados.append({"medicamento": medicamento[:200], "posologia": posologia[:500]})
        return {"itens": normalizados, "observacoes": (_limpo(conteudo.get("observacoes")) or "")[:500] or None}

    dias = conteudo.get("dias")
    if isinstance(dias, bool) or not isinstance(dias, int) or not (1 <= dias <= MAX_DIAS_ATESTADO):
        raise ConteudoInvalidoError(f"Informe de 1 a {MAX_DIAS_ATESTADO} dias de afastamento")
    return {
        "dias": dias,
        "a_partir_de": _limpo(conteudo.get("a_partir_de")),
        "motivo": (_limpo(conteudo.get("motivo")) or "")[:500] or None,
        "cid": (_limpo(conteudo.get("cid")) or "")[:10] or None,
    }


async def emitir_documento(
    db: AsyncSession,
    atendimento_id: int,
    profissional_id: int,
    estabelecimento_id: int,
    tipo: TipoDocumento,
    conteudo: dict,
) -> DocumentoClinico:
    """Emite receita ou atestado do atendimento em andamento ou já realizado."""
    atendimento = (await _do_profissional(db, atendimento_id, profissional_id, estabelecimento_id))[0]
    if atendimento.status not in _COM_DOCUMENTO:
        raise OperacaoNaoPermitidaError("Inicie o atendimento antes de emitir documentos")

    documento = DocumentoClinico(
        atendimento_id=atendimento_id,
        profissional_id=profissional_id,
        cliente_id=atendimento.cliente_id,
        estabelecimento_id=estabelecimento_id,
        tipo=tipo,
        conteudo=validar_conteudo(tipo, conteudo),
        codigo=secrets.token_hex(5).upper(),
    )
    db.add(documento)
    await db.flush()
    await db.refresh(documento)
    log.info("documento_clinico_emitido", atendimento_id=atendimento_id, tipo=tipo.value)
    return documento


async def pdf_do_documento(
    db: AsyncSession, documento_id: int, atendimento_id: int, profissional_id: int, estabelecimento_id: int
) -> tuple[bytes, str]:
    await _do_profissional(db, atendimento_id, profissional_id, estabelecimento_id)
    return await _pdf(db, documento_id, atendimento_id=atendimento_id)


async def _pdf(db: AsyncSession, documento_id: int, atendimento_id: int) -> tuple[bytes, str]:
    documento = (
        await db.execute(
            select(DocumentoClinico).where(
                DocumentoClinico.id == documento_id, DocumentoClinico.atendimento_id == atendimento_id
            )
        )
    ).scalar_one_or_none()
    if documento is None:
        raise AtendimentoNaoEncontradoError("Documento não encontrado")

    _, _, cliente, profissional, unidade, _ = await _contexto(db, atendimento_id)
    local = documento.emitido_em.astimezone(_fuso(unidade.timezone)) if documento.emitido_em else None
    emitido_em = (local or datetime.now()).strftime("%d/%m/%Y")
    endereco = ", ".join(p for p in (unidade.endereco, unidade.cidade) if p)
    if endereco and unidade.estado:
        endereco += f"/{unidade.estado}"
    pdf = gerar_pdf({
        "tipo": documento.tipo.value,
        "codigo": documento.codigo,
        "emitido_em": emitido_em,
        "unidade": {"nome": unidade.nome, "endereco": endereco or None, "telefone": unidade.telefone},
        "profissional": {"nome": profissional.nome, "registro": profissional.registro_profissional},
        "paciente": {"nome": cliente.nome},
        "conteudo": documento.conteudo,
        "timbre": await papel_timbrado_service.para_o_pdf(db, documento.estabelecimento_id),
    })
    return pdf, f"{documento.tipo.value.lower()}-{documento.codigo.lower()}.pdf"


def _fuso(nome: str | None):
    from zoneinfo import ZoneInfo

    return ZoneInfo(fuso_valido(nome))
