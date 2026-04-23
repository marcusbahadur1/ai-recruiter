"""AI provider facade — tries OpenAI first, falls back to Anthropic.
All application code MUST use this facade. Never call SDKs directly.
"""

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.services.claude_ai import ClaudeAIService
from app.services.crypto import decrypt
from app.services.openai_ai import OpenAIService

if TYPE_CHECKING:
    from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


class AIProvider:
    def __init__(self, tenant: "Tenant") -> None:
        self._tenant = tenant

    def _get_openai_service(self) -> OpenAIService | None:
        raw_key = self._tenant.ai_api_key
        resolved_key = decrypt(raw_key) if raw_key else None
        api_key = resolved_key if self._tenant.ai_provider == "openai" else None
        api_key = api_key or settings.openai_api_key
        if api_key:
            return OpenAIService(api_key=api_key)
        return None

    def _get_claude_service(self) -> ClaudeAIService | None:
        raw_key = self._tenant.ai_api_key
        resolved_key = decrypt(raw_key) if raw_key else None
        api_key = resolved_key if self._tenant.ai_provider == "anthropic" else None
        api_key = api_key or settings.anthropic_api_key
        if api_key:
            return ClaudeAIService(api_key=api_key)
        return None

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> str:
        primary = self._tenant.ai_provider or "anthropic"
        if primary == "openai":
            first_svc, first_name = self._get_openai_service(), "OpenAI"
            second_svc, second_name = self._get_claude_service(), "Anthropic"
        else:
            first_svc, first_name = self._get_claude_service(), "Anthropic"
            second_svc, second_name = self._get_openai_service(), "OpenAI"

        if first_svc:
            try:
                result = await first_svc.complete(
                    prompt=prompt, system=system, max_tokens=max_tokens
                )
                logger.debug("AIProvider: %s complete succeeded", first_name)
                return result
            except Exception as e:
                logger.warning(
                    "AIProvider: %s complete failed (%s) — trying %s",
                    first_name,
                    e,
                    second_name,
                )

        if second_svc:
            try:
                result = await second_svc.complete(
                    prompt=prompt, system=system, max_tokens=max_tokens
                )
                logger.debug("AIProvider: %s complete succeeded", second_name)
                return result
            except Exception as e:
                logger.warning(
                    "AIProvider: %s complete also failed (%s)", second_name, e
                )
                raise

        raise ValueError(
            "No AI provider available — set OPENAI_API_KEY or ANTHROPIC_API_KEY"
        )

    async def stream_complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Stream text tokens from the primary AI provider.

        Falls back to a single-chunk yield from complete() if no streaming
        service is available (e.g. misconfigured keys).
        """
        primary = self._tenant.ai_provider or "anthropic"
        svc = (
            self._get_claude_service()
            if primary == "anthropic"
            else self._get_openai_service()
        )
        if svc:
            async for token in svc.stream_complete(
                prompt=prompt, system=system, max_tokens=max_tokens
            ):
                yield token
        else:
            # No streaming service — yield full response as one chunk
            result = await self.complete(prompt=prompt, system=system, max_tokens=max_tokens)
            yield result

    async def complete_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        primary = self._tenant.ai_provider or "anthropic"
        if primary == "openai":
            first_svc, first_name = self._get_openai_service(), "OpenAI"
            second_svc, second_name = self._get_claude_service(), "Anthropic"
        else:
            first_svc, first_name = self._get_claude_service(), "Anthropic"
            second_svc, second_name = self._get_openai_service(), "OpenAI"

        if first_svc:
            try:
                result = await first_svc.complete_json(
                    prompt=prompt, system=system, max_tokens=max_tokens
                )
                logger.debug("AIProvider: %s complete_json succeeded", first_name)
                return result
            except Exception as e:
                logger.warning(
                    "AIProvider: %s complete_json failed (%s) — trying %s",
                    first_name,
                    e,
                    second_name,
                )

        if second_svc:
            try:
                result = await second_svc.complete_json(
                    prompt=prompt, system=system, max_tokens=max_tokens
                )
                logger.debug("AIProvider: %s complete_json succeeded", second_name)
                return result
            except Exception as e:
                logger.warning(
                    "AIProvider: %s complete_json also failed (%s)", second_name, e
                )
                raise

        raise ValueError(
            "No AI provider available — set OPENAI_API_KEY or ANTHROPIC_API_KEY"
        )
