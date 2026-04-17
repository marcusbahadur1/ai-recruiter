"""Unit tests for the AIProvider facade."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.ai_provider import AIProvider
from app.services.claude_ai import ClaudeAIService
from app.services.openai_ai import OpenAIService
from app.services.crypto import encrypt


# ── Service resolution ────────────────────────────────────────────────────────

def test_anthropic_tenant_builds_claude_service(tenant):
    tenant.ai_provider = "anthropic"
    tenant.ai_api_key = None
    provider = AIProvider(tenant)
    svc = provider._get_claude_service()
    assert isinstance(svc, ClaudeAIService)


def test_openai_tenant_builds_openai_service(tenant_with_openai_key):
    provider = AIProvider(tenant_with_openai_key)
    svc = provider._get_openai_service()
    assert isinstance(svc, OpenAIService)


def test_openai_service_is_none_without_key(tenant, monkeypatch):
    tenant.ai_provider = "anthropic"
    tenant.ai_api_key = None
    monkeypatch.setattr("app.services.ai_provider.settings.openai_api_key", None)
    provider = AIProvider(tenant)
    assert provider._get_openai_service() is None


def test_tenant_key_decrypted_for_claude(tenant):
    raw_key = "sk-ant-custom-key-123"
    tenant.ai_provider = "anthropic"
    tenant.ai_api_key = encrypt(raw_key)
    provider = AIProvider(tenant)
    svc = provider._get_claude_service()
    assert svc is not None
    assert svc._client.api_key == raw_key


def test_openai_tenant_raises_without_any_key(tenant, monkeypatch):
    """complete() should raise when no provider key is available."""
    tenant.ai_provider = "openai"
    tenant.ai_api_key = None
    monkeypatch.setattr("app.services.ai_provider.settings.openai_api_key", None)
    monkeypatch.setattr("app.services.ai_provider.settings.anthropic_api_key", None)
    provider = AIProvider(tenant)
    with pytest.raises(ValueError, match="No AI provider"):
        import asyncio
        asyncio.get_event_loop().run_until_complete(provider.complete("hello"))


# ── Delegation to underlying service ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_delegates_to_service(tenant, monkeypatch):
    monkeypatch.setattr("app.services.ai_provider.settings.openai_api_key", None)
    provider = AIProvider(tenant)
    with patch.object(ClaudeAIService, "complete", new=AsyncMock(return_value="delegated")):
        result = await provider.complete(prompt="hello", system="sys", max_tokens=256)
    assert result == "delegated"


@pytest.mark.asyncio
async def test_complete_json_delegates_to_service(tenant, monkeypatch):
    monkeypatch.setattr("app.services.ai_provider.settings.openai_api_key", None)
    provider = AIProvider(tenant)
    with patch.object(ClaudeAIService, "complete_json", new=AsyncMock(return_value={"key": "val"})):
        result = await provider.complete_json(prompt="json?")
    assert result == {"key": "val"}
