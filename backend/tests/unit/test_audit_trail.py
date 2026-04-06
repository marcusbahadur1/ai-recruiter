"""Unit tests for the AuditTrailService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.audit_trail import AuditTrailService


def _make_session() -> AsyncMock:
    session = AsyncMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)
    session.flush = AsyncMock(return_value=None)
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_emit_adds_event_to_session():
    db = _make_session()
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    service = AuditTrailService(db, tenant_id)

    event = await service.emit(
        job_id=job_id,
        event_type="scout.candidate_discovered",
        event_category="talent_scout",
        severity="info",
        actor="system",
        summary="Discovered Alice Example",
        detail={"linkedin_url": "https://linkedin.com/in/alice"},
    )

    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    assert event.tenant_id == tenant_id
    assert event.job_id == job_id
    assert event.event_type == "scout.candidate_discovered"
    assert event.severity == "info"
    assert event.actor == "system"


@pytest.mark.asyncio
async def test_emit_with_optional_fields():
    db = _make_session()
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    application_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    service = AuditTrailService(db, tenant_id)

    event = await service.emit(
        job_id=job_id,
        event_type="screener.screening_passed",
        event_category="resume_screener",
        severity="success",
        actor="system",
        summary="Scored 8/10 — passed",
        candidate_id=candidate_id,
        application_id=application_id,
        actor_user_id=actor_user_id,
        detail={"score": 8, "reasoning": "Strong match"},
        duration_ms=1234,
    )

    assert event.candidate_id == candidate_id
    assert event.application_id == application_id
    assert event.actor_user_id == actor_user_id
    assert event.duration_ms == 1234
    assert event.detail == {"score": 8, "reasoning": "Strong match"}


@pytest.mark.asyncio
async def test_emit_defaults_severity_to_info():
    db = _make_session()
    service = AuditTrailService(db, uuid.uuid4())

    event = await service.emit(
        job_id=uuid.uuid4(),
        event_type="system.task_retry",
        event_category="system",
        actor="system",
        summary="Retrying task",
    )

    assert event.severity == "info"


@pytest.mark.asyncio
async def test_emit_scout_job_started_event():
    """Verify the exact event_type string matches SPEC.md §15.2."""
    db = _make_session()
    tenant_id = uuid.uuid4()
    service = AuditTrailService(db, tenant_id)

    event = await service.emit(
        job_id=uuid.uuid4(),
        event_type="scout.job_started",
        event_category="talent_scout",
        severity="info",
        actor="recruiter",
        summary="Talent Scout started for job 'Java Developer'",
    )

    assert event.event_type == "scout.job_started"
    assert event.event_category == "talent_scout"


@pytest.mark.asyncio
async def test_emit_payment_credit_charged():
    """Verify payment event type from SPEC.md §15.4."""
    db = _make_session()
    service = AuditTrailService(db, uuid.uuid4())

    event = await service.emit(
        job_id=uuid.uuid4(),
        event_type="payment.credit_charged",
        event_category="payment",
        severity="info",
        actor="system",
        summary="Credit deducted for job search",
        detail={"credits_remaining": 9},
    )

    assert event.event_type == "payment.credit_charged"
    assert event.event_category == "payment"


@pytest.mark.asyncio
async def test_emit_system_gdpr_erasure():
    """Verify system event type from SPEC.md §15.4."""
    db = _make_session()
    service = AuditTrailService(db, uuid.uuid4())

    event = await service.emit(
        job_id=uuid.uuid4(),
        event_type="system.gdpr_erasure",
        event_category="system",
        severity="info",
        actor="recruiter",
        summary="Candidate PII anonymised",
    )

    assert event.event_type == "system.gdpr_erasure"
