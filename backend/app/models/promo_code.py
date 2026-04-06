import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL = platform-wide promo (available to all tenants)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(
        Enum("credits", "discount_pct", "full_access", name="promo_code_type_enum"),
        nullable=False,
    )
    value: Mapped[float] = mapped_column(Numeric, nullable=False)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int | None] = mapped_column(Integer)
    uses_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
