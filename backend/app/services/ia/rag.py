"""Servico RAG — Retrieval-Augmented Generation.

Gerencia collection Qdrant, ingestao de documentos e retrieval.
"""

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings

log = structlog.get_logger(__name__)

COLLECTION_NAME = "protocolos_clinicos"
VECTOR_SIZE = 768  # nomic-embed-text (Ollama local)
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def get_qdrant_client() -> QdrantClient:
    """Cria e retorna QdrantClient configurado."""
    return QdrantClient(url=settings.qdrant_url)


def criar_collection_se_nao_existe(client: QdrantClient) -> None:
    """Cria collection de protocolos se nao existe."""
    if client.collection_exists(COLLECTION_NAME):
        log.info("qdrant_collection_existe", collection=COLLECTION_NAME)
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )
    log.info("qdrant_collection_criada", collection=COLLECTION_NAME)


def health_check_qdrant(client: QdrantClient) -> dict:
    """Verifica saude do Qdrant e da collection."""
    try:
        exists = client.collection_exists(COLLECTION_NAME)
        return {
            "status": "ok",
            "collection": COLLECTION_NAME,
            "exists": exists,
        }
    except Exception as e:
        log.error("qdrant_health_check_falhou", erro=str(e))
        return {
            "status": "erro",
            "erro": str(e),
        }


def chunk_texto(texto: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Divide texto em chunks com overlap.

    Args:
        texto: Texto completo do documento.
        chunk_size: Tamanho maximo de cada chunk em caracteres.
        overlap: Sobreposicao entre chunks consecutivos.

    Returns:
        Lista de chunks de texto.
    """
    if not texto or not texto.strip():
        return []

    chunks = []
    inicio = 0
    while inicio < len(texto):
        fim = inicio + chunk_size
        chunk = texto[inicio:fim].strip()
        if chunk:
            chunks.append(chunk)
        inicio += chunk_size - overlap

    return chunks


async def indexar_documento(
    client: QdrantClient,
    embeddings_fn,
    documento_id: str,
    titulo: str,
    texto: str,
) -> int:
    """Faz chunking, embedding e indexacao de um documento no Qdrant.

    Args:
        client: QdrantClient configurado.
        embeddings_fn: Funcao async que recebe lista de textos e retorna embeddings.
        documento_id: ID unico do documento.
        titulo: Titulo do documento.
        texto: Texto completo do documento.

    Returns:
        Numero de chunks indexados.
    """
    chunks = chunk_texto(texto)
    if not chunks:
        return 0

    # Gerar embeddings
    vectors = await embeddings_fn(chunks)

    # Criar pontos para o Qdrant
    points = []
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        point_id = hash(f"{documento_id}:{i}") & 0x7FFFFFFFFFFFFFFF  # positive int64
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "documento_id": documento_id,
                    "titulo": titulo,
                    "chunk_index": i,
                    "texto": chunk,
                },
            )
        )

    client.upsert(collection_name=COLLECTION_NAME, points=points)

    log.info(
        "documento_indexado",
        documento_id=documento_id,
        titulo=titulo,
        chunks=len(chunks),
    )
    return len(chunks)


async def buscar_contexto(
    client: QdrantClient,
    embeddings_fn,
    query: str,
    top_k: int = 3,
    score_threshold: float = 0.7,
) -> list[dict]:
    """Busca chunks relevantes no Qdrant para uma query.

    Args:
        client: QdrantClient configurado.
        embeddings_fn: Funcao async que recebe lista de textos e retorna embeddings.
        query: Texto da busca.
        top_k: Numero maximo de resultados.
        score_threshold: Score minimo para considerar relevante.

    Returns:
        Lista de dicts com texto e metadata dos chunks relevantes.
    """
    query_vector = (await embeddings_fn([query]))[0]

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
    )

    contextos = []
    for point in results.points:
        contextos.append({
            "texto": point.payload.get("texto", ""),
            "titulo": point.payload.get("titulo", ""),
            "documento_id": point.payload.get("documento_id", ""),
            "score": point.score,
        })

    log.info(
        "rag_busca",
        query_len=len(query),
        resultados=len(contextos),
    )
    return contextos
