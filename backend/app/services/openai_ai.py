"""Async wrapper around the OpenAI SDK — same interface as ClaudeAIService."""
import json
import logging
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIService:
    """Thin async wrapper around AsyncOpenAI."""

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
        # OpenAI requires the word 'json' in messages when using json_object response format
        json_system = (system + " Return your response as JSON.") if system else "Return your response as JSON."
        messages: list[dict[str, str]] = [
            {"role": "system", "content": json_system},
            {"role": "user", "content": prompt},
        ]
        response = await self._client.chat.completions.create(
            model=self._DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=messages,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""

        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("OpenAIService.complete_json: invalid JSON response: %s", raw)
            raise ValueError(f"Model returned non-JSON response: {raw!r}") from exc
