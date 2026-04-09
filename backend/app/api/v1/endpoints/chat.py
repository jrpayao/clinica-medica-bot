"""Endpoints de chat: WebSocket + REST + Webhook WhatsApp.

WS   /v1/chat/ws/{token}         — comunicacao em tempo real
POST /v1/chat/sessao             — criar nova sessao (auth opcional; estabelecimento_id via JWT ou body)
POST /v1/chat/encerrar           — encerrar sessao
POST /v1/chat/webhook/whatsapp   — webhook Evolution API (WhatsApp)
"""

import structlog
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_estabelecimento_id_chat
from app.core.database import AsyncSessionLocal, get_db
from app.core.redis import get_redis_client  # noqa: E402
from app.services.ia.chat_service import ChatService
from app.services.whatsapp_service import enviar_mensagem_whatsapp, extrair_mensagem_evolution

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# Router separado para WebSocket (sem HTTPBearer dependency — incompatível com WS)
ws_router = APIRouter(tags=["Chat"])


class CriarSessaoRequest(BaseModel):
    canal: str = "PORTAL"
    estabelecimento_id: int | None = None


class CriarSessaoResponse(BaseModel):
    session_token: str


class EncerrarSessaoRequest(BaseModel):
    session_token: str
    status: str = "ENCERRADA"


@router.post(
    "/sessao",
    response_model=CriarSessaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar sessao de chat",
)
async def criar_sessao(
    dados: CriarSessaoRequest,
    db: AsyncSession = Depends(get_db),
    est_id_token: Annotated[int | None, Depends(get_estabelecimento_id_chat)] = None,
) -> CriarSessaoResponse:
    # Prioridade: JWT token > body > None
    estabelecimento_id = est_id_token or dados.estabelecimento_id
    if not estabelecimento_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="estabelecimento_id é obrigatório (informe no body ou autentique-se)",
        )
    redis = get_redis_client()
    service = ChatService(db, redis)
    token = await service.criar_sessao(canal=dados.canal, estabelecimento_id=estabelecimento_id)
    return CriarSessaoResponse(session_token=token)


@router.post(
    "/encerrar",
    status_code=status.HTTP_200_OK,
    summary="Encerrar sessao de chat",
)
async def encerrar_sessao(
    dados: EncerrarSessaoRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    redis = get_redis_client()
    service = ChatService(db, redis)
    await service.encerrar_sessao(dados.session_token, status=dados.status)
    return {"mensagem": "Sessao encerrada com sucesso"}


@ws_router.websocket("/chat/ws/{session_token}")
async def websocket_chat(
    websocket: WebSocket,
    session_token: str,
) -> None:
    """WebSocket para chat em tempo real.

    Fluxo:
    1. Cliente conecta com session_token
    2. Cliente envia JSON: {"mensagem": "texto"}
    3. Servidor responde JSON: {"resposta": "...", "sessao_expirada": false, ...}
    4. Se sessao expirada, servidor avisa e fecha
    """
    await websocket.accept()

    redis = get_redis_client()

    try:
        async with AsyncSessionLocal() as db:
            while True:
                data = await websocket.receive_json()
                mensagem = data.get("mensagem", "")
                confirmar_slot_id = data.get("confirmar_slot_id")

                if not mensagem and confirmar_slot_id is None:
                    await websocket.send_json({"erro": "Mensagem vazia"})
                    continue

                service = ChatService(db=db, redis=redis)

                msg_efetiva = mensagem if mensagem else f"confirmar:{confirmar_slot_id}"
                resultado = await service.processar_mensagem(
                    session_token=session_token,
                    mensagem=msg_efetiva,
                )

                await websocket.send_json(resultado)

                if resultado.get("sessao_expirada"):
                    await websocket.close(code=1000, reason="Sessao expirada")
                    break

    except WebSocketDisconnect:
        log.info(
            "websocket_desconectado",
            token=session_token[:8] + "...",
        )
    except Exception as e:
        log.error(
            "websocket_erro",
            token=session_token[:8] + "...",
            erro=str(e),
        )
        await websocket.close(code=1011, reason="Erro interno")


@router.post(
    "/webhook/whatsapp",
    status_code=status.HTTP_200_OK,
    summary="Webhook Evolution API (WhatsApp)",
)
async def webhook_whatsapp(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Recebe mensagens do WhatsApp via Evolution API.

    Fluxo:
    1. Parsear payload Evolution API
    2. Buscar ou criar sessao de chat pelo telefone
    3. Processar mensagem pelo ChatService
    4. Enviar resposta via Evolution API
    """
    payload = await request.json()

    msg_data = extrair_mensagem_evolution(payload)
    if not msg_data:
        return {"status": "ignorado"}

    telefone = msg_data["telefone"]
    mensagem = msg_data["mensagem"]

    redis = get_redis_client()
    service = ChatService(db, redis)

    # Buscar sessao existente pelo telefone ou criar nova
    session_key = f"chat:whatsapp:{telefone}"
    session_token = await redis.get(session_key)

    if not session_token:
        session_token = await service.criar_sessao(canal="WHATSAPP")
        await redis.set(session_key, session_token, ex=1800)

    resultado = await service.processar_mensagem(
        session_token=session_token,
        mensagem=mensagem,
    )

    # Enviar resposta via WhatsApp
    if resultado.get("resposta"):
        await enviar_mensagem_whatsapp(
            telefone=telefone,
            mensagem=resultado["resposta"],
        )

    log.info(
        "whatsapp_webhook_processado",
        telefone=telefone[:5] + "***",
    )
    return {"status": "processado"}
