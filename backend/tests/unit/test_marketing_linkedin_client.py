"""Unit tests for the LinkedIn marketing OAuth client."""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.services.marketing.linkedin_client import LinkedInClient
from tests.unit.conftest import mock_http


def test_personal_authorization_url_uses_oidc_profile_scopes(monkeypatch):
    monkeypatch.setattr("app.config.settings.linkedin_client_id", "client-id")
    monkeypatch.setattr(
        "app.config.settings.linkedin_redirect_uri",
        "https://airecruiterz-api.fly.dev/api/v1/marketing/accounts/linkedin/callback",
    )

    url = LinkedInClient().get_authorization_url("state value", "personal")

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.linkedin.com"
    assert params["client_id"] == ["client-id"]
    assert params["redirect_uri"] == [
        "https://airecruiterz-api.fly.dev/api/v1/marketing/accounts/linkedin/callback"
    ]
    assert params["state"] == ["state value"]
    assert params["scope"] == ["openid profile w_member_social"]


@pytest.mark.asyncio
async def test_get_personal_profile_uses_userinfo_oidc_claims():
    async with mock_http() as mock:
        route = mock.get("https://api.linkedin.com/v2/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "sub": "abc123",
                    "given_name": "Jane",
                    "family_name": "Doe",
                },
            )
        )

        profile = await LinkedInClient().get_personal_profile("access-token")

    assert profile == {
        "id": "abc123",
        "localizedFirstName": "Jane",
        "localizedLastName": "Doe",
    }
    assert route.calls.last.request.headers["Authorization"] == "Bearer access-token"
