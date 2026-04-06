"""Unit tests for the GDPR anonymise_candidate service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.gdpr import _redact_dict, anonymise_candidate


# ── _redact_dict ──────────────────────────────────────────────────────────────

def test_redact_dict_replaces_known_pii_keys():
    detail = {
        "name": "Alice Example",
        "email": "alice@example.com",
        "linkedin_url": "https://linkedin.com/in/alice",
        "score": 8,
        "reasoning": "Strong match",
    }
    result = _redact_dict(detail)

    assert result["name"] == "[REDACTED]"
    assert result["email"] == "[REDACTED]"
    assert result["linkedin_url"] == "[REDACTED]"
    # Non-PII fields preserved
    assert result["score"] == 8
    assert result["reasoning"] == "Strong match"


def test_redact_dict_handles_nested():
    detail = {
        "candidate": {
            "name": "Bob",
            "email": "bob@test.com",
            "skills": ["Java", "Python"],
        },
        "job_ref": "ABC123",
    }
    result = _redact_dict(detail)

    assert result["candidate"]["name"] == "[REDACTED]"
    assert result["candidate"]["email"] == "[REDACTED]"
    assert result["candidate"]["skills"] == ["Java", "Python"]
    assert result["job_ref"] == "ABC123"


def test_redact_dict_preserves_non_pii():
    detail = {"score": 9, "duration_ms": 500, "job_ref": "XYZ"}
    result = _redact_dict(detail)
    assert result == detail


def test_redact_dict_handles_empty():
    assert _redact_dict({}) == {}


# ── anonymise_candidate ───────────────────────────────────────────────────────

def _make_session() -> AsyncMock:
    session = AsyncMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)
    session.flush = AsyncMock(return_value=None)
    return session


def _make_candidate(tenant_id: uuid.UUID, job_id: uuid.UUID) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.tenant_id = tenant_id
    c.job_id = job_id
    c.name = "Alice Example"
    c.email = "alice@example.com"
    c.linkedin_url = "https://linkedin.com/in/alice"
    c.brightdata_profile = {"name": "Alice", "summary": "Senior dev"}
    c.resume_embedding = [0.1] * 1536
    return c


@pytest.mark.asyncio
async def test_anonymise_candidate_raises_if_not_found():
    db = _make_session()
    tenant_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="not found"):
        await anonymise_candidate(db, tenant_id, candidate_id)


@pytest.mark.asyncio
async def test_anonymise_candidate_issues_update_statements():
    db = _make_session()
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    candidate = _make_candidate(tenant_id, job_id)

    execute_calls = []

    async def side_effect(query, *args, **kwargs):
        execute_calls.append(query)
        m = MagicMock()
        # First call: find candidate
        if len(execute_calls) == 1:
            m.scalar_one_or_none.return_value = candidate
        # Audit events query (redact)
        elif len(execute_calls) == 3:
            m.scalars.return_value.all.return_value = []
        # Applications query
        elif len(execute_calls) == 4:
            m.scalars.return_value.all.return_value = []
        else:
            m.scalars.return_value.all.return_value = []
            m.scalar_one_or_none.return_value = None
        return m

    db.execute = side_effect

    with patch("app.services.gdpr.AuditTrailService") as MockAudit:
        mock_audit_instance = AsyncMock()
        mock_audit_instance.emit = AsyncMock()
        MockAudit.return_value = mock_audit_instance

        await anonymise_candidate(db, tenant_id, candidate.id)

    # Verify a GDPR erasure audit event was emitted
    mock_audit_instance.emit.assert_awaited_once()
    emit_kwargs = mock_audit_instance.emit.call_args.kwargs
    assert emit_kwargs["event_type"] == "system.gdpr_erasure"
    assert emit_kwargs["candidate_id"] == candidate.id


@pytest.mark.asyncio
async def test_anonymise_candidate_deletes_storage_for_resumes():
    db = _make_session()
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    candidate = _make_candidate(tenant_id, job_id)

    app = MagicMock()
    app.resume_storage_path = f"{tenant_id}/{job_id}/alice@example.com/resume.pdf"

    execute_calls = []

    async def side_effect(query, *args, **kwargs):
        execute_calls.append(query)
        m = MagicMock()
        if len(execute_calls) == 1:
            m.scalar_one_or_none.return_value = candidate
        elif len(execute_calls) == 3:
            m.scalars.return_value.all.return_value = []  # no audit events
        elif len(execute_calls) == 4:
            m.scalars.return_value.all.return_value = [app]  # one application with resume
        else:
            m.scalars.return_value.all.return_value = []
            m.scalar_one_or_none.return_value = None
        return m

    db.execute = side_effect

    with patch("app.services.gdpr._delete_supabase_file", new_callable=AsyncMock) as mock_delete, \
         patch("app.services.gdpr.AuditTrailService") as MockAudit:
        mock_audit_instance = AsyncMock()
        mock_audit_instance.emit = AsyncMock()
        MockAudit.return_value = mock_audit_instance

        await anonymise_candidate(db, tenant_id, candidate.id)

    mock_delete.assert_awaited_once_with(app.resume_storage_path)
