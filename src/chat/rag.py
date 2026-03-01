import hashlib
import logging
import re
import uuid
from collections import Counter

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    Fusion,
    FusionQuery,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from src.ai.document_parser import parse_document
from src.config import settings
from src.providers import embed_text
from src.providers.factory import get_embedding_provider

from .models import ChatDocument

logger = logging.getLogger(__name__)

_qdrant: AsyncQdrantClient | None = None

# ---------------------------------------------------------------------------
# BM25 sparse vectorizer (lightweight, no heavy deps)
# ---------------------------------------------------------------------------

# Simple tokenizer: lowercase, split on non-alphanumeric, drop short tokens
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")

# English stop words (small set to keep it lightweight)
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "is", "it", "be", "as", "by", "was", "are", "that", "this",
    "with", "from", "not", "have", "has", "had", "will", "can", "do",
    "does", "did", "been", "being", "would", "could", "should", "may",
    "might", "shall", "its", "his", "her", "my", "our", "we", "he",
    "she", "they", "them", "their", "you", "your", "me", "us", "who",
    "which", "what", "where", "when", "how", "all", "each", "any",
    "no", "so", "if", "then", "than", "too", "very", "just", "about",
})

# BM25 parameters
_BM25_K1 = 1.2
_BM25_B = 0.75
_AVG_DOC_LEN = 200.0  # approximate average chunk length in tokens


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase terms, removing stop words."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP_WORDS]


def _build_vocab(tokens: list[str]) -> dict[str, int]:
    """Map each unique token to a stable integer index (hash-based)."""
    vocab: dict[str, int] = {}
    for token in set(tokens):
        # Use a large hash space to minimize collisions
        idx = hash(token) % (2**31)
        vocab[token] = abs(idx)
    return vocab


def sparse_vectorize(text: str) -> SparseVector:
    """Generate a BM25-style sparse vector for the given text.

    Uses term frequency with BM25 saturation weighting.  Since we don't have
    corpus-level IDF statistics, we apply a uniform IDF=1 and rely on BM25's TF
    saturation to cap the influence of repeated terms.  The actual ranking boost
    from sparse vectors comes from exact keyword matching via RRF fusion.
    """
    tokens = _tokenize(text)
    if not tokens:
        return SparseVector(indices=[0], values=[0.0])

    tf = Counter(tokens)
    vocab = _build_vocab(tokens)
    doc_len = len(tokens)

    indices: list[int] = []
    values: list[float] = []

    for token, count in tf.items():
        idx = vocab[token]
        # BM25 TF saturation: tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl/avgdl))
        numerator = count * (_BM25_K1 + 1)
        denominator = count + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_len / _AVG_DOC_LEN)
        score = numerator / denominator
        indices.append(idx)
        values.append(score)

    return SparseVector(indices=indices, values=values)


# ---------------------------------------------------------------------------
# Qdrant client
# ---------------------------------------------------------------------------


def _get_client() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    return _qdrant


def _use_hybrid() -> bool:
    """Check whether hybrid search is enabled."""
    return settings.qdrant_hybrid_search


async def ensure_collection() -> None:
    """Create the Qdrant collection if it does not already exist."""
    client = _get_client()
    dim = get_embedding_provider().dimension
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    hybrid = _use_hybrid()

    if settings.qdrant_collection not in names:
        if hybrid:
            await client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config={"dense": VectorParams(size=dim, distance=Distance.COSINE)},
                sparse_vectors_config={"sparse": SparseVectorParams()},
            )
            logger.info(
                "Created Qdrant collection: %s (hybrid, dense_dim=%d)",
                settings.qdrant_collection, dim,
            )
        else:
            await client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            logger.info(
                "Created Qdrant collection: %s (dense-only, dim=%d)",
                settings.qdrant_collection, dim,
            )
    else:
        info = await client.get_collection(settings.qdrant_collection)
        vectors_config = info.config.params.vectors

        # Detect old-format (unnamed) collection when hybrid is enabled
        if hybrid and isinstance(vectors_config, VectorParams):
            logger.warning(
                "Qdrant collection '%s' uses legacy unnamed vectors. "
                "Hybrid search requires named vectors ('dense' + 'sparse'). "
                "Delete the collection and re-ingest to enable hybrid search. "
                "Falling back to dense-only mode.",
                settings.qdrant_collection,
            )
        elif hybrid and isinstance(vectors_config, dict):
            # Named vectors — check dense dimension
            dense_cfg = vectors_config.get("dense")
            if dense_cfg and dense_cfg.size != dim:
                logger.warning(
                    "Qdrant collection '%s' dense vector has dimension %d "
                    "but current embedding provider uses %d. "
                    "Delete the collection and re-ingest to change dimensions.",
                    settings.qdrant_collection, dense_cfg.size, dim,
                )
        elif not hybrid and isinstance(vectors_config, VectorParams):
            # Dense-only mode with unnamed vectors — check dimension
            if vectors_config.size != dim:
                logger.warning(
                    "Qdrant collection '%s' has dimension %d but current "
                    "embedding provider uses %d. "
                    "Delete the collection and re-ingest to change dimensions.",
                    settings.qdrant_collection, vectors_config.size, dim,
                )


