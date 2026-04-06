"""Snov.io email finder client."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_EMAILS_URL = "https://api.snov.io/v1/get-emails-from-names"


async def find_email(
    first_name: str,
    last_name: str,
    domain: str,
    api_key: str,
) -> Optional[str]:
    """Find a candidate's email via Snov.io get-emails-from-names endpoint.

    Args:
        first_name: Candidate's first name.
        last_name: Candidate's last name.
        domain: Company domain (e.g. ``"acme.com"``).
        api_key: Snov.io API key (decrypted tenant key).

    Returns:
        The first email address found, or ``None`` if no match.
    """
    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "domain": domain,
        "apiSecret": api_key,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(_EMAILS_URL, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Snov HTTP %s for %r %r @%r: %s",
                exc.response.status_code,
                first_name,
                last_name,
                domain,
                exc.response.text,
            )
            return None
        except httpx.RequestError as exc:
            logger.error(
                "Snov request error for %r %r @%r: %s",
                first_name,
                last_name,
                domain,
                exc,
            )
            return None

    data = response.json()
    emails = data.get("emails") or []
    if emails:
        return emails[0].get("email")
    return None
