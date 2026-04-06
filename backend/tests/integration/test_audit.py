"""Integration tests for /api/v1/jobs/{id}/audit-events and /super-admin/audit."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.routers.super_admin import _get_super_admin
from tests.integration.conftest import make_db_mock, make_job


@pytest_asyncio.fixture()
async def super_admin_client(mock_db):
    """Client fixture with super_admin dependency override."""
    async def override_get_db():
        yield mock_db

    async def mock_super_admin():
        t = MagicMock()
        t.id = uuid.uuid4()
        t._is_super_admin = True
        return t

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[_get_super_admin] = mock_super_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def forbidden_super_admin_client(mock_db):
    """Client fixture where super_admin check raises 403."""
    async def override_get_db():
        yield mock_db

    async def reject_super_admin():
        raise HTTPException(status_code=403, detail="super_admin role required")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[_get_super_admin] = reject_super_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def make_audit_event(tenant_id: uuid.UUID, job_id: uuid.UUID, **kwargs) -> MagicMock:
    e = MagicMock()
    e.id = kwargs.get("id", uuid.uuid4())
    e.tenant_id = tenant_id
    e.job_id = job_id
    e.candidate_id = kwargs.get("candidate_id", None)
    e.application_id = kwargs.get("application_id", None)
    e.event_type = kwargs.get("event_type", "scout.candidate_discovered")
    e.event_category = kwargs.get("event_category", "talent_scout")
    e.severity = kwargs.get("severity", "info")
    e.actor = kwargs.get("actor", "system")
    e.actor_user_id = None
    e.summary = kwargs.get("summary", "Test event")
    e.detail = kwargs.get("detail", {"key": "value"})
    e.duration_ms = None
    e.created_at = datetime.now(timezone.utc)
    return e


# ── GET /jobs/{id}/audit-events ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_audit_events_returns_history(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    job = make_job(tenant_id, id=job_id)
    event = make_audit_event(tenant_id, job_id)

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            # _verify_job_access
            m.scalar_one_or_none.return_value = job
        elif call_count == 2:
            # count query
            m.scalars.return_value.all.return_value = [event]
        else:
            # paginated query
            m.scalars.return_value.all.return_value = [event]
        return m

    mock_db.execute = side_effect

    resp = await client.get(
        f"/api/v1/jobs/{job_id}/audit-events",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["event_type"] == event.event_type


@pytest.mark.asyncio
async def test_list_audit_events_404_for_unknown_job(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(
        f"/api/v1/jobs/{uuid.uuid4()}/audit-events",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_audit_events_category_filter(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    job = make_job(tenant_id, id=job_id)
    event = make_audit_event(tenant_id, job_id, event_category="talent_scout")

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalar_one_or_none.return_value = job
        else:
            m.scalars.return_value.all.return_value = [event]
        return m

    mock_db.execute = side_effect

    resp = await client.get(
        f"/api/v1/jobs/{job_id}/audit-events?category=talent_scout",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["event_category"] == "talent_scout"


@pytest.mark.asyncio
async def test_list_audit_events_pagination(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    job = make_job(tenant_id, id=job_id)
    events = [make_audit_event(tenant_id, job_id) for _ in range(10)]

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalar_one_or_none.return_value = job
        elif call_count == 2:
            m.scalars.return_value.all.return_value = events  # total count
        else:
            m.scalars.return_value.all.return_value = events[:5]  # page
        return m

    mock_db.execute = side_effect

    resp = await client.get(
        f"/api/v1/jobs/{job_id}/audit-events?limit=5&offset=0",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert len(data["items"]) == 5
    assert data["limit"] == 5


# ── GET /super-admin/audit ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_super_admin_audit_requires_super_admin_role(forbidden_super_admin_client):
    """Requests without super_admin role should be rejected."""
    resp = await forbidden_super_admin_client.get(
        "/api/v1/super-admin/audit",
        headers={"Authorization": "Bearer regular_user_token"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_audit_returns_system_and_payment_events(
    super_admin_client, mock_db, tenant_id
):
    job_id = uuid.uuid4()
    system_event = make_audit_event(
        tenant_id, job_id,
        event_type="system.task_failed_permanent",
        event_category="system",
        severity="error",
    )
    payment_event = make_audit_event(
        tenant_id, job_id,
        event_type="payment.credit_charged",
        event_category="payment",
        severity="info",
    )

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            # paginated events query: result.scalars().all()
            m.scalars.return_value.all.return_value = [system_event, payment_event]
        else:
            # count query: count_result.scalar_one()
            m.scalar_one.return_value = 2
        return m

    mock_db.execute = side_effect

    resp = await super_admin_client.get(
        "/api/v1/super-admin/audit",
        headers={"Authorization": "Bearer super_admin_token"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    categories = {item["event_category"] for item in data["items"]}
    assert categories.issubset({"system", "payment"})
