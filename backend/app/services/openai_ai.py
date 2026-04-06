"""Async wrapper around the OpenAI SDK — same interface as ClaudeAIService."""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIService:
    """Thin async wrapper around AsyncOpenAI.

    Instantiated per-request via AIProvider with the resolved API key.
    """

    _DEFAULT_MODEL = "gpt-4o"
    _DEFAULT_MAX_TOKENS = 1024

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        """Send a user prompt (with optional system message) and return the text reply.

        Args:
            prompt: The user-turn content.
            system: Optional system instruction.
            max_tokens: Upper bound on generated tokens.

        Returns:
            The assistant's reply as a plain string.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self._DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    async def complete_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """Like ``complete`` but requests JSON output and parses the reply.

        Args:
            prompt: The user-turn content.
            system: Optional system instruction.
            max_tokens: Upper bound on generated tokens.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            ValueError: If the response cannot be parsed as JSON.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self._DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=messages,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("OpenAIService.complete_json: invalid JSON response: %s", raw)
            raise ValueError(f"Model returned non-JSON response: {raw!r}") from exc
