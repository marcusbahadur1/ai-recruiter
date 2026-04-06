"""Unit tests for the Apollo.io service."""

import json

import httpx
import pytest

from app.services.apollo import find_email, _MATCH_URL
from tests.unit.conftest import mock_http

_API_KEY = "apollo-test-key"


@pytest.mark.asyncio
async def test_find_email_returns_email_from_person():
    async with mock_http() as mock:
        mock.post(_MATCH_URL).mock(
            return_value=httpx.Response(
                200,
                json={"person": {"email": "jane.doe@acme.com", "email_status": "verified"}},
            )
        )
        result = await find_email(name="Jane Doe", company="Acme Corp", api_key=_API_KEY)

    assert result == "jane.doe@acme.com"


@pytest.mark.asyncio
async def test_find_email_returns_none_when_no_person():
    async with mock_http() as mock:
        mock.post(_MATCH_URL).mock(
            return_value=httpx.Response(200, json={"person": None})
        )
        result = await find_email(name="Jane Doe", company="Acme Corp", api_key=_API_KEY)

    assert result is None


@pytest.mark.asyncio
async def test_find_email_returns_none_when_no_email_field():
    async with mock_http() as mock:
        mock.post(_MATCH_URL).mock(
            return_value=httpx.Response(200, json={"person": {"id": "abc123"}})
        )
        result = await find_email(name="Jane Doe", company="Acme Corp", api_key=_API_KEY)

    assert result is None


@pytest.mark.asyncio
async def test_find_email_returns_none_on_http_error():
    async with mock_http() as mock:
        mock.post(_MATCH_URL).mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        result = await find_email(name="Jane Doe", company="Acme Corp", api_key=_API_KEY)

    assert result is None


@pytest.mark.asyncio
async def test_find_email_sends_correct_payload():
    async with mock_http() as mock:
        route = mock.post(_MATCH_URL).mock(
            return_value=httpx.Response(200, json={"person": {"email": "x@y.com"}})
        )
        await find_email(name="John Smith", company="Tech Co", api_key=_API_KEY)

    payload = json.loads(route.calls.last.request.content)
    assert payload["name"] == "John Smith"
    assert payload["organization_name"] == "Tech Co"
