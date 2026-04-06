"""Unit tests for the BrightData service."""

import httpx
import pytest

from app.services.brightdata import (
    _SNAPSHOT_URL,
    _TRIGGER_URL,
    get_linkedin_profile,
)
from tests.unit.conftest import mock_http

_API_KEY = "bd-test-key"
_LINKEDIN_URL = "https://www.linkedin.com/in/jane-doe"
_SNAPSHOT_ID = "snap_abc123"
_SNAPSHOT_FETCH_URL = _SNAPSHOT_URL.format(snapshot_id=_SNAPSHOT_ID)


@pytest.mark.asyncio
async def test_get_linkedin_profile_happy_path(monkeypatch):
    monkeypatch.setattr("app.services.brightdata.asyncio.sleep", lambda _: _noop())

    async with mock_http() as mock:
        mock.post(_TRIGGER_URL).mock(
            return_value=httpx.Response(200, json={"snapshot_id": _SNAPSHOT_ID})
        )
        mock.get(_SNAPSHOT_FETCH_URL).mock(
            return_value=httpx.Response(
                200,
                json=[{"name": "Jane Doe", "headline": "Java Developer"}],
            )
        )
        profile = await get_linkedin_profile(_LINKEDIN_URL, api_key=_API_KEY)

    assert profile == {"name": "Jane Doe", "headline": "Java Developer"}


@pytest.mark.asyncio
async def test_get_linkedin_profile_returns_empty_on_trigger_error():
    async with mock_http() as mock:
        mock.post(_TRIGGER_URL).mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        profile = await get_linkedin_profile(_LINKEDIN_URL, api_key=_API_KEY)

    assert profile == {}


@pytest.mark.asyncio
async def test_get_linkedin_profile_returns_empty_on_empty_snapshot(monkeypatch):
    monkeypatch.setattr("app.services.brightdata.asyncio.sleep", lambda _: _noop())

    async with mock_http() as mock:
        mock.post(_TRIGGER_URL).mock(
            return_value=httpx.Response(200, json={"snapshot_id": _SNAPSHOT_ID})
        )
        mock.get(_SNAPSHOT_FETCH_URL).mock(
            return_value=httpx.Response(200, json=[])
        )
        profile = await get_linkedin_profile(_LINKEDIN_URL, api_key=_API_KEY)

    assert profile == {}


@pytest.mark.asyncio
async def test_get_linkedin_profile_polls_on_202(monkeypatch):
    monkeypatch.setattr("app.services.brightdata.asyncio.sleep", lambda _: _noop())
    monkeypatch.setattr("app.services.brightdata._MAX_POLL_ATTEMPTS", 3)

    responses = iter([
        httpx.Response(202),
        httpx.Response(202),
        httpx.Response(200, json=[{"name": "Jane"}]),
    ])

    async with mock_http() as mock:
        mock.post(_TRIGGER_URL).mock(
            return_value=httpx.Response(200, json={"snapshot_id": _SNAPSHOT_ID})
        )
        mock.get(_SNAPSHOT_FETCH_URL).mock(side_effect=responses)
        profile = await get_linkedin_profile(_LINKEDIN_URL, api_key=_API_KEY)

    assert profile == {"name": "Jane"}


@pytest.mark.asyncio
async def test_get_linkedin_profile_times_out_after_max_attempts(monkeypatch):
    monkeypatch.setattr("app.services.brightdata.asyncio.sleep", lambda _: _noop())
    monkeypatch.setattr("app.services.brightdata._MAX_POLL_ATTEMPTS", 2)

    async with mock_http() as mock:
        mock.post(_TRIGGER_URL).mock(
            return_value=httpx.Response(200, json={"snapshot_id": _SNAPSHOT_ID})
        )
        mock.get(_SNAPSHOT_FETCH_URL).mock(return_value=httpx.Response(202))
        profile = await get_linkedin_profile(_LINKEDIN_URL, api_key=_API_KEY)

    assert profile == {}


async def _noop():
    pass
