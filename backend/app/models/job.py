import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Job identity ──────────────────────────────────────────────────────────
    job_ref: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_variations: Mapped[dict | list | None] = mapped_column(JSONB)
    job_type: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    # ── Requirements ──────────────────────────────────────────────────────────
    required_skills: Mapped[dict | list | None] = mapped_column(JSONB)
    experience_years: Mapped[int | None] = mapped_column(Integer)
    salary_min: Mapped[float | None] = mapped_column(Numeric)
    salary_max: Mapped[float | None] = mapped_column(Numeric)

    # ── Location ──────────────────────────────────────────────────────────────
    location: Mapped[str | None] = mapped_column(String(200))
    location_variations: Mapped[dict | list | None] = mapped_column(JSONB)
    work_type: Mapped[str | None] = mapped_column(
        Enum("onsite", "hybrid", "remote", "remote_global", name="work_type_enum")
    )

    # ── Additional detail ─────────────────────────────────────────────────────
    tech_stack: Mapped[dict | list | None] = mapped_column(JSONB)
    team_size: Mapped[int | None] = mapped_column(Integer)

    # ── Talent Scout configuration ────────────────────────────────────────────
    candidate_target: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # ── Hiring configuration ──────────────────────────────────────────────────
    minimum_score: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    hiring_manager_email: Mapped[str | None] = mapped_column(String(255))
    hiring_manager_name: Mapped[str | None] = mapped_column(String(200))
    evaluation_prompt: Mapped[str | None] = mapped_column(Text)
    outreach_email_prompt: Mapped[str | None] = mapped_column(Text)
    interview_questions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    custom_interview_questions: Mapped[dict | list | None] = mapped_column(JSONB)
    ai_recruiter_config: Mapped[dict | None] = mapped_column(JSONB)

    # ── Mode ─────────────────────────────────────────────────────────────────
    mode: Mapped[str] = mapped_column(String(50), nullable=False, default="talent_scout")

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum("draft", "active", "paused", "closed", name="job_status_enum"),
        nullable=False,
        default="draft",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates=None, lazy="raise")  # type: ignore[name-defined]
