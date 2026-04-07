"""Audit trail service — writes append-only events to job_audit_events.

Every pipeline step (Talent Scout, Resume Screener, payment, system) must emit
an event via AuditTrailService.emit().  The Postgres trigger defined in the
initial migration fires NOTIFY on the audit_{job_id} channel after each INSERT;
this module does NOT call NOTIFY directly.
"""

import uuid
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_audit_event import JobAuditEvent


class AuditTrailService:
    """Writes audit events for a specific tenant.

    Instantiate once per request/task and reuse across multiple emit() calls.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Owning tenant — injected here so callers never forget it.
    """

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id

    async def emit(
        self,
        *,
        job_id: uuid.UUID,
        event_type: str,
        event_category: Literal["talent_scout", "resume_screener", "payment", "system"],
        severity: Literal["info", "success", "warning", "error"] = "info",
        actor: Literal["system", "recruiter", "candidate", "hiring_manager"] = "system",
        summary: str,
        candidate_id: uuid.UUID | None = None,
        application_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        detail: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> JobAuditEvent:
        """Insert one audit event row.

        The Postgres trigger fires NOTIFY after the INSERT so SSE subscribers
        receive the event in real time.  Do NOT call NOTIFY from Python.

        Args:
            job_id: The job this event belongs to.
            event_type: Exact string from SPEC.md §15.2–15.4.
            event_category: Top-level grouping enum.
            severity: info | success | warning | error.
            actor: Who caused the event.
            summary: Human-readable one-liner (≤500 chars).
            candidate_id: Set for candidate-scoped events.
            application_id: Set for application-scoped events.
            actor_user_id: Set when a human user triggered the event.
            detail: Arbitrary structured payload (avoid raw PII — will be
                    redacted by GDPR erasure if candidate-linked).
            duration_ms: Wall-clock time of the external call, if applicable.

        Returns:
            The persisted JobAuditEvent instance.
        """
        event = JobAuditEvent(
            tenant_id=self._tenant_id,
            job_id=job_id,
            candidate_id=candidate_id,
            application_id=application_id,
            event_type=event_type,
            event_category=event_category,
            severity=severity,
            actor=actor,
            actor_user_id=actor_user_id,
            summary=summary,
            detail=detail,
            duration_ms=duration_ms,
        )
        # Do NOT open a new transaction — the caller owns the transaction and
        # will commit.  flush() assigns the PK so downstream code can reference
        # the event id before the commit happens.
        self._db.add(event)
        await self._db.flush()
        return event
