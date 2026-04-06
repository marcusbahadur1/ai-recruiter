"""Unit tests for the Snov.io service."""

import json

import httpx
import pytest

from app.services.snov import _EMAILS_URL, find_email
from tests.unit.conftest import mock_http

_API_KEY = "snov-test-key"


@pytest.mark.asyncio
async def test_find_email_returns_first_email():
    async with mock_http() as mock:
        mock.post(_EMAILS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "emails": [
                        {"email": "jane.doe@acme.com", "type": "professional"},
                        {"email": "jdoe@acme.com", "type": "professional"},
                    ]
                },
            )
        )
        result = await find_email(
            first_name="Jane", last_name="Doe", domain="acme.com", api_key=_API_KEY
        )

    assert result == "jane.doe@acme.com"


@pytest.mark.asyncio
async def test_find_email_returns_none_when_no_emails():
    async with mock_http() as mock:
        mock.post(_EMAILS_URL).mock(
            return_value=httpx.Response(200, json={"emails": []})
        )
        result = await find_email(
            first_name="Jane", last_name="Doe", domain="acme.com", api_key=_API_KEY
        )

    assert result is None


@pytest.mark.asyncio
async def test_find_email_returns_none_on_http_error():
    async with mock_http() as mock:
        mock.post(_EMAILS_URL).mock(
            return_value=httpx.Response(403, json={"error": "Forbidden"})
        )
        result = await find_email(
            first_name="Jane", last_name="Doe", domain="acme.com", api_key=_API_KEY
        )

    assert result is None


@pytest.mark.asyncio
async def test_find_email_sends_correct_payload():
    async with mock_http() as mock:
        route = mock.post(_EMAILS_URL).mock(
            return_value=httpx.Response(200, json={"emails": []})
        )
        await find_email(
            first_name="Alice", last_name="Jones", domain="corp.io", api_key=_API_KEY
        )

    payload = json.loads(route.calls.last.request.content)
    assert payload["firstName"] == "Alice"
    assert payload["lastName"] == "Jones"
    assert payload["domain"] == "corp.io"
    assert payload["apiSecret"] == _API_KEY
