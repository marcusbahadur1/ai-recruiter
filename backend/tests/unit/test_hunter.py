"""Unit tests for the Hunter.io service."""

import httpx
import pytest

from app.services.hunter import _FINDER_URL, _MIN_CONFIDENCE, find_email
from tests.unit.conftest import mock_http

_API_KEY = "hunter-test-key"


@pytest.mark.asyncio
async def test_find_email_returns_email_above_confidence_threshold():
    async with mock_http() as mock:
        mock.get(_FINDER_URL).mock(
            return_value=httpx.Response(
                200,
                json={"data": {"email": "jane@acme.com", "confidence": 90}},
            )
        )
        result = await find_email(
            first_name="Jane", last_name="Doe", domain="acme.com", api_key=_API_KEY
        )

    assert result == "jane@acme.com"


@pytest.mark.asyncio
async def test_find_email_returns_none_when_confidence_too_low():
    async with mock_http() as mock:
        mock.get(_FINDER_URL).mock(
            return_value=httpx.Response(
                200,
                json={"data": {"email": "jane@acme.com", "confidence": 50}},
            )
        )
        result = await find_email(
            first_name="Jane", last_name="Doe", domain="acme.com", api_key=_API_KEY
        )

    assert result is None


@pytest.mark.asyncio
async def test_find_email_returns_none_exactly_at_threshold():
    """Confidence must be strictly greater than _MIN_CONFIDENCE."""
    async with mock_http() as mock:
        mock.get(_FINDER_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {"email": "jane@acme.com", "confidence": _MIN_CONFIDENCE}
                },
            )
        )
        result = await find_email(
            first_name="Jane", last_name="Doe", domain="acme.com", api_key=_API_KEY
        )

    assert result is None


@pytest.mark.asyncio
async def test_find_email_returns_none_on_http_error():
    async with mock_http() as mock:
        mock.get(_FINDER_URL).mock(
            return_value=httpx.Response(429, json={"errors": ["rate limited"]})
        )
        result = await find_email(
            first_name="Jane", last_name="Doe", domain="acme.com", api_key=_API_KEY
        )

    assert result is None


@pytest.mark.asyncio
async def test_find_email_passes_correct_params():
    async with mock_http() as mock:
        route = mock.get(_FINDER_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"email": None, "confidence": 0}}
            )
        )
        await find_email(
            first_name="Bob", last_name="Smith", domain="example.com", api_key=_API_KEY
        )

    url = str(route.calls.last.request.url)
    assert "first_name=Bob" in url
    assert "last_name=Smith" in url
    assert "domain=example.com" in url
