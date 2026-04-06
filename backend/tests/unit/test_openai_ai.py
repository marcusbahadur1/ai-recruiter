"""Unit tests for OpenAIService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.openai_ai import OpenAIService


@pytest.fixture()
def service():
    return OpenAIService(api_key="sk-test-openai")


def _mock_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ── complete ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_returns_text(service):
    create_mock = AsyncMock(return_value=_mock_response("Hello!"))

    with patch.object(service._client.chat.completions, "create", new=create_mock):
        result = await service.complete(prompt="Say hello")

    assert result == "Hello!"


@pytest.mark.asyncio
async def test_complete_with_system_prepends_system_message(service):
    create_mock = AsyncMock(return_value=_mock_response("ok"))

    with patch.object(service._client.chat.completions, "create", new=create_mock):
        await service.complete(prompt="Hello", system="Be concise")

    messages = create_mock.call_args.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "Be concise"}
    assert messages[1] == {"role": "user", "content": "Hello"}


@pytest.mark.asyncio
async def test_complete_without_system_only_has_user_message(service):
    create_mock = AsyncMock(return_value=_mock_response("ok"))

    with patch.object(service._client.chat.completions, "create", new=create_mock):
        await service.complete(prompt="Hello")

    messages = create_mock.call_args.kwargs["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


# ── complete_json ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_json_parses_valid_json(service):
    create_mock = AsyncMock(return_value=_mock_response('{"score": 7}'))

    with patch.object(service._client.chat.completions, "create", new=create_mock):
        result = await service.complete_json(prompt="Return JSON")

    assert result == {"score": 7}


@pytest.mark.asyncio
async def test_complete_json_uses_json_object_format(service):
    create_mock = AsyncMock(return_value=_mock_response('{"x": 1}'))

    with patch.object(service._client.chat.completions, "create", new=create_mock):
        await service.complete_json(prompt="JSON please")

    kwargs = create_mock.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_complete_json_raises_on_invalid_json(service):
    create_mock = AsyncMock(return_value=_mock_response("not json"))

    with patch.object(service._client.chat.completions, "create", new=create_mock):
        with pytest.raises(ValueError, match="non-JSON"):
            await service.complete_json(prompt="Return JSON")
