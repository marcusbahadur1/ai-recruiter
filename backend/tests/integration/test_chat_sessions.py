"""Integration tests for the /api/v1/chat-sessions routes.

Tests exercise:
- GET /current — returns existing session or creates new one
- POST /new — always creates a fresh session
- POST /{id}/message — AI turn in each phase

Mock strategy:
- get_current_tenant dependency → mock_tenant (from conftest)
- DB session → mock_db (from conftest)
- AIProvider → deterministic responses
- _get_user_id dependency → fixed UUID
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.integration.conftest import make_db_mock

API = "/api/v1/chat-sessions"

_USER_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
_SESSION_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_session(tenant_id: uuid.UUID, phase: str = "job_collection", **kwargs) -> MagicMock:
    s = MagicMock()
    s.id = kwargs.get("id", _SESSION_ID)
    s.tenant_id = tenant_id
    s.user_id = _USER_ID
    s.job_id = kwargs.get("job_id", None)
    s.messages = kwargs.get("messages", [])
    s.phase = phase
    now = datetime.now(timezone.utc)
    s.created_at = now
    s.updated_at = now
    return s


# ── GET /current ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_current_returns_existing_session(client, mock_db, tenant_id):
    """Returns existing job_collection session for the tenant/user."""
    session = _make_session(tenant_id, phase="job_collection")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = session
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch("app.routers.chat_sessions._get_user_id", return_value=_USER_ID):
        resp = await client.get(
            f"{API}/current", headers={"Authorization": "Bearer test"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(_SESSION_ID)
    assert data["phase"] == "job_collection"


@pytest.mark.asyncio
async def test_get_current_creates_session_if_none_exists(client, mock_db, tenant_id):
    """When no active session exists, creates a new job_collection session."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    new_session = _make_session(tenant_id, phase="job_collection")

    with patch("app.routers.chat_sessions._get_user_id", return_value=_USER_ID), \
         patch("app.routers.chat_sessions._create_session", new_callable=AsyncMock, return_value=new_session):
        resp = await client.get(
            f"{API}/current", headers={"Authorization": "Bearer test"}
        )

    assert resp.status_code == 200
    assert resp.json()["phase"] == "job_collection"


# ── POST /new ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_session_creates_fresh_session(client, mock_db, tenant_id):
    """POST /new always creates a new session, regardless of existing ones."""
    new_session = _make_session(tenant_id, phase="job_collection")

    with patch("app.routers.chat_sessions._get_user_id", return_value=_USER_ID), \
         patch("app.routers.chat_sessions._create_session", new_callable=AsyncMock, return_value=new_session):
        resp = await client.post(
            f"{API}/new", headers={"Authorization": "Bearer test"}
        )

    assert resp.status_code == 201
    assert resp.json()["phase"] == "job_collection"


# ── POST /{id}/message — job_collection phase ─────────────────────────────────

