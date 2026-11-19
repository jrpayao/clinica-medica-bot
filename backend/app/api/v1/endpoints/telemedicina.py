"""Telemedicina (G29).

Paciente (público, pelo token do link):
  GET  /v1/teleconsulta/{token}                          — situação: termo, sala de espera, sala ou encerrada
  POST /v1/teleconsulta/{token}/consentimento            — aceite do termo
  POST /v1/teleconsulta/{token}/presenca                 — sinal da página aberta; faz o check-in
  GET  /v1/teleconsulta/{token}/documentos/{id}.pdf      — receita ou atestado emitido no atendimento

Profissional (MEDICO, só os próprios atendimentos):
  GET  /v1/profissional/atendimentos/{id}/sala           — paciente, triagem, sala, registro e documentos
  PUT  /v1/profissional/atendimentos/{id}/registro       — anotações do atendimento
  POST /v1/profissional/atendimentos/{id}/documentos     — emite receita ou atestado
  GET  /v1/profissional/atendimentos/{id}/documentos/{doc}.pdf
  POST /v1/profissional/atendimentos/{id}/enviar-link    — reenvia o link ao paciente

Agenda:
  PATCH /v1/agenda/slots/online                          — marca horários livres do dia como "aceita online"
"""

from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    get_current_user,
    profissional_do_token,
    require_estabelecimento,
    require_role,
)
from app.core.database import get_db
from app.models.teleconsulta import TipoDocumento
from app.services import telemedicina_service as tele

log = structlog.get_logger(__name__)

publico = APIRouter(prefix="/teleconsulta", tags=["Teleconsulta (paciente)"])
profissional = APIRouter(prefix="/profissional/atendimentos/{atendimento_id}", tags=["Teleconsulta (profissional)"])
agenda = APIRouter(prefix="/agenda", tags=["Agenda"])

ROLES_AGENDA_ONLINE = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "MEDICO")
_LINK_INVALIDO = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link de teleconsulta inválido")


def _pdf(conteudo: bytes, nome: str) -> Response:
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nome}"', "Cache-Control": "no-store"},
    )


# ── Paciente ────────────────────────────────────────────────────────────────

