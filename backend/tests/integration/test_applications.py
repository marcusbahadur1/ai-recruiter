"""Integration tests for /api/v1/applications routes and public test/interview routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers.applications import _sign_interview_token, _sign_test_token
from tests.integration.conftest import make_application, make_job

API = "/api/v1/applications"


# ── GET /applications ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_applications_empty(client, mock_db, tenant_id):
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(API, headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_list_applications_with_job_filter(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    a = make_application(tenant_id, job_id)
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [a]
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(
        f"{API}?job_id={job_id}", headers={"Authorization": "Bearer test"}
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["applicant_email"] == a.applicant_email


# ── GET /applications/{id} ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_application_returns_application(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    a = make_application(tenant_id, job_id)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = a
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(f"{API}/{a.id}", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    assert resp.json()["id"] == str(a.id)


@pytest.mark.asyncio
async def test_get_application_returns_404(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(
        f"{API}/{uuid.uuid4()}", headers={"Authorization": "Bearer test"}
    )
    assert resp.status_code == 404


# ── POST /applications/{id}/trigger-test ──────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_test_returns_202(client, mock_db, tenant_id, mock_tenant):
    job_id = uuid.uuid4()
    a = make_application(
        tenant_id, job_id, screening_status="passed", test_status="not_started"
    )
    job = make_job(tenant_id, id=job_id)

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalar_one_or_none.return_value = a  # get_application_or_404
        elif call_count == 2:
            m.scalar_one_or_none.return_value = job  # get_job_or_404
        return m

    mock_db.execute = side_effect

    with (
        patch("app.routers.applications.AIProvider") as MockAI,
        patch(
            "app.routers.applications.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("app.routers.applications.AuditTrailService") as MockAudit,
    ):
        mock_ai_instance = AsyncMock()
        mock_ai_instance.complete = AsyncMock(
            return_value='["Question 1", "Question 2", "Question 3", "Question 4", "Question 5"]'
        )
        MockAI.return_value = mock_ai_instance

        mock_audit_instance = AsyncMock()
        mock_audit_instance.emit = AsyncMock()
        MockAudit.return_value = mock_audit_instance

        resp = await client.post(
            f"{API}/{a.id}/trigger-test",
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert "test_url" in data


@pytest.mark.asyncio
async def test_trigger_test_rejects_unscreened(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    a = make_application(tenant_id, job_id, screening_status="pending")
    job = make_job(tenant_id, id=job_id)

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        m.scalar_one_or_none.return_value = a if call_count == 1 else job
        return m

    mock_db.execute = side_effect

    resp = await client.post(
        f"{API}/{a.id}/trigger-test",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 409


# ── GET /test/{id}/{token} (public) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_test_returns_state(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    a = make_application(
        tenant_id,
        job_id,
        test_status="invited",
        test_answers={
            "questions": ["Q1?", "Q2?", "Q3?"],
            "answers": [],
            "conversation": [],
        },
    )
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = a
    mock_db.execute = AsyncMock(return_value=result_mock)

    token = _sign_test_token(a.id)
    resp = await client.get(f"/api/v1/test/{a.id}/{token}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["questions_total"] == 3
    assert data["questions_answered"] == 0
    assert data["next_question"] == "Q1?"


@pytest.mark.asyncio
async def test_get_test_invalid_token(client, mock_db):
    app_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/test/{app_id}/bad_token")
    assert resp.status_code == 400


# ── POST /test/{id}/message (public) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_test_message_records_answer(
    client, mock_db, tenant_id, mock_tenant
):
    job_id = uuid.uuid4()
    a = make_application(
        tenant_id,
        job_id,
        test_status="in_progress",
        test_answers={
            "questions": ["Q1?", "Q2?"],
            "current_question_idx": 0,
            "answers": [],
            "full_conversation": [],
        },
    )
    job = make_job(tenant_id, id=job_id)

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalar_one_or_none.return_value = a  # application
        elif call_count == 2:
            m.scalar_one_or_none.return_value = mock_tenant  # tenant
        else:
            m.scalar_one_or_none.return_value = job  # job
        return m

    mock_db.execute = side_effect

    token = _sign_test_token(a.id)
    with (
        patch("app.routers.applications.AIProvider") as MockAI,
        patch("app.routers.applications.AuditTrailService") as MockAudit,
    ):
        mock_ai_instance = AsyncMock()
        mock_ai_instance.complete_json = AsyncMock(
            return_value={
                "reply": "Thank you. Next question: Q2?",
                "answer_accepted": True,
                "test_complete": False,
            }
        )
        MockAI.return_value = mock_ai_instance
        mock_audit_instance = AsyncMock()
        mock_audit_instance.emit = AsyncMock()
        MockAudit.return_value = mock_audit_instance

        resp = await client.post(
            f"/api/v1/test/{a.id}/message",
            json={"token": token, "answer": "My answer to Q1"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answered"] == 1
    assert data["completed"] is False
    assert data["next_question"] == "Q2?"


@pytest.mark.asyncio
async def test_post_test_message_completes_test(
    client, mock_db, tenant_id, mock_tenant
):
    job_id = uuid.uuid4()
    a = make_application(
        tenant_id,
        job_id,
        test_status="in_progress",
        test_answers={
            "questions": ["Q1?"],
            "current_question_idx": 0,
            "answers": [],
            "full_conversation": [],
        },
    )
    job = make_job(tenant_id, id=job_id)

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalar_one_or_none.return_value = a
        elif call_count == 2:
            m.scalar_one_or_none.return_value = mock_tenant
        else:
            m.scalar_one_or_none.return_value = job
        return m

    mock_db.execute = side_effect

    token = _sign_test_token(a.id)
    with (
        patch("app.routers.applications.AIProvider") as MockAI,
        patch("app.routers.applications.AuditTrailService") as MockAudit,
        patch("app.tasks.screener_tasks.score_test") as MockScore,
    ):
        mock_ai_instance = AsyncMock()
        mock_ai_instance.complete_json = AsyncMock(
            return_value={
                "reply": "Great! Assessment complete.",
                "answer_accepted": True,
                "test_complete": True,
            }
        )
        MockAI.return_value = mock_ai_instance
        mock_audit_instance = AsyncMock()
        mock_audit_instance.emit = AsyncMock()
        MockAudit.return_value = mock_audit_instance

        resp = await client.post(
            f"/api/v1/test/{a.id}/message",
            json={"token": token, "answer": "My answer"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["completed"] is True
    assert data["next_question"] is None
    MockScore.delay.assert_called_once()


# ── GET /actions/invite-interview/{id}/{token} (public) ───────────────────────


@pytest.mark.asyncio
async def test_invite_interview_confirms_on_valid_token(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    a = make_application(tenant_id, job_id, interview_invited=False)
    job = make_job(tenant_id, id=job_id)
    mock_tenant = MagicMock()
    mock_tenant.id = tenant_id
    mock_tenant.sendgrid_api_key = None
    mock_tenant.email_inbox = "jobs-test@firm.com"

    call_count = 0

    async def side_effect(query, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            m.scalar_one_or_none.return_value = a  # application
        elif call_count == 2:
            m.scalar_one_or_none.return_value = job  # job
        elif call_count == 3:
            m.scalar_one_or_none.return_value = mock_tenant  # tenant
        return m

    mock_db.execute = side_effect

    token = _sign_interview_token(a.id)

    with (
        patch(
            "app.routers.applications.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("app.routers.applications.AuditTrailService") as MockAudit,
    ):
        mock_audit_instance = AsyncMock()
        mock_audit_instance.emit = AsyncMock()
        MockAudit.return_value = mock_audit_instance

        resp = await client.get(f"/api/v1/actions/invite-interview/{a.id}/{token}")

    assert resp.status_code == 200
    assert "Interview Invitation Sent" in resp.text
    assert a.interview_invited is True


@pytest.mark.asyncio
async def test_invite_interview_invalid_token(client, mock_db):
    app_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/actions/invite-interview/{app_id}/invalid_token")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_invite_interview_already_sent(client, mock_db, tenant_id):
    job_id = uuid.uuid4()
    a = make_application(tenant_id, job_id, interview_invited=True)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = a
    mock_db.execute = AsyncMock(return_value=result_mock)

    token = _sign_interview_token(a.id)
    resp = await client.get(f"/api/v1/actions/invite-interview/{a.id}/{token}")

    assert resp.status_code == 200
    assert "Already Sent" in resp.text
