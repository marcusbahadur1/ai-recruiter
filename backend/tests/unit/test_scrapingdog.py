"""Unit tests for the ScrapingDog service."""

import httpx
import pytest

from app.services.scrapingdog import search_linkedin
from tests.unit.conftest import mock_http

_API_KEY = "dog-test-key"
_QUERY = '"Java Developer Melbourne site:linkedin.com/in/"'
_BASE_URL = "https://api.scrapingdog.com/google"


@pytest.mark.asyncio
async def test_search_linkedin_returns_normalised_results():
    async with mock_http() as mock:
        mock.get(_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "organic_results": [
                        {
                            "title": "Jane Doe - Java Developer | LinkedIn",
                            "snippet": "5 years Java experience",
                            "link": "https://www.linkedin.com/in/jane-doe",
                        },
                        {
                            "title": "Bob Smith - Software Engineer | LinkedIn",
                            "snippet": "Java, Spring Boot",
                            "link": "https://www.linkedin.com/in/bob-smith",
                        },
                    ]
                },
            )
        )
        results = await search_linkedin(query=_QUERY, start=0, api_key=_API_KEY)

    assert len(results) == 2
    assert results[0] == {
        "title": "Jane Doe - Java Developer | LinkedIn",
        "snippet": "5 years Java experience",
        "link": "https://www.linkedin.com/in/jane-doe",
    }


@pytest.mark.asyncio
async def test_search_linkedin_passes_correct_params():
    async with mock_http() as mock:
        route = mock.get(_BASE_URL).mock(
            return_value=httpx.Response(200, json={"organic_results": []})
        )
        await search_linkedin(query=_QUERY, start=20, api_key=_API_KEY)

    request = route.calls.last.request
    assert "start=20" in str(request.url)
    assert "results=10" in str(request.url)
    assert "advance_search=false" in str(request.url)


@pytest.mark.asyncio
async def test_search_linkedin_returns_empty_on_http_error():
    async with mock_http() as mock:
        mock.get(_BASE_URL).mock(
            return_value=httpx.Response(403, json={"error": "Forbidden"})
        )
        results = await search_linkedin(query=_QUERY, start=0, api_key=_API_KEY)

    assert results == []


@pytest.mark.asyncio
async def test_search_linkedin_skips_results_without_link():
    async with mock_http() as mock:
        mock.get(_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "organic_results": [
                        {"title": "No link result", "snippet": "snippet", "link": ""},
                        {
                            "title": "Has link",
                            "snippet": "s",
                            "link": "https://linkedin.com/in/x",
                        },
                    ]
                },
            )
        )
        results = await search_linkedin(query=_QUERY, start=0, api_key=_API_KEY)

    assert len(results) == 1
    assert results[0]["link"] == "https://linkedin.com/in/x"
