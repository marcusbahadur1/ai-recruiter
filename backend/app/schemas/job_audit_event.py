import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class JobAuditEventCreate(BaseModel):
    """Used internally by the audit trail service — never accepted from external callers."""

    job_id: uuid.UUID
    candidate_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    event_type: str
    event_category: Literal["talent_scout", "resume_screener", "payment", "system"]
    severity: Literal["info", "success", "warning", "error"] = "info"
    actor: Literal["system", "recruiter", "candidate", "hiring_manager"] = "system"
    actor_user_id: uuid.UUID | None = None
    summary: str
    detail: dict[str, Any] | None = None
    duration_ms: int | None = None


class JobAuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID | None
    application_id: uuid.UUID | None
    event_type: str
    event_category: Literal["talent_scout", "resume_screener", "payment", "system"]
    severity: Literal["info", "success", "warning", "error"]
    actor: Literal["system", "recruiter", "candidate", "hiring_manager"]
    actor_user_id: uuid.UUID | None
    summary: str
    detail: dict[str, Any] | None
    duration_ms: int | None
    created_at: datetime
