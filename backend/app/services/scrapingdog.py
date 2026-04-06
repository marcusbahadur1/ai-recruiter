"""ScrapingDog Google Search API client for LinkedIn candidate discovery."""

import logging

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.scrapingdog.com/google"


async def search_linkedin(
    query: str,
    start: int,
    api_key: str,
) -> list[dict]:
    """Search Google via ScrapingDog and return normalised LinkedIn results.

    Args:
        query: Search query string, e.g.
               ``'"Java Developer Melbourne site:linkedin.com/in/"'``.
        start: Pagination offset (0, 10, 20, … 90 for pages 1–10).
        api_key: ScrapingDog API key (platform or tenant).

    Returns:
        List of dicts with keys ``title``, ``snippet``, and ``link``.
        Returns an empty list on API errors so the caller can continue.
    """
    params = {
        "api_key": api_key,
        "query": query,
        "advance_search": "false",
        "results": "10",
        "start": str(start),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(_BASE_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "ScrapingDog HTTP error %s for query %r (start=%d): %s",
                exc.response.status_code,
                query,
                start,
                exc.response.text,
            )
            return []
        except httpx.RequestError as exc:
            logger.error(
                "ScrapingDog request error for query %r (start=%d): %s",
                query,
                start,
                exc,
            )
            return []

    data = response.json()
    return _normalise(data)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _normalise(data: dict) -> list[dict]:
    """Extract and normalise organic results from the raw ScrapingDog response."""
    organic = data.get("organic_results", [])
    results = []
    for item in organic:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        if link:
            results.append({"title": title, "snippet": snippet, "link": link})
    return results
