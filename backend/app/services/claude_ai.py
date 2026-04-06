"""Async wrapper around the Anthropic SDK (Claude Sonnet)."""

import json
import logging
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

    async def complete_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """Like ``complete`` but parses the reply as JSON and returns a dict.

        Args:
            prompt: The user-turn content.  Should instruct the model to return JSON.
            system: Optional system instruction.
            max_tokens: Upper bound on generated tokens.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            ValueError: If the response cannot be parsed as JSON.
        """
        raw = await self.complete(prompt=prompt, system=system, max_tokens=max_tokens)
        # Strip markdown code fences if the model wraps its JSON
        stripped = raw.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1]) if len(lines) > 2 else stripped
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            logger.error("ClaudeAIService.complete_json: invalid JSON response: %s", raw)
            raise ValueError(f"Model returned non-JSON response: {raw!r}") from exc
