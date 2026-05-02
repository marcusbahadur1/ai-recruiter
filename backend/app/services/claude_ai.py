"""Async wrapper around the Anthropic SDK (Claude Sonnet)."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class ClaudeAIService:
    """Thin async wrapper around AsyncAnthropic.

    Instantiated per-request via AIProvider with the resolved API key.
    """

    _DEFAULT_MODEL = "claude-sonnet-4-6"
    _DEFAULT_MAX_TOKENS = 1024

    def __init__(self, api_key: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        """Send a user prompt (with optional system message) and return the text reply.

        Args:
            prompt: The user-turn content.
            system: Optional system instruction prepended to the conversation.
            max_tokens: Upper bound on generated tokens.

        Returns:
            The assistant's reply as a plain string.
        """
        kwargs: dict[str, Any] = {
            "model": self._DEFAULT_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        message = await self._client.messages.create(**kwargs)
        return message.content[0].text

    async def stream_complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        """Stream text tokens from Claude as they are generated."""
        kwargs: dict[str, Any] = {
            "model": self._DEFAULT_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    @staticmethod
    def _clean_json_response(text: str) -> str:
        """Strip markdown code fences that the model may wrap around JSON output."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]  # remove ```json
        elif text.startswith("```"):
            text = text[3:]  # remove ```
        if text.endswith("```"):
            text = text[:-3]  # remove trailing ```
        return text.strip()

    async def complete_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """Like ``complete`` but parses the reply as JSON and returns a dict.

        Args:
            prompt: The user-turn content.  Should instruct the model to return
                JSON with no markdown formatting, no code fences, no ```json prefix.
            system: Optional system instruction.
            max_tokens: Upper bound on generated tokens.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            ValueError: If the response cannot be parsed as JSON.
        """
        raw = await self.complete(prompt=prompt, system=system, max_tokens=max_tokens)
        cleaned = self._clean_json_response(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "ClaudeAIService.complete_json: invalid JSON response: %s", raw
            )
            raise ValueError(f"Model returned non-JSON response: {raw!r}") from exc
