"""Embedding generation service.

Uses OpenAI text-embedding-3-small (1536 dims) by default.

NOTE: Anthropic does not currently expose a public text-embedding API.
      When tenant.ai_provider == 'anthropic' we fall back to the platform
      OpenAI key for embeddings — a tenant-supplied OpenAI key is used if
      available. TODO: revisit if Anthropic releases an embedding endpoint.
"""

import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from app.config import settings
from app.services.crypto import decrypt

if TYPE_CHECKING:
    from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMS = 1536


async def generate_embedding(text: str, tenant: "Tenant | None" = None) -> list[float]:
    """Generate a 1536-dimensional embedding vector for *text*.

    Args:
        text: The text to embed.  Long inputs are silently truncated by the API.
        tenant: Optional tenant used to resolve a tenant-supplied OpenAI key.
                Falls back to the platform OPENAI_API_KEY if not provided or
                if the tenant has not set their own key.

    Returns:
        A list of 1536 floats (unit-normalised by the API).

    Raises:
        ValueError: If no OpenAI API key is available.
    """
    api_key = _resolve_openai_key(tenant)
    if not api_key:
        raise ValueError(
            "No OpenAI API key available for embeddings: set OPENAI_API_KEY "
            "in environment or configure tenant.ai_api_key (OpenAI)."
        )

    client = AsyncOpenAI(api_key=api_key)
    response = await client.embeddings.create(
        model=_EMBEDDING_MODEL,
        input=text,
        dimensions=_EMBEDDING_DIMS,
    )
    return response.data[0].embedding


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
