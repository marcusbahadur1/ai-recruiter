"""Apollo.io email discovery client."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_MATCH_URL = "https://api.apollo.io/v1/people/match"


async def find_email(name: str, company: str, api_key: str) -> Optional[str]:
    """Look up a candidate's email via Apollo.io people/match.

    Args:
        name: Full name of the candidate (e.g. ``"Jane Smith"``).
        company: Current company name (e.g. ``"Acme Corp"``).
        api_key: Apollo.io API key (decrypted tenant key).

    Returns:
        Email address string if found, ``None`` otherwise.
    """
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }
    payload = {
        "name": name,
        "organization_name": company,
        "reveal_personal_emails": True,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(_MATCH_URL, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Apollo HTTP %s for %r at %r: %s",
                exc.response.status_code,
                name,
                company,
                exc.response.text,
            )
            return None
        except httpx.RequestError as exc:
            logger.error("Apollo request error for %r at %r: %s", name, company, exc)
            return None

    data = response.json()
    person = data.get("person") or {}
    email = person.get("email")
    if email:
        return email

    # Fallback: check email_status field within the person object
    return None
