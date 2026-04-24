"""Unsplash stock photo integration for the AI Marketing Module.

Free tier: 50 requests/hour. Redis caching keeps well within this limit.

Unsplash Terms of Service requirements enforced here:
1. Every photo used must store attribution (photographer name + links).
2. trigger_download() must be called every time a photo is selected for use.
3. "Photo by X on Unsplash" must be displayed in any UI showing the photo.
   The image_attribution dict returned by search_photo() contains all required values.
"""
import hashlib
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.unsplash.com"
_CACHE_TTL = 3600  # 1 hour


class UnsplashRateLimitError(Exception):
    """Raised when the Unsplash API rate limit (50 req/hr on free tier) is hit."""


class UnsplashClient:
    """Async Unsplash API client with Redis result caching."""

    def __init__(self) -> None:
        from app.config import settings
        self._access_key = settings.unsplash_access_key or ""

    async def search_photo(
        self, query: str, orientation: str = "landscape"
    ) -> dict[str, Any] | None:
        """Search for a photo matching the query string.

        Checks Redis cache first (TTL 1 hour). On a cache miss, calls the
        Unsplash search API, picks the best result, caches and returns it.

        Returns a dict with:
          image_url             — 1080px-wide regular URL
          download_trigger_url  — must be passed to trigger_download() when used
          attribution           — {photographer_name, photographer_url, unsplash_url}

        Returns None when no results are found.
        Raises UnsplashRateLimitError on HTTP 429.
        """
        cache_key = f"unsplash:{hashlib.md5(query.encode()).hexdigest()}"

        # ── Cache read ─────────────────────────────────────────────────────────
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("Unsplash cache hit for query=%r", query)
            return cached

        # ── API call ───────────────────────────────────────────────────────────
        if not self._access_key:
            logger.warning("UNSPLASH_ACCESS_KEY not set — skipping image search")
            return None

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_API_BASE}/search/photos",
                params={
                    "query": query,
                    "orientation": orientation,
                    "per_page": 5,
                    "client_id": self._access_key,
                },
            )

        if resp.status_code == 429:
            raise UnsplashRateLimitError("Unsplash rate limit reached (50 req/hr on free tier)")

        resp.raise_for_status()
        results = resp.json().get("results", [])

        if not results:
            logger.debug("Unsplash returned no results for query=%r", query)
            return None

        # Pick best result — highest resolution landscape/square photo
        photo = results[0]

        result = {
            "image_url": photo["urls"]["regular"],
            "download_trigger_url": photo["links"]["download_location"],
            "attribution": {
                "photographer_name": photo["user"]["name"],
                "photographer_url": (
                    photo["user"]["links"]["html"]
                    + "?utm_source=airecruiterz&utm_medium=referral"
                ),
                "unsplash_url": "https://unsplash.com/?utm_source=airecruiterz&utm_medium=referral",
            },
        }

        self._cache_set(cache_key, result)
        logger.debug("Unsplash photo selected for query=%r photographer=%s", query, photo["user"]["name"])
        return result

    async def trigger_download(self, download_location_url: str) -> None:
        """Notify Unsplash that a photo was used — required by ToS on every use.

        Swallows all exceptions; a failed trigger must never break content generation.
        """
        if not self._access_key:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.get(
                    download_location_url,
                    params={"client_id": self._access_key},
                )
            logger.debug("Unsplash download triggered: %s", download_location_url[:80])
        except Exception as exc:
            logger.warning("Unsplash trigger_download failed (non-fatal): %s", exc)

    # ── Redis helpers ──────────────────────────────────────────────────────────

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        try:
            import json
            import redis as redis_lib
            from app.config import settings
            r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2, decode_responses=True)
            raw = r.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.debug("Unsplash cache read failed (non-fatal): %s", exc)
            return None

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        try:
            import json
            import redis as redis_lib
            from app.config import settings
            r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2, decode_responses=True)
            r.setex(key, _CACHE_TTL, json.dumps(value))
        except Exception as exc:
            logger.debug("Unsplash cache write failed (non-fatal): %s", exc)
