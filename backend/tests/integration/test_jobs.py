"""Integration tests for /api/v1/jobs routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.integration.conftest import make_job

API = "/api/v1/jobs"


# ── GET /jobs ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_jobs_returns_empty_list(client, mock_db, tenant_id):
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(API, headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_jobs_returns_jobs(client, mock_db, tenant_id):
    job = make_job(tenant_id)
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [job]
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(API, headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == job.title
    assert data["items"][0]["job_ref"] == job.job_ref


@pytest.mark.asyncio
async def test_list_jobs_pagination(client, mock_db, tenant_id):
    jobs = [make_job(tenant_id, title=f"Job {i}") for i in range(5)]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = jobs
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(f"{API}?limit=2&offset=0", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


# ── POST /jobs ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_job_returns_201(client, mock_db, tenant_id):
    job = make_job(tenant_id)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None  # job_ref uniqueness check would go here
    mock_db.execute = AsyncMock(return_value=result_mock)

    payload = {
        "title": "Java Developer",
        "job_type": "Software Engineer",
        "description": "We need a Java dev",
        "required_skills": ["Java", "Spring Boot"],
        "experience_years": 5,
        "location": "Sydney",
        "work_type": "hybrid",
        "minimum_score": 7,
    }

    with patch("app.routers.jobs.Job", return_value=job):
        resp = await client.post(
            API,
            json=payload,
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == job.title


@pytest.mark.asyncio
async def test_create_job_requires_title(client, mock_db):
    resp = await client.post(
        API,
        json={"job_type": "Engineer"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 422


# ── GET /jobs/{id} ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_returns_job(client, mock_db, tenant_id):
    job = make_job(tenant_id)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = job
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(f"{API}/{job.id}", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    assert resp.json()["id"] == str(job.id)


@pytest.mark.asyncio
async def test_get_job_returns_404_for_unknown(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(
        f"{API}/{uuid.uuid4()}", headers={"Authorization": "Bearer test"}
    )
    assert resp.status_code == 404


# ── PATCH /jobs/{id} ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_job_patches_fields(client, mock_db, tenant_id):
    job = make_job(tenant_id)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = job
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.patch(
        f"{API}/{job.id}",
        json={"status": "active", "minimum_score": 8},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    # Verify setattr was called on the job mock
    assert job.status == "active"
    assert job.minimum_score == 8


@pytest.mark.asyncio
async def test_update_job_404_when_not_found(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.patch(
        f"{API}/{uuid.uuid4()}",
        json={"status": "closed"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 404


# ── POST /jobs/{id}/trigger-scout ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trigger_scout_returns_202(client, mock_db, mock_tenant, tenant_id):
    job = make_job(tenant_id)
    audit_event = MagicMock()
    audit_event.id = uuid.uuid4()

    # First execute() → find job; second/third → audit inserts
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = job
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch("app.routers.jobs.AuditTrailService") as MockAudit:
        mock_audit_instance = AsyncMock()
        mock_audit_instance.emit = AsyncMock(return_value=audit_event)
        MockAudit.return_value = mock_audit_instance

        resp = await client.post(
            f"{API}/{job.id}/trigger-scout",
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["job_id"] == str(job.id)


@pytest.mark.asyncio
async def test_trigger_scout_requires_credits(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.credits_remaining = 0
    job = make_job(tenant_id)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = job
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.post(
        f"{API}/{job.id}/trigger-scout",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_trigger_scout_404_for_unknown_job(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.post(
        f"{API}/{uuid.uuid4()}/trigger-scout",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 404
