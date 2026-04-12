"""Integration tests for /api/v1/tenants routes (GET /me, PATCH /me)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.integration.conftest import make_db_mock


def _make_tenant_for_response(tenant_id: uuid.UUID) -> MagicMock:
    """Create a mock tenant with all TenantResponse-required fields explicitly set."""
    t = MagicMock()
    t.id = tenant_id
    t.name = "Test Firm"
    t.slug = "test-firm"
    t.phone = None
    t.address = None
    t.main_contact_name = "Alice"
    t.main_contact_email = "alice@testfirm.com"
    t.email_inbox = "jobs-test@airecruiterz.com"
    t.email_inbox_host = None
    t.email_inbox_port = None
    t.email_inbox_user = None
    t.website_url = "https://testfirm.com"
    t.stripe_customer_id = None
    t.stripe_subscription_id = None
    t.plan = "individual"
    t.credits_remaining = 10
    t.ai_provider = "anthropic"
    t.search_provider = "brightdata"
    t.email_discovery_provider = "domain_deduction"
    t.ai_api_key = None
    t.scrapingdog_api_key = None
    t.brightdata_api_key = None
    t.apollo_api_key = None
    t.hunter_api_key = None
    t.snov_api_key = None
    t.sendgrid_api_key = None
    t.gdpr_dpa_signed_at = None
    t.is_active = True
    t.created_at = datetime.now(timezone.utc)
    return t


@pytest.mark.asyncio
async def test_get_me(client, tenant_id, mock_tenant, monkeypatch):
    """GET /tenants/me returns the authenticated tenant's profile."""
    # Patch mock_tenant to have all required TenantResponse fields
    full_tenant = _make_tenant_for_response(tenant_id)

    from app.database import get_db
    from app.main import app
    from app.routers.auth import get_current_tenant
    from httpx import ASGITransport, AsyncClient

    mock_db = make_db_mock()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_tenant] = lambda: full_tenant
    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(
            "/api/v1/tenants/me",
            headers={"Authorization": "Bearer test_token"},
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Firm"
    assert data["slug"] == "test-firm"
    assert data["plan"] == "individual"
    assert data["has_ai_api_key"] is False


@pytest.mark.asyncio
async def test_update_me():
    """PATCH /tenants/me updates tenant fields and returns updated profile."""
    tenant_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    full_tenant = _make_tenant_for_response(tenant_id)

    from app.database import get_db
    from app.main import app
    from app.routers.auth import get_current_tenant
    from httpx import ASGITransport, AsyncClient

    mock_db = make_db_mock()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_tenant] = lambda: full_tenant
    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.patch(
            "/api/v1/tenants/me",
            json={"name": "Updated Firm", "phone": "+61400000000"},
            headers={"Authorization": "Bearer test_token"},
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Firm"
