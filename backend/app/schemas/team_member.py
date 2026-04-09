import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    name: str | None
    role: str
    status: str
    invited_at: datetime
    joined_at: datetime | None


class TeamInviteRequest(BaseModel):
    email: EmailStr
    name: str | None = None
    role: Literal["admin", "recruiter", "hiring_manager"] = "recruiter"
