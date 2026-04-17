import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobAuditEvent(Base):
    """
    Append-only audit log for every pipeline step.

    Rules (enforced in application code AND by DB convention):
    - No UPDATE or DELETE ever issued against this table.
    - GDPR erasure: redact PII within `detail` JSONB in-place (set fields to '[REDACTED]').
    - A Postgres trigger fires NOTIFY audit_{job_id} after every INSERT so SSE can deliver
      events in real time. The channel name uses underscores (hyphens replaced).
    """

    __tablename__ = "job_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
    )

    # ── Event classification ──────────────────────────────────────────────────
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    event_category: Mapped[str] = mapped_column(
        Enum(
            "talent_scout",
            "resume_screener",
            "payment",
            "system",
            name="audit_event_category_enum",
        ),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        Enum("info", "success", "warning", "error", name="audit_severity_enum"),
        nullable=False,
        default="info",
    )
    actor: Mapped[str] = mapped_column(
        Enum(
            "system",
            "recruiter",
            "candidate",
            "hiring_manager",
            name="audit_actor_enum",
        ),
        nullable=False,
        default="system",
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # ── Payload ───────────────────────────────────────────────────────────────
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # ── Timestamp — IMMUTABLE, never updated ──────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        # Fast time-range queries on the audit feed
        Index("ix_job_audit_events_created_at", "created_at"),
        # Efficient tenant-scoped listing (already covered by FK index, explicit for clarity)
        Index("ix_job_audit_events_tenant_id", "tenant_id"),
    )
