import hashlib
import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.ai.document_parser import parse_document
from src.config import settings
from src.providers import embed_text
from src.providers.factory import get_embedding_provider

from .models import ChatDocument

logger = logging.getLogger(__name__)

_qdrant: AsyncQdrantClient | None = None


def _get_client() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    return _qdrant


async def ensure_collection() -> None:
    """Create the Qdrant collection if it does not already exist."""
    client = _get_client()
    dim = get_embedding_provider().dimension
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if settings.qdrant_collection not in names:
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection: %s (dim=%d)", settings.qdrant_collection, dim)
    else:
        # Check dimension mismatch
        info = await client.get_collection(settings.qdrant_collection)
        existing_dim = info.config.params.vectors.size
        if existing_dim != dim:
            logger.warning(
                "Qdrant collection '%s' has dimension %d but current embedding provider uses %d. "
                "Delete the collection and re-ingest to change dimensions.",
                settings.qdrant_collection,
                existing_dim,
                dim,
            )


def chunk_text(text: str, size: int = 2000, overlap: int = 256) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _deterministic_uuid(doc_id: str, chunk_idx: int) -> str:
    """Generate a deterministic UUID from doc_id + chunk_idx."""
    raw = f"{doc_id}:{chunk_idx}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


async def ingest_document(
    filename: str, file_bytes: bytes, session_id: str | None = None
) -> ChatDocument:
    """Parse, chunk, embed, and store a document in Qdrant."""
    text = parse_document(filename, file_bytes)
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    doc_id = str(uuid.uuid4())

    chunks = chunk_text(text)

    await ensure_collection()
    client = _get_client()

    points = []
    for idx, chunk in enumerate(chunks):
        vector = await embed_text(chunk)
        point_id = _deterministic_uuid(doc_id, idx)
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "text": chunk,
                    "filename": filename,
                    "doc_id": doc_id,
                    "chunk_idx": idx,
                    "session_id": session_id,
                },
            )
        )

    if points:
        await client.upsert(
            collection_name=settings.qdrant_collection, points=points
        )
        logger.info("Ingested %d chunks for '%s'", len(points), filename)

    return ChatDocument(
        id=doc_id,
        session_id=session_id,
        filename=filename,
        content_hash=content_hash,
        chunk_count=len(chunks),
    )


async def search_relevant(query: str, top_k: int | None = None) -> list[dict]:
    """Embed the query and search Qdrant for relevant chunks."""
    if top_k is None:
        top_k = settings.chat_context_chunks

    await ensure_collection()
    client = _get_client()

    query_vector = await embed_text(query)
    response = await client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=top_k,
    )

    return [
        {
            "text": hit.payload["text"],
            "filename": hit.payload["filename"],
            "score": hit.score,
        }
        for hit in response.points
    ]
