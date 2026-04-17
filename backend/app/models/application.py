import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Application(Base):
    __tablename__ = "applications"

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
    # Nullable — linked when a Scout candidate submits a resume
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
    )

    # ── Applicant ─────────────────────────────────────────────────────────────
    applicant_name: Mapped[str] = mapped_column(String(300), nullable=False)
    applicant_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Pipeline status ───────────────────────────────────────────────────────
    # Unified status tracking the full pipeline stage
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="received")

    # ── Resume ────────────────────────────────────────────────────────────────
    resume_storage_path: Mapped[str | None] = mapped_column(String(500))
    resume_filename: Mapped[str | None] = mapped_column(String(500))
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    # ── Screening ─────────────────────────────────────────────────────────────
    resume_score: Mapped[int | None] = mapped_column(Integer)
    resume_reasoning: Mapped[str | None] = mapped_column(Text)
    resume_strengths: Mapped[list | None] = mapped_column(JSONB)
    resume_gaps: Mapped[list | None] = mapped_column(JSONB)
    screening_score: Mapped[int | None] = mapped_column(Integer)
    screening_reasoning: Mapped[str | None] = mapped_column(Text)
    screening_status: Mapped[str] = mapped_column(
        Enum("pending", "passed", "failed", name="screening_status_enum"),
        nullable=False,
        default="pending",
    )

    # ── Competency test ───────────────────────────────────────────────────────
    test_status: Mapped[str] = mapped_column(
        Enum(
            "not_started",
            "invited",
            "in_progress",
            "completed",
            "passed",
            "failed",
            name="test_status_enum",
        ),
        nullable=False,
        default="not_started",
    )
    test_score: Mapped[int | None] = mapped_column(Integer)
    test_answers: Mapped[dict | list | None] = mapped_column(JSONB)
    test_evaluation: Mapped[dict | list | None] = mapped_column(JSONB)
    test_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Interview ─────────────────────────────────────────────────────────────
    interview_invited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    interview_invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    interview_invite_token: Mapped[str | None] = mapped_column(String(255))
    interview_invite_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # ── Email deduplication ───────────────────────────────────────────────────
    email_message_id: Mapped[str | None] = mapped_column(String(500), unique=True)

    # ── GDPR ──────────────────────────────────────────────────────────────────
    gdpr_consent_given: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates=None, lazy="raise")  # type: ignore[name-defined]  # noqa: F821
    job: Mapped["Job"] = relationship("Job", back_populates=None, lazy="raise")  # type: ignore[name-defined]  # noqa: F821
    candidate: Mapped["Candidate | None"] = relationship(
        "Candidate", back_populates=None, lazy="raise"
    )  # type: ignore[name-defined]  # noqa: F821
