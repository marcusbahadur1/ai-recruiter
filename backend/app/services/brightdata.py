"""BrightData LinkedIn People Profiles dataset client.

Triggers a collect-by-URL request and polls for the result.
Dataset: LinkedIn People Profiles (gd_l1viktl72bvl7bjuj0).
"""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_TRIGGER_URL = (
    "https://api.brightdata.com/datasets/v3/trigger"
    "?dataset_id=gd_l1viktl72bvl7bjuj0&include_errors=true"
)
_SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"

_POLL_INTERVAL_SECONDS = 5
_MAX_POLL_ATTEMPTS = 24  # 2 minutes maximum wait


async def get_linkedin_profile(linkedin_url: str, api_key: str) -> dict:
    """Fetch a LinkedIn public profile via BrightData People Profiles dataset.

    Triggers a one-URL collection, then polls until the snapshot is ready.

    Args:
        linkedin_url: Full LinkedIn profile URL,
                      e.g. ``"https://www.linkedin.com/in/john-doe-123abc"``.
        api_key: BrightData API key (platform or decrypted tenant key).

    Returns:
        The first (and only) profile dict returned by BrightData, or an empty
        dict if the profile could not be fetched.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        snapshot_id = await _trigger_collection(client, headers, linkedin_url)
        if not snapshot_id:
            return {}

        profile = await _poll_snapshot(client, headers, snapshot_id)
        return profile


# ── Internal helpers ───────────────────────────────────────────────────────────


async def _trigger_collection(
    client: httpx.AsyncClient,
    headers: dict,
    linkedin_url: str,
) -> str | None:
    """Trigger a BrightData collection and return the snapshot_id."""
    try:
        response = await client.post(
            _TRIGGER_URL,
            headers=headers,
            json=[{"url": linkedin_url}],
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "BrightData trigger HTTP %s for %r: %s",
            exc.response.status_code,
            linkedin_url,
            exc.response.text,
        )
        return None
    except httpx.RequestError as exc:
        logger.error("BrightData trigger request error for %r: %s", linkedin_url, exc)
        return None

    data = response.json()
    snapshot_id = data.get("snapshot_id")
    if not snapshot_id:
        logger.error("BrightData trigger: no snapshot_id in response: %s", data)
    return snapshot_id


async def _poll_snapshot(
    client: httpx.AsyncClient,
    headers: dict,
    snapshot_id: str,
) -> dict:
    """Poll the snapshot endpoint until the data is ready, then return the first record."""
    url = _SNAPSHOT_URL.format(snapshot_id=snapshot_id)

    for attempt in range(_MAX_POLL_ATTEMPTS):
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        try:
            response = await client.get(url, headers=headers, params={"format": "json"})
        except httpx.RequestError as exc:
            logger.error(
                "BrightData snapshot poll error (attempt %d): %s", attempt, exc
            )
            continue

        if response.status_code == 202:
            # Still processing
            continue

        if response.status_code != 200:
            logger.error(
                "BrightData snapshot HTTP %s (attempt %d): %s",
                response.status_code,
                attempt,
                response.text,
            )
            return {}

        records = response.json()
        if isinstance(records, list) and records:
            return records[0]
        return {}

    logger.error(
        "BrightData snapshot %r timed out after %d attempts",
        snapshot_id,
        _MAX_POLL_ATTEMPTS,
    )
    return {}