@pytest.mark.asyncio
async def test_send_message_job_collection_phase(client, mock_db, tenant_id, mock_tenant):
    """AI response in job_collection phase: parses JSON, returns message and job_fields."""
    session = _make_session(tenant_id, phase="job_collection", messages=[])
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = session
    mock_db.execute = AsyncMock(return_value=result_mock)

    ai_json = (
        '{"message": "Great! What is the job title?", '
        '"job_fields": {"title": null}, '
        '"current_step": 1, "ready_for_payment": false}'
    )

    with patch("app.routers.chat_sessions.AIProvider") as MockAI:
        mock_instance = AsyncMock()
        mock_instance.complete = AsyncMock(return_value=ai_json)
        MockAI.return_value = mock_instance

        resp = await client.post(
            f"{API}/{_SESSION_ID}/message",
            json={"message": "Hi, I want to post a new job."},
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Great! What is the job title?"
    assert data["phase"] == "job_collection"
    assert "session_id" in data


@pytest.mark.asyncio
async def test_send_message_transitions_to_payment(client, mock_db, tenant_id, mock_tenant):
    """When AI sets ready_for_payment=true, phase transitions to 'payment'."""
    session = _make_session(tenant_id, phase="job_collection", messages=[])
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = session
    mock_db.execute = AsyncMock(return_value=result_mock)

    ai_json = (
        '{"message": "All confirmed! Ready to proceed to payment.", '
        '"job_fields": {"title": "Python Developer"}, '
        '"current_step": 16, "ready_for_payment": true}'
    )

    with patch("app.routers.chat_sessions.AIProvider") as MockAI:
        mock_instance = AsyncMock()
        mock_instance.complete = AsyncMock(return_value=ai_json)
        MockAI.return_value = mock_instance

        resp = await client.post(
            f"{API}/{_SESSION_ID}/message",
            json={"message": "Yes, everything looks correct!"},
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == "payment"
    assert session.phase == "payment"


@pytest.mark.asyncio
async def test_send_message_payment_phase_confirms(client, mock_db, tenant_id, mock_tenant):
    """payment phase: AI confirms payment → phase transitions to 'recruitment'."""
    session = _make_session(tenant_id, phase="payment", messages=[])
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = session
    mock_db.execute = AsyncMock(return_value=result_mock)

    ai_json = (
        '{"message": "Payment confirmed! Your job is now live.", '
        '"promo_code": null, "payment_confirmed": true}'
    )

    with patch("app.routers.chat_sessions.AIProvider") as MockAI:
        mock_instance = AsyncMock()
        mock_instance.complete = AsyncMock(return_value=ai_json)
        MockAI.return_value = mock_instance

        resp = await client.post(
            f"{API}/{_SESSION_ID}/message",
            json={"message": "I've completed the payment."},
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == "recruitment"
    assert data["payment_confirmed"] is True


@pytest.mark.asyncio
async def test_send_message_recruitment_phase_plain_text(client, mock_db, tenant_id, mock_tenant):
    """recruitment phase: AI returns plain text — no JSON parsing needed."""
    session = _make_session(tenant_id, phase="recruitment", messages=[])
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = session
    mock_db.execute = AsyncMock(return_value=result_mock)

    ai_reply = "The Scout has found 12 candidates so far. 8 have been scored."

    with patch("app.routers.chat_sessions.AIProvider") as MockAI:
        mock_instance = AsyncMock()
        mock_instance.complete = AsyncMock(return_value=ai_reply)
        MockAI.return_value = mock_instance

        resp = await client.post(
            f"{API}/{_SESSION_ID}/message",
            json={"message": "How is the search going?"},
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == ai_reply
    assert data["phase"] == "recruitment"


@pytest.mark.asyncio
async def test_send_message_empty_body_returns_422(client, mock_db, tenant_id):
    """Empty message body returns 422."""
    resp = await client.post(
        f"{API}/{_SESSION_ID}/message",
        json={"message": ""},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_message_session_not_found_returns_404(client, mock_db, tenant_id):
    """Non-existent session returns 404."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.post(
        f"{API}/{uuid.uuid4()}/message",
        json={"message": "Hello"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_message_handles_non_json_ai_response(client, mock_db, tenant_id, mock_tenant):
    """job_collection phase: non-JSON AI response falls back to plain text."""
    session = _make_session(tenant_id, phase="job_collection", messages=[])
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = session
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch("app.routers.chat_sessions.AIProvider") as MockAI:
        mock_instance = AsyncMock()
        mock_instance.complete = AsyncMock(return_value="Hello! Tell me about the role.")
        MockAI.return_value = mock_instance

        resp = await client.post(
            f"{API}/{_SESSION_ID}/message",
            json={"message": "Start"},
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "Hello" in data["message"]
    assert data["phase"] == "job_collection"  # no transition since no JSON


# ── Test: conversation helper functions ───────────────────────────────────────

def test_maybe_summarise_short_conversation():
    """Short conversations are returned unchanged."""
    from app.routers.chat_sessions import _maybe_summarise

    messages = [{"role": "user", "content": f"msg {i}", "timestamp": "2026-01-01T00:00:00+00:00"}
                for i in range(5)]
    result = _maybe_summarise(messages)
    assert result == messages


def test_maybe_summarise_long_conversation():
    """Long conversations are summarised with a system message prepended."""
    from app.routers.chat_sessions import _maybe_summarise

    messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}",
         "timestamp": "2026-01-01T00:00:00+00:00"}
        for i in range(35)
    ]
    result = _maybe_summarise(messages)

    assert len(result) == 11  # 1 summary + 10 recent
    assert result[0]["role"] == "system"
    assert "omitted" in result[0]["content"]


def test_extract_json_from_padded_response():
    """_extract_json handles text surrounding a JSON object."""
    from app.routers.chat_sessions import _extract_json

    text = 'Here is my response: {"message": "hello", "ready_for_payment": false} done.'
    extracted = _extract_json(text)
    import json
    data = json.loads(extracted)
    assert data["message"] == "hello"


def test_parse_job_collection_transitions_to_payment():
    """_parse_job_collection returns new_phase='payment' when ready_for_payment=true."""
    from app.routers.chat_sessions import _parse_job_collection

    raw = '{"message": "All set!", "job_fields": {"title": "Engineer"}, "current_step": 16, "ready_for_payment": true}'
    reply, fields, new_phase, extras = _parse_job_collection(raw)

    assert reply == "All set!"
    assert new_phase == "payment"
    assert fields == {"title": "Engineer"}


def test_parse_payment_transitions_to_recruitment():
    """_parse_payment returns new_phase='recruitment' when payment_confirmed=true."""
    from app.routers.chat_sessions import _parse_payment

    raw = '{"message": "Payment done!", "payment_confirmed": true}'
    reply, fields, new_phase, extras = _parse_payment(raw)

    assert reply == "Payment done!"
    assert new_phase == "recruitment"
    assert extras["payment_confirmed"] is True


def test_format_history_for_ai():
    """_format_history_for_ai converts messages to a readable transcript."""
    from app.routers.chat_sessions import _format_history_for_ai

    messages = [
        {"role": "user", "content": "Hello", "timestamp": ""},
        {"role": "assistant", "content": "Hi there!", "timestamp": ""},
    ]
    result = _format_history_for_ai(messages)
    assert "Recruiter: Hello" in result
    assert "AI Recruiter: Hi there!" in result
