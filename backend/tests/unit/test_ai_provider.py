"""Unit tests for the AIProvider facade."""

import pytest
from unittest.mock import AsyncMock

from app.services.ai_provider import AIProvider
from app.services.claude_ai import ClaudeAIService
from app.services.openai_ai import OpenAIService
from app.services.crypto import encrypt


# ── Provider routing ──────────────────────────────────────────────────────────

def test_anthropic_tenant_builds_claude_service(tenant):
    tenant.ai_provider = "anthropic"
    tenant.ai_api_key = None
    provider = AIProvider(tenant)
    assert isinstance(provider._service, ClaudeAIService)


def test_openai_tenant_builds_openai_service(tenant_with_openai_key):
    provider = AIProvider(tenant_with_openai_key)
    assert isinstance(provider._service, OpenAIService)


def test_tenant_key_decrypted_and_used(tenant):
    raw_key = "sk-ant-custom-key-123"
    tenant.ai_provider = "anthropic"
    tenant.ai_api_key = encrypt(raw_key)
    provider = AIProvider(tenant)
    assert provider._service._client.api_key == raw_key


def test_openai_tenant_raises_without_any_key(tenant, monkeypatch):
    tenant.ai_provider = "openai"
    tenant.ai_api_key = None
    monkeypatch.setattr("app.services.ai_provider.settings.openai_api_key", None)
    with pytest.raises(ValueError, match="No OpenAI API key"):
        AIProvider(tenant)


# ── Delegation to underlying service ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_delegates_to_service(tenant):
    provider = AIProvider(tenant)
    provider._service.complete = AsyncMock(return_value="delegated")

    result = await provider.complete(prompt="hello", system="sys", max_tokens=256)

    provider._service.complete.assert_awaited_once_with(
        prompt="hello", system="sys", max_tokens=256
    )
    assert result == "delegated"


@pytest.mark.asyncio
async def test_complete_json_delegates_to_service(tenant):
    provider = AIProvider(tenant)
    provider._service.complete_json = AsyncMock(return_value={"key": "val"})

    result = await provider.complete_json(prompt="json?")

    assert result == {"key": "val"}
