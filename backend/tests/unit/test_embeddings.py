"""Unit tests for the embeddings service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embeddings import generate_embedding
from app.services.crypto import encrypt


def _mock_embedding_response(vector: list[float]) -> MagicMock:
    item = MagicMock()
    item.embedding = vector
    response = MagicMock()
    response.data = [item]
    return response


@pytest.mark.asyncio
async def test_generate_embedding_returns_vector(tenant):
    expected = [0.1, 0.2, 0.3]

    with patch("app.services.embeddings.AsyncOpenAI") as MockClient:
        instance = MockClient.return_value
        instance.embeddings.create = AsyncMock(
            return_value=_mock_embedding_response(expected)
        )
        result = await generate_embedding("hello world", tenant=tenant)

    assert result == expected


@pytest.mark.asyncio
async def test_generate_embedding_uses_correct_model(tenant):
    with patch("app.services.embeddings.AsyncOpenAI") as MockClient:
        instance = MockClient.return_value
        instance.embeddings.create = AsyncMock(
            return_value=_mock_embedding_response([0.0])
        )
        await generate_embedding("text", tenant=tenant)

    call_kwargs = instance.embeddings.create.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"
    assert call_kwargs["dimensions"] == 1536


@pytest.mark.asyncio
async def test_generate_embedding_uses_tenant_openai_key(tenant_with_openai_key):
    with patch("app.services.embeddings.AsyncOpenAI") as MockClient:
        instance = MockClient.return_value
        instance.embeddings.create = AsyncMock(
            return_value=_mock_embedding_response([0.5])
        )
        await generate_embedding("text", tenant=tenant_with_openai_key)

    # The client should be constructed with the tenant's decrypted key
    MockClient.assert_called_once_with(api_key="sk-test-openai-key")


@pytest.mark.asyncio
async def test_generate_embedding_raises_without_key(tenant, monkeypatch):
    tenant.ai_provider = "anthropic"
    tenant.ai_api_key = None
    monkeypatch.setattr("app.services.embeddings.settings.openai_api_key", None)

    with pytest.raises(ValueError, match="No OpenAI API key"):
        await generate_embedding("text", tenant=tenant)
