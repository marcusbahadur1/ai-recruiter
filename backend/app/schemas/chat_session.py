import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: str  # ISO 8601


class ChatSessionBase(BaseModel):
    user_id: uuid.UUID
    job_id: uuid.UUID | None = None
    messages: list[dict[str, Any]] = []
    phase: Literal[
        "job_collection", "payment", "recruitment", "post_recruitment"
    ] = "job_collection"


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSessionUpdate(BaseModel):
    job_id: uuid.UUID | None = None
    messages: list[dict[str, Any]] | None = None
    phase: (
        Literal["job_collection", "payment", "recruitment", "post_recruitment"] | None
    ) = None


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID | None
    messages: list[dict[str, Any]] | None
    phase: Literal["job_collection", "payment", "recruitment", "post_recruitment"]
    created_at: datetime
    updated_at: datetime


class ChatSessionListItem(BaseModel):
    """Lightweight session summary for the history list — no full messages payload."""

    id: uuid.UUID
    phase: Literal["job_collection", "payment", "recruitment", "post_recruitment"]
    job_id: uuid.UUID | None
    job_title: str | None = None
    preview: str = Field(description="First user message, truncated to 80 chars")
    message_count: int
    created_at: datetime
    updated_at: datetime
