"""Integration tests for /api/v1/super-admin routes."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.routers.super_admin import _get_super_admin
from tests.integration.conftest import make_db_mock


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_admin_tenant() -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.name = "Super Admin"
    t.slug = "super-admin"
    t._is_super_admin = True
    return t


def _make_full_tenant(**kwargs) -> MagicMock:
    """Mock tenant with all TenantResponse-required fields explicitly set."""
    t = MagicMock()
    t.id = kwargs.get("id", uuid.uuid4())
    t.name = kwargs.get("name", "Test Firm")
    t.slug = kwargs.get("slug", "test-firm")
    t.phone = None
    t.address = None
    t.main_contact_name = None
    t.main_contact_email = None
    t.email_inbox = "jobs@testfirm.com"
    t.email_inbox_host = None
    t.email_inbox_port = None
    t.email_inbox_user = None
    t.website_url = None
    t.stripe_customer_id = None
    t.stripe_subscription_id = None
    t.plan = kwargs.get("plan", "trial")
    t.credits_remaining = kwargs.get("credits_remaining", 10)
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
    t.jobs_email = None
    t.recruiter_system_prompt = None
    t.widget_primary_color = None
    t.widget_bot_name = None
    return t


@pytest_asyncio.fixture()
async def sa_client():
    """Client with _get_super_admin dependency overridden."""
    admin = _make_admin_tenant()
    mock_db = make_db_mock()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[_get_super_admin] = lambda: admin

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, mock_db, admin

    app.dependency_overrides.clear()


# ── GET /super-admin/tenants ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tenants(sa_client):
    ac, mock_db, _ = sa_client
    tenant = _make_full_tenant()

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalars.return_value.all.return_value = [tenant]
        else:
            m.scalar_one.return_value = 1
        return m

    mock_db.execute = side_effect

    resp = await ac.get(
        "/api/v1/super-admin/tenants",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == tenant.name


@pytest.mark.asyncio
async def test_list_tenants_with_filters(sa_client):
    ac, mock_db, _ = sa_client

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalars.return_value.all.return_value = []
        else:
            m.scalar_one.return_value = 0
        return m

    mock_db.execute = side_effect

    resp = await ac.get(
        "/api/v1/super-admin/tenants?plan=free&is_active=true&search=test",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ── GET /super-admin/tenants/{id} ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tenant(sa_client):
    ac, mock_db, _ = sa_client
    tenant = _make_full_tenant()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = tenant
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await ac.get(
        f"/api/v1/super-admin/tenants/{tenant.id}",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == tenant.name


@pytest.mark.asyncio
async def test_get_tenant_not_found(sa_client):
    ac, mock_db, _ = sa_client

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await ac.get(
        f"/api/v1/super-admin/tenants/{uuid.uuid4()}",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 404


# ── PATCH /super-admin/tenants/{id} ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_tenant_plan(sa_client):
    ac, mock_db, _ = sa_client
    tenant = _make_full_tenant()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = tenant
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await ac.patch(
        f"/api/v1/super-admin/tenants/{tenant.id}",
        json={"plan": "agency_small", "is_active": True},
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_tenant_credits(sa_client):
    ac, mock_db, admin = sa_client
    tenant = _make_full_tenant(credits_remaining=5)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = tenant
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await ac.patch(
        f"/api/v1/super-admin/tenants/{tenant.id}",
        json={"credits_remaining": 50},
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_tenant_not_found(sa_client):
    ac, mock_db, _ = sa_client

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await ac.patch(
        f"/api/v1/super-admin/tenants/{uuid.uuid4()}",
        json={"plan": "recruiter"},
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 404


# ── POST /super-admin/impersonate/{id} ────────────────────────────────────────


@pytest.mark.asyncio
async def test_impersonate_tenant(sa_client):
    ac, mock_db, _ = sa_client
    target = _make_full_tenant()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = target
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch(
        "app.routers.super_admin._generate_impersonation_token",
        new=AsyncMock(return_value="impersonation_token_xyz"),
    ):
        resp = await ac.post(
            f"/api/v1/super-admin/impersonate/{target.id}",
            headers={"Authorization": "Bearer super_token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == str(target.id)
    assert data["tenant_name"] == target.name
    assert data["access_token"] == "impersonation_token_xyz"


@pytest.mark.asyncio
async def test_impersonate_tenant_not_found(sa_client):
    ac, mock_db, _ = sa_client

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await ac.post(
        f"/api/v1/super-admin/impersonate/{uuid.uuid4()}",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 404


# ── GET /super-admin/platform-keys ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_platform_keys(sa_client):
    ac, _, _ = sa_client

    resp = await ac.get(
        "/api/v1/super-admin/platform-keys",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # conftest.py sets ANTHROPIC_API_KEY, so this should be True
    assert data["has_anthropic_api_key"] is True
    assert "has_openai_api_key" in data
    assert "default_ai_provider" in data


# ── POST /super-admin/promo-codes ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_platform_promo_code(sa_client):
    ac, mock_db, _ = sa_client

    resp = await ac.post(
        "/api/v1/super-admin/promo-codes",
        json={
            "code": "SUMMER25",
            "type": "credits",
            "value": "10.00",
            "max_uses": 100,
            "is_active": True,
        },
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "SUMMER25"
    assert data["type"] == "credits"


@pytest.mark.asyncio
async def test_create_platform_promo_code_duplicate(sa_client):
    """DB unique constraint raises 409."""
    ac, mock_db, _ = sa_client

    # Make db.commit raise a unique constraint error
    mock_db.commit = AsyncMock(side_effect=Exception("unique constraint violated"))
    mock_db.rollback = AsyncMock()

    resp = await ac.post(
        "/api/v1/super-admin/promo-codes",
        json={
            "code": "DUPLICATE",
            "type": "discount_pct",
            "value": "20.00",
            "is_active": True,
        },
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 409


# ── GET /super-admin/health ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_system_health_celery_unavailable(sa_client):
    """Health endpoint returns 200 even when Celery/Redis is unreachable."""
    ac, _, _ = sa_client

    resp = await ac.get(
        "/api/v1/super-admin/health",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    # Connection fails in test env, so status is 'error'
    assert data["status"] in (
        "healthy",
        "no_workers",
        "unreachable",
        "error",
        "unknown",
    )
    assert "checked_at" in data


@pytest.mark.asyncio
async def test_system_health_celery_available(sa_client):
    """Health endpoint returns healthy status when Celery module is mocked via sys.modules."""
    import sys

    ac, _, _ = sa_client

    mock_ch = MagicMock()
    mock_ch.queue_declare.return_value = (None, 3, None)

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.channel.return_value.__enter__ = MagicMock(return_value=mock_ch)
    mock_conn.channel.return_value.__exit__ = MagicMock(return_value=False)

    mock_celery_app = MagicMock()
    mock_celery_app.connection_or_connect.return_value = mock_conn
    mock_celery_app.control.inspect.return_value.active.return_value = {
        "worker@host": []
    }
    mock_celery_app.control.inspect.return_value.reserved.return_value = {}

    mock_module = MagicMock()
    mock_module.celery_app = mock_celery_app

    with patch.dict(sys.modules, {"app.tasks.celery_app": mock_module}):
        resp = await ac.get(
            "/api/v1/super-admin/health",
            headers={"Authorization": "Bearer super_token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["celery_queue_depth"] == 3
    assert data["worker_count"] == 1


# ── GET /super-admin/audit ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_platform_audit_returns_events(sa_client):
    ac, mock_db, _ = sa_client

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalars.return_value.all.return_value = []
        else:
            m.scalar_one.return_value = 0
        return m

    mock_db.execute = side_effect

    resp = await ac.get(
        "/api/v1/super-admin/audit",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_platform_audit_category_filter(sa_client):
    ac, mock_db, _ = sa_client

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalars.return_value.all.return_value = []
        else:
            m.scalar_one.return_value = 0
        return m

    mock_db.execute = side_effect

    resp = await ac.get(
        "/api/v1/super-admin/audit?event_category=payment",
        headers={"Authorization": "Bearer super_token"},
    )
    assert resp.status_code == 200


# ── Auth guard for _get_super_admin ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_super_admin_requires_bearer_token():
    """Requests without super_admin auth are rejected."""

    app.dependency_overrides.pop(_get_super_admin, None)

    with patch("app.routers.super_admin.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "app_metadata": {"role": "recruiter", "tenant_id": str(uuid.uuid4())}
        }
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_httpx.AsyncClient.return_value = mock_client

        mock_db = make_db_mock()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get(
                "/api/v1/super-admin/tenants",
                headers={"Authorization": "Bearer regular_user_token"},
            )

    app.dependency_overrides.clear()
    assert resp.status_code == 403
