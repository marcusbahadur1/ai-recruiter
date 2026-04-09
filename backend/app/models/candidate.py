import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

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

    # ── Identity ──────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str | None] = mapped_column(String(300))
    snippet: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(255))
    email_source: Mapped[str | None] = mapped_column(
        Enum("apollo", "hunter", "snov", "deduced", "manual", "unknown", name="email_source_enum")
    )
    company: Mapped[str | None] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(300))

    # ── Enrichment ────────────────────────────────────────────────────────────
    brightdata_profile: Mapped[dict | None] = mapped_column(JSONB)
    resume_embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    # ── Scoring ───────────────────────────────────────────────────────────────
    suitability_score: Mapped[int | None] = mapped_column(Integer)
    score_reasoning: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[list | None] = mapped_column(JSONB)
    gaps: Mapped[list | None] = mapped_column(JSONB)

    # ── Pipeline status ───────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum(
            "discovered",
            "profiled",
            "scored",
            "passed",
            "failed",
            "emailed",
            "applied",
            "tested",
            "interviewed",
            "rejected",
            name="candidate_status_enum",
        ),
        nullable=False,
        default="discovered",
    )

    # ── Outreach ──────────────────────────────────────────────────────────────
    outreach_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outreach_email_content: Mapped[str | None] = mapped_column(Text)

    # ── GDPR ──────────────────────────────────────────────────────────────────
    gdpr_consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gdpr_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates=None, lazy="raise")  # type: ignore[name-defined]
    job: Mapped["Job"] = relationship("Job", back_populates=None, lazy="raise")  # type: ignore[name-defined]
