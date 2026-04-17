"""Integration tests for /api/v1/candidates routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.integration.conftest import make_candidate, make_job

API = "/api/v1/candidates"


# ── GET /candidates ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_candidates_empty(client, mock_db, tenant_id):
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(API, headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_candidates_with_results(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    c = make_candidate(tenant_id, job_id)
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [c]
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(API, headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == c.name


@pytest.mark.asyncio
async def test_list_candidates_search_filter(client, mock_db, tenant_id):
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(
        f"{API}?search=Alice&status=discovered",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 200


# ── GET /candidates/{id} ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_candidate_returns_candidate(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    c = make_candidate(tenant_id, job_id)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = c
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(f"{API}/{c.id}", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    assert resp.json()["id"] == str(c.id)


@pytest.mark.asyncio
async def test_get_candidate_404(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(
        f"{API}/{uuid.uuid4()}", headers={"Authorization": "Bearer test"}
    )
    assert resp.status_code == 404


# ── PATCH /candidates/{id} ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_candidate_patches_status(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    c = make_candidate(tenant_id, job_id)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = c
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.patch(
        f"{API}/{c.id}",
        json={"status": "passed"},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert c.status == "passed"


# ── DELETE /candidates/{id} — GDPR erasure ────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_candidate_calls_anonymise(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    c = make_candidate(tenant_id, job_id)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = c
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch(
        "app.routers.candidates.anonymise_candidate", new_callable=AsyncMock
    ) as mock_anon:
        resp = await client.delete(
            f"{API}/{c.id}", headers={"Authorization": "Bearer test"}
        )

    assert resp.status_code == 204
    mock_anon.assert_awaited_once_with(mock_db, tenant_id, c.id)


@pytest.mark.asyncio
async def test_delete_candidate_404_for_unknown(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.delete(
        f"{API}/{uuid.uuid4()}", headers={"Authorization": "Bearer test"}
    )
    assert resp.status_code == 404


# ── POST /candidates/{id}/send-outreach ───────────────────────────────────────


@pytest.mark.asyncio
async def test_send_outreach_returns_200(client, mock_db, tenant_id, mock_tenant):
    job_id = uuid.uuid4()
    c = make_candidate(tenant_id, job_id, opted_out=False, email="alice@example.com")
    job = make_job(tenant_id, id=job_id)

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalar_one_or_none.return_value = c  # get_candidate_or_404
        elif call_count == 2:
            m.scalar_one_or_none.return_value = job  # get_job_for_candidate
        else:
            m.scalar_one_or_none.return_value = None
        return m

    mock_db.execute = side_effect

    with (
        patch("app.routers.candidates.AIProvider") as MockAI,
        patch(
            "app.routers.candidates.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("app.routers.candidates.AuditTrailService") as MockAudit,
    ):
        mock_ai = AsyncMock()
        mock_ai.complete = AsyncMock(return_value="Your personalised email text here.")
        MockAI.return_value = mock_ai

        mock_audit_instance = AsyncMock()
        mock_audit_instance.emit = AsyncMock()
        MockAudit.return_value = mock_audit_instance

        resp = await client.post(
            f"{API}/{c.id}/send-outreach",
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 200
    assert c.status == "emailed"


@pytest.mark.asyncio
async def test_send_outreach_rejects_opted_out(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    c = make_candidate(tenant_id, job_id, opted_out=True, email="alice@example.com")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = c
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.post(
        f"{API}/{c.id}/send-outreach",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_send_outreach_rejects_no_email(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    c = make_candidate(tenant_id, job_id, opted_out=False, email=None)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = c
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.post(
        f"{API}/{c.id}/send-outreach",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 422
