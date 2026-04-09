"""AI provider facade — tries OpenAI first, falls back to Anthropic.
All application code MUST use this facade. Never call SDKs directly.
"""
import logging
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
        # Always try OpenAI first
        openai_svc = self._get_openai_service()
        if openai_svc:
            try:
                result = await openai_svc.complete(
                    prompt=prompt, system=system, max_tokens=max_tokens
                )
                logger.debug("AIProvider: OpenAI complete succeeded")
                return result
            except Exception as e:
                logger.warning("AIProvider: OpenAI complete failed (%s) — trying Anthropic", e)

        # Fall back to Anthropic
        claude_svc = self._get_claude_service()
        if claude_svc:
            try:
                result = await claude_svc.complete(
                    prompt=prompt, system=system, max_tokens=max_tokens
                )
                logger.debug("AIProvider: Anthropic complete succeeded")
                return result
            except Exception as e:
                logger.warning("AIProvider: Anthropic complete also failed (%s)", e)
                raise

        raise ValueError("No AI provider available — set OPENAI_API_KEY or ANTHROPIC_API_KEY")

    async def complete_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        # Always try OpenAI first
        openai_svc = self._get_openai_service()
        if openai_svc:
            try:
                result = await openai_svc.complete_json(
                    prompt=prompt, system=system, max_tokens=max_tokens
                )
                logger.debug("AIProvider: OpenAI complete_json succeeded")
                return result
            except Exception as e:
                logger.warning("AIProvider: OpenAI complete_json failed (%s) — trying Anthropic", e)

        # Fall back to Anthropic
        claude_svc = self._get_claude_service()
        if claude_svc:
            try:
                result = await claude_svc.complete_json(
                    prompt=prompt, system=system, max_tokens=max_tokens
                )
                logger.debug("AIProvider: Anthropic complete_json succeeded")
                return result
            except Exception as e:
                logger.warning("AIProvider: Anthropic complete_json also failed (%s)", e)
                raise

        raise ValueError("No AI provider available — set OPENAI_API_KEY or ANTHROPIC_API_KEY")
