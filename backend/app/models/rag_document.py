import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        Enum("website_scrape", "manual_upload", name="rag_source_type_enum"),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(String(500))
    filename: Mapped[str | None] = mapped_column(String(300))
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates=None, lazy="raise")  # type: ignore[name-defined]  # noqa: F821