def _collection_is_hybrid(info) -> bool:
    """Check if an existing collection has named vectors (hybrid format)."""
    vectors_config = info.config.params.vectors
    return isinstance(vectors_config, dict) and "dense" in vectors_config


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


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

    # Determine if the actual collection supports hybrid
    info = await client.get_collection(settings.qdrant_collection)
    use_hybrid = _use_hybrid() and _collection_is_hybrid(info)

    points = []
    for idx, chunk in enumerate(chunks):
        dense_vector = await embed_text(chunk)
        point_id = _deterministic_uuid(doc_id, idx)
        payload = {
            "text": chunk,
            "filename": filename,
            "doc_id": doc_id,
            "chunk_idx": idx,
            "session_id": session_id,
        }

        if use_hybrid:
            sparse_vector = sparse_vectorize(chunk)
            points.append(
                PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vector,
                        "sparse": sparse_vector,
                    },
                    payload=payload,
                )
            )
        else:
            points.append(
                PointStruct(
                    id=point_id,
                    vector=dense_vector,
                    payload=payload,
                )
            )

    if points:
        await client.upsert(
            collection_name=settings.qdrant_collection, points=points
        )
        logger.info(
            "Ingested %d chunks for '%s' (hybrid=%s)",
            len(points), filename, use_hybrid,
        )

    return ChatDocument(
        id=doc_id,
        session_id=session_id,
        filename=filename,
        content_hash=content_hash,
        chunk_count=len(chunks),
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


async def search_relevant(query: str, top_k: int | None = None) -> list[dict]:
    """Search Qdrant for relevant chunks using hybrid or dense-only search."""
    if top_k is None:
        top_k = settings.chat_context_chunks

    await ensure_collection()
    client = _get_client()

    # Check actual collection format
    info = await client.get_collection(settings.qdrant_collection)
    use_hybrid = _use_hybrid() and _collection_is_hybrid(info)

    if use_hybrid:
        return await _search_hybrid(client, query, top_k)
    else:
        return await _search_dense(client, query, top_k)


async def _search_dense(
    client: AsyncQdrantClient, query: str, top_k: int
) -> list[dict]:
    """Dense-only search (backward compatible with legacy collections)."""
    query_vector = await embed_text(query)

    # Support both named and unnamed vector collections
    info = await client.get_collection(settings.qdrant_collection)
    if isinstance(info.config.params.vectors, dict) and "dense" in info.config.params.vectors:
        # Named vector collection but hybrid disabled — search dense only
        response = await client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            using="dense",
            limit=top_k,
        )
    else:
        # Legacy unnamed vector collection
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


async def _search_hybrid(
    client: AsyncQdrantClient, query: str, top_k: int
) -> list[dict]:
    """Hybrid search: dense + sparse vectors fused with RRF."""
    dense_vector = await embed_text(query)
    sparse_vector = sparse_vectorize(query)

    # Prefetch more candidates from each source, then fuse and limit
    prefetch_limit = top_k * 3

    response = await client.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            Prefetch(
                query=dense_vector,
                using="dense",
                limit=prefetch_limit,
            ),
            Prefetch(
                query=sparse_vector,
                using="sparse",
                limit=prefetch_limit,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
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
