"""Endpoints RAG — ingestao de documentos e health check.

POST /v1/rag/documentos — ingerir documento (texto ou PDF)
GET /v1/rag/health — health check do Qdrant
"""

import structlog
from fastapi import APIRouter, Depends, Form, status

from app.api.v1.dependencies import require_role
from app.services.ia.rag import (
    criar_collection_se_nao_existe,
    get_qdrant_client,
    health_check_qdrant,
    indexar_documento,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


async def _gerar_embeddings(textos: list[str]) -> list[list[float]]:
    """Gera embeddings via nomic-embed-text (Ollama local)."""
    from langchain_ollama import OllamaEmbeddings

    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434",
    )
    return await embeddings.aembed_documents(textos)


@router.post(
    "/documentos",
    status_code=status.HTTP_201_CREATED,
    summary="Ingerir documento para RAG",
    dependencies=[Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO"))],
)
async def ingerir_documento(
    titulo: str = Form(...),
    documento_id: str = Form(...),
    texto: str = Form(...),
) -> dict:
    """Ingere documento de texto para indexacao no Qdrant.

    Requer role ADMIN.
    """
    client = get_qdrant_client()
    criar_collection_se_nao_existe(client)

    num_chunks = await indexar_documento(
        client=client,
        embeddings_fn=_gerar_embeddings,
        documento_id=documento_id,
        titulo=titulo,
        texto=texto,
    )

    return {
        "documento_id": documento_id,
        "titulo": titulo,
        "chunks_indexados": num_chunks,
    }


@router.get(
    "/health",
    summary="Health check do Qdrant",
)
async def rag_health() -> dict:
    """Verifica saude do Qdrant e da collection."""
    client = get_qdrant_client()
    return health_check_qdrant(client)
