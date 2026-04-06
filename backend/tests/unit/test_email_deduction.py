"""Unit tests for EmailDeductionService."""

import asyncio
import time
from unittest.mock import patch

import httpx
import pytest

from app.services.email_deduction import (
    EmailDeductionService,
    _GOOGLE_SEARCH_URL,
    _email_candidates,
    _extract_domain,
    _is_social_domain,
)
from tests.unit.conftest import mock_http


# ── Helper functions ──────────────────────────────────────────────────────────

def test_email_candidates_generates_four_formats():
    results = _email_candidates("Jane", "Doe", "acme.com")
    assert "jane.doe@acme.com" in results
    assert "j.doe@acme.com" in results
    assert "jane@acme.com" in results
    assert "janedoe@acme.com" in results
    assert len(results) == 4


def test_extract_domain_strips_protocol_and_path():
    assert _extract_domain("https://www.acme.com/about") == "acme.com"
    assert _extract_domain("http://corp.io/page?x=1") == "corp.io"


def test_extract_domain_returns_none_for_invalid():
    assert _extract_domain("not-a-domain") is None


def test_is_social_domain_recognises_linkedin():
    assert _is_social_domain("linkedin.com") is True
    assert _is_social_domain("www.linkedin.com") is True


def test_is_social_domain_false_for_business():
    assert _is_social_domain("acme.com") is False


# ── Domain lookup and full flow ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_email_resolves_domain_and_verifies():
    service = EmailDeductionService(scrapingdog_api_key="dog-key")

    async with mock_http() as mock:
        mock.get(_GOOGLE_SEARCH_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "organic_results": [
                        {
                            "title": "Acme Corp",
                            "snippet": "Leading company",
                            "link": "https://acme.com/about",
                        }
                    ]
                },
            )
        )
        with patch("app.services.email_deduction._smtp_check", return_value=True):
            result = await service.find_email("Jane", "Doe", "Acme Corp")

    assert result == "jane.doe@acme.com"


@pytest.mark.asyncio
async def test_find_email_returns_none_when_no_domain_found():
    service = EmailDeductionService(scrapingdog_api_key="dog-key")

    async with mock_http() as mock:
        mock.get(_GOOGLE_SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"organic_results": []})
        )
        result = await service.find_email("Jane", "Doe", "Unknown Co")

    assert result is None


@pytest.mark.asyncio
async def test_find_email_returns_none_without_scrapingdog_key():
    service = EmailDeductionService(scrapingdog_api_key=None)
    result = await service.find_email("Jane", "Doe", "Acme Corp")
    assert result is None


@pytest.mark.asyncio
async def test_find_email_returns_none_when_all_smtp_fail():
    service = EmailDeductionService(scrapingdog_api_key="dog-key")

    async with mock_http() as mock:
        mock.get(_GOOGLE_SEARCH_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "organic_results": [
                        {"title": "Acme", "snippet": "", "link": "https://acme.com"}
                    ]
                },
            )
        )
        with patch("app.services.email_deduction._smtp_check", return_value=False):
            result = await service.find_email("Jane", "Doe", "Acme Corp")

    assert result is None


@pytest.mark.asyncio
async def test_find_email_skips_social_domains():
    service = EmailDeductionService(scrapingdog_api_key="dog-key")

    async with mock_http() as mock:
        mock.get(_GOOGLE_SEARCH_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "organic_results": [
                        {
                            "title": "Jane Doe LinkedIn",
                            "snippet": "Profile",
                            "link": "https://linkedin.com/in/jane",
                        }
                    ]
                },
            )
        )
        result = await service.find_email("Jane", "Doe", "Acme Corp")

    assert result is None


# ── Rate limiting ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limiter_allows_checks_when_window_expired():
    service = EmailDeductionService()
    domain = "ratelimit-test.com"

    # Populate with 5 timestamps all older than the 60s window
    now = time.monotonic()
    service._rate_timestamps[domain] = [now - 61] * 5

    # Should not block since all timestamps are outside the window
    await asyncio.wait_for(service._wait_for_rate_limit(domain), timeout=1.0)
    # After call, one fresh timestamp should be appended
    assert len(service._rate_timestamps[domain]) == 1


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_window_full():
    """With 5 recent timestamps and asyncio.sleep patched, sleep is called."""
    service = EmailDeductionService()
    domain = "blocked-domain.com"

    sleep_called = []

    async def fake_sleep(duration: float) -> None:
        sleep_called.append(duration)

    now = time.monotonic()
    service._rate_timestamps[domain] = [now - 10] * 5  # all within window

    with patch("app.services.email_deduction.asyncio.sleep", fake_sleep):
        await asyncio.wait_for(service._wait_for_rate_limit(domain), timeout=2.0)

    assert sleep_called, "asyncio.sleep should have been called due to rate limiting"
