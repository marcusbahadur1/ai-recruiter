import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Supabase Auth user — stored as UUID, not a FK since users live in auth.users
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Linked once the recruiter confirms and creates a job
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
    )

    # [{role: "user"|"assistant", content: "...", timestamp: "ISO8601"}]
    messages: Mapped[list | None] = mapped_column(JSONB, nullable=False, default=list)

    phase: Mapped[str] = mapped_column(
        Enum(
            "job_collection",
            "payment",
            "recruitment",
            "post_recruitment",
            name="chat_phase_enum",
        ),
        nullable=False,
        default="job_collection",
    )

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
    job: Mapped["Job | None"] = relationship("Job", back_populates=None, lazy="raise")  # type: ignore[name-defined]