@publico.get("/{token}", summary="Situação da teleconsulta para o paciente")
async def situacao(token: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await tele.situacao_do_paciente(db, token)
    except tele.TeleconsultaNaoEncontradaError:
        raise _LINK_INVALIDO


@publico.post("/{token}/consentimento", summary="Aceitar o termo de teleconsulta")
async def consentir(token: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await tele.registrar_consentimento(db, token, ip=request.client.host if request.client else None)
        await db.commit()
        return await tele.registrar_presenca(db, token)
    except tele.TeleconsultaNaoEncontradaError:
        raise _LINK_INVALIDO


@publico.post("/{token}/presenca", summary="Sinal de presença do paciente na página")
async def presenca(token: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await tele.registrar_presenca(db, token)
    except tele.TeleconsultaNaoEncontradaError:
        raise _LINK_INVALIDO
    except tele.ConsentimentoPendenteError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@publico.get("/{token}/documentos/{documento_id}.pdf", summary="Baixar receita ou atestado")
async def documento_do_paciente(token: str, documento_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    try:
        return _pdf(*await tele.pdf_do_documento_do_paciente(db, token, documento_id))
    except tele.TeleconsultaNaoEncontradaError:
        raise _LINK_INVALIDO
    except tele.AtendimentoNaoEncontradoError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")


# ── Profissional ────────────────────────────────────────────────────────────

async def _profissional_id(usuario: Annotated[dict, Depends(require_role("MEDICO"))]) -> int:
    return profissional_do_token(usuario)  # type: ignore[return-value]  # MEDICO nunca devolve None


_Prof = Annotated[int, Depends(_profissional_id)]
_Unidade = Annotated[int, Depends(require_estabelecimento)]


def _erro(e: Exception) -> HTTPException:
    if isinstance(e, tele.AtendimentoNaoEncontradoError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, tele.ConteudoInvalidoError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


_ERROS = (tele.AtendimentoNaoEncontradoError, tele.OperacaoNaoPermitidaError, tele.ConteudoInvalidoError)


class RegistroRequest(BaseModel):
    queixa: str | None = Field(None, max_length=5000)
    evolucao: str | None = Field(None, max_length=20000)
    conduta: str | None = Field(None, max_length=5000)


class DocumentoRequest(BaseModel):
    tipo: TipoDocumento
    conteudo: dict


@profissional.get("/sala", summary="Tela de atendimento do profissional")
async def sala(atendimento_id: int, prof: _Prof, unidade: _Unidade, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        dados = await tele.sala_do_profissional(db, atendimento_id, prof, unidade)
    except _ERROS as e:
        raise _erro(e)
    await db.commit()  # a sala de um atendimento online antigo pode ter sido criada agora
    return dados


@profissional.put("/registro", summary="Salvar as anotações do atendimento")
async def registro(
    atendimento_id: int, dados: RegistroRequest, prof: _Prof, unidade: _Unidade, db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        salvo = await tele.salvar_registro(
            db, atendimento_id, prof, unidade, queixa=dados.queixa, evolucao=dados.evolucao, conduta=dados.conduta
        )
    except _ERROS as e:
        raise _erro(e)
    await db.commit()
    return {"atualizado_em": salvo.updated_at.isoformat()}


@profissional.post("/documentos", status_code=status.HTTP_201_CREATED, summary="Emitir receita ou atestado")
async def emitir(
    atendimento_id: int, dados: DocumentoRequest, prof: _Prof, unidade: _Unidade, db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        doc = await tele.emitir_documento(db, atendimento_id, prof, unidade, dados.tipo, dados.conteudo)
    except _ERROS as e:
        raise _erro(e)
    await db.commit()
    return {"id": doc.id, "tipo": doc.tipo.value, "codigo": doc.codigo, "conteudo": doc.conteudo}


@profissional.get("/documentos/{documento_id}.pdf", summary="PDF do documento emitido")
async def documento(
    atendimento_id: int, documento_id: int, prof: _Prof, unidade: _Unidade, db: AsyncSession = Depends(get_db)
) -> Response:
    try:
        return _pdf(*await tele.pdf_do_documento(db, documento_id, atendimento_id, prof, unidade))
    except _ERROS as e:
        raise _erro(e)


@profissional.post("/enviar-link", summary="Reenviar o link da teleconsulta ao paciente")
async def reenviar_link(
    atendimento_id: int, prof: _Prof, unidade: _Unidade, db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        atendimento = (await tele._do_profissional(db, atendimento_id, prof, unidade))[0]
    except _ERROS as e:
        raise _erro(e)
    enviado = await tele.enviar_link(db, atendimento)
    await db.commit()
    return {"enviado": enviado}


# ── Agenda: horários que aceitam atendimento online ─────────────────────────

class SlotsOnlineRequest(BaseModel):
    data: date
    aceita_online: bool
    profissional_id: int | None = None
    slot_ids: list[int] | None = Field(None, max_length=200)


@agenda.patch("/slots/online", summary="Marcar horários livres do dia como atendimento online")
async def slots_online(
    dados: SlotsOnlineRequest,
    unidade: _Unidade,
    usuario: Annotated[dict, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    if usuario.get("role") not in ROLES_AGENDA_ONLINE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito")
    proprio = profissional_do_token(usuario)  # MEDICO só altera a própria agenda
    profissional_id = proprio if proprio is not None else dados.profissional_id
    if profissional_id is None and dados.slot_ids is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe o profissional ou os horários",
        )
    alterados = await tele.marcar_slots_online(
        db, unidade, dados.data, dados.aceita_online, profissional_id=profissional_id, slot_ids=dados.slot_ids
    )
    await db.commit()
    return {"alterados": alterados}
