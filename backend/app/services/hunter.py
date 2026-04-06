"""Hunter.io email finder client — only returns emails with confidence > 70%."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_FINDER_URL = "https://api.hunter.io/v2/email-finder"
_MIN_CONFIDENCE = 70


async def find_email(
    first_name: str,
    last_name: str,
    domain: str,
    api_key: str,
) -> Optional[str]:
    """Find a candidate's work email via Hunter.io.

    Args:
        first_name: Candidate's first name.
        last_name: Candidate's last name.
        domain: Company domain (e.g. ``"acme.com"``).
        api_key: Hunter.io API key (decrypted tenant key).

    Returns:
        Email address if found with confidence > 70%, ``None`` otherwise.
    """
    params = {
        "first_name": first_name,
        "last_name": last_name,
        "domain": domain,
        "api_key": api_key,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(_FINDER_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Hunter HTTP %s for %r %r @%r: %s",
                exc.response.status_code,
                first_name,
                last_name,
                domain,
                exc.response.text,
            )
            return None
        except httpx.RequestError as exc:
            logger.error(
                "Hunter request error for %r %r @%r: %s",
                first_name,
                last_name,
                domain,
                exc,
            )
            return None

    data = response.json()
    result = data.get("data") or {}
    email = result.get("email")
    confidence = result.get("confidence") or 0

    if email and confidence > _MIN_CONFIDENCE:
        return email

    return None
