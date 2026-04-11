"""Embedding generation service.

Uses OpenAI text-embedding-3-small (1536 dims) by default.

NOTE: Anthropic does not currently expose a public text-embedding API.
      When tenant.ai_provider == 'anthropic' we fall back to the platform
      OpenAI key for embeddings — a tenant-supplied OpenAI key is used if
      available. TODO: revisit if Anthropic releases an embedding endpoint.

Two variants are provided:
- generate_embedding()       — synchronous, safe to call from Celery workers
- generate_embedding_async() — async, for use in FastAPI request handlers
"""

import logging
from typing import TYPE_CHECKING

import numpy as np
from openai import AsyncOpenAI, OpenAI

from app.config import settings
from app.services.crypto import decrypt

if TYPE_CHECKING:
    from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMS = 1536
_CHUNK_SIZE = 6000
_CHUNK_OVERLAP = 500


def generate_embedding(text: str, tenant: "Tenant | None" = None) -> list[float]:
    """Generate a 1536-dimensional embedding vector for *text* (synchronous).

    Uses the synchronous OpenAI client — safe to call from Celery workers
    where asyncio.run() has already completed and the event loop is closed.

    Long texts are split into overlapping chunks; chunk embeddings are averaged
    and L2-normalised to produce a single representative vector.
    """
    api_key = _resolve_openai_key(tenant)
    if not api_key:
        raise ValueError(
            "No OpenAI API key available for embeddings: set OPENAI_API_KEY "
            "in environment or configure tenant.ai_api_key (OpenAI)."
        )

    chunks = _chunk_text(text)
    if not chunks:
        return []

    client = OpenAI(api_key=api_key)
    embeddings: list[list[float]] = []
    for chunk in chunks:
        response = client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=chunk,
            dimensions=_EMBEDDING_DIMS,
        )
        embeddings.append(response.data[0].embedding)

    return _average_embeddings(embeddings)


async def generate_embedding_async(text: str, tenant: "Tenant | None" = None) -> list[float]:
    """Generate a 1536-dimensional embedding vector for *text* (async).

    Uses the async OpenAI client — for use in FastAPI request handlers and
    other async contexts where the event loop remains open.
    """
    api_key = _resolve_openai_key(tenant)
    if not api_key:
        raise ValueError(
            "No OpenAI API key available for embeddings: set OPENAI_API_KEY "
            "in environment or configure tenant.ai_api_key (OpenAI)."
        )

    chunks = _chunk_text(text)
    if not chunks:
        return []

    client = AsyncOpenAI(api_key=api_key)
    embeddings: list[list[float]] = []
    for chunk in chunks:
        response = await client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=chunk,
            dimensions=_EMBEDDING_DIMS,
        )
        embeddings.append(response.data[0].embedding)

    return _average_embeddings(embeddings)


def _average_embeddings(embeddings: list[list[float]]) -> list[float]:
    """Average a list of embedding vectors and L2-normalise the result."""
    if len(embeddings) == 1:
        return embeddings[0]
    avg = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    return avg.tolist()


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks of ~_CHUNK_SIZE chars."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
        if start >= len(text):
            break
    return chunks


# ── Internal helpers ───────────────────────────────────────────────────────────

def _resolve_openai_key(tenant: "Tenant | None") -> str | None:
    """Return the best-available OpenAI API key.

    Priority:
    1. Tenant's own key (decrypted), but only if provider is 'openai'.
    2. Platform OPENAI_API_KEY env var.
    """
    if tenant is not None and tenant.ai_provider == "openai" and tenant.ai_api_key:
        return decrypt(tenant.ai_api_key)
    return settings.openai_api_key
