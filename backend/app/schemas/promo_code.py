import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PromoCodeBase(BaseModel):
    code: str
    type: Literal["credits", "discount_pct", "full_access"]
    value: Decimal
    expires_at: datetime | None = None
    max_uses: int | None = None
    is_active: bool = True


class PromoCodeCreate(PromoCodeBase):
    # tenant_id omitted — NULL means platform-wide; set by super_admin service only
    pass


class PromoCodeUpdate(BaseModel):
    expires_at: datetime | None = None
    max_uses: int | None = None
    is_active: bool | None = None


class PromoCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    code: str
    type: Literal["credits", "discount_pct", "full_access"]
    value: Decimal
    expires_at: datetime | None
    max_uses: int | None
    uses_count: int
    is_active: bool
