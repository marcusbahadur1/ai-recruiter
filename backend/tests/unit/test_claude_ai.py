"""Unit tests for ClaudeAIService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.claude_ai import ClaudeAIService


@pytest.fixture()
def service():
    return ClaudeAIService(api_key="sk-ant-test")


# ── complete ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_returns_text(service):
    mock_content = MagicMock()
    mock_content.text = "Hello, world!"
    mock_message = MagicMock()
    mock_message.content = [mock_content]

    with patch.object(
        service._client.messages, "create", new=AsyncMock(return_value=mock_message)
    ):
        result = await service.complete(prompt="Say hello")

    assert result == "Hello, world!"


@pytest.mark.asyncio
async def test_complete_with_system_passes_system_kwarg(service):
    mock_content = MagicMock()
    mock_content.text = "Result"
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    create_mock = AsyncMock(return_value=mock_message)

    with patch.object(service._client.messages, "create", new=create_mock):
        await service.complete(prompt="Hello", system="You are helpful")

    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["system"] == "You are helpful"


@pytest.mark.asyncio
async def test_complete_without_system_omits_system_kwarg(service):
    mock_content = MagicMock()
    mock_content.text = "Result"
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    create_mock = AsyncMock(return_value=mock_message)

    with patch.object(service._client.messages, "create", new=create_mock):
        await service.complete(prompt="Hello")

    call_kwargs = create_mock.call_args.kwargs
    assert "system" not in call_kwargs


# ── complete_json ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_json_parses_valid_json(service):
    mock_content = MagicMock()
    mock_content.text = '{"score": 8, "reasoning": "Strong match"}'
    mock_message = MagicMock()
    mock_message.content = [mock_content]

    with patch.object(
        service._client.messages, "create", new=AsyncMock(return_value=mock_message)
    ):
        result = await service.complete_json(prompt="Score this candidate")

    assert result == {"score": 8, "reasoning": "Strong match"}


@pytest.mark.asyncio
async def test_complete_json_strips_markdown_fences(service):
    mock_content = MagicMock()
    mock_content.text = '```json\n{"key": "value"}\n```'
    mock_message = MagicMock()
    mock_message.content = [mock_content]

    with patch.object(
        service._client.messages, "create", new=AsyncMock(return_value=mock_message)
    ):
        result = await service.complete_json(prompt="Return JSON")

    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_complete_json_raises_on_invalid_json(service):
    mock_content = MagicMock()
    mock_content.text = "This is not JSON at all."
    mock_message = MagicMock()
    mock_message.content = [mock_content]

    with patch.object(
        service._client.messages, "create", new=AsyncMock(return_value=mock_message)
    ):
        with pytest.raises(ValueError, match="non-JSON"):
            await service.complete_json(prompt="Return JSON")
