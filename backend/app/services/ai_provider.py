"""AI provider facade — routes to ClaudeAIService or OpenAIService based on tenant config.

All application code MUST use this facade.  Never call the Anthropic or OpenAI
SDKs directly from routers or Celery tasks.
"""

from typing import TYPE_CHECKING, Any

from app.config import settings
from app.services.claude_ai import ClaudeAIService
from app.services.crypto import decrypt
from app.services.openai_ai import OpenAIService

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class AIProvider:
    """Facade that delegates to the tenant's configured AI provider.

    Usage::

        ai = AIProvider(tenant)
        text = await ai.complete(prompt="...", system="...")
        data = await ai.complete_json(prompt="Return JSON: ...")
    """

    def __init__(self, tenant: "Tenant") -> None:
        self._provider = tenant.ai_provider
        self._service = self._build_service(tenant)

    # ── Public interface ───────────────────────────────────────────────────────

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> str:
        """Send a prompt and return the plain-text reply.

        Args:
            prompt: User-turn content.
            system: Optional system instruction.
            max_tokens: Token budget for the response.

        Returns:
            Assistant reply as a string.
        """
        return await self._service.complete(
            prompt=prompt, system=system, max_tokens=max_tokens
        )

    async def complete_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Send a prompt and return the reply parsed as JSON.

        Args:
            prompt: User-turn content — should instruct the model to return JSON.
            system: Optional system instruction.
            max_tokens: Token budget for the response.

        Returns:
            Parsed JSON dict.

        Raises:
            ValueError: If the model returns malformed JSON.
        """
        return await self._service.complete_json(
            prompt=prompt, system=system, max_tokens=max_tokens
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_service(self, tenant: "Tenant") -> ClaudeAIService | OpenAIService:
        """Resolve the API key and instantiate the correct backend service."""
        raw_key = tenant.ai_api_key
        resolved_key = decrypt(raw_key) if raw_key else None

        if tenant.ai_provider == "anthropic":
            api_key = resolved_key or settings.anthropic_api_key
            return ClaudeAIService(api_key=api_key)

        # openai
        api_key = resolved_key or settings.openai_api_key
        if not api_key:
            raise ValueError(
                "No OpenAI API key available: set OPENAI_API_KEY in environment "
                "or configure tenant.ai_api_key."
            )
        return OpenAIService(api_key=api_key)
