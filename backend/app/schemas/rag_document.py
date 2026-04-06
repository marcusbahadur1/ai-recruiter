import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RagDocumentBase(BaseModel):
    source_type: Literal["website_scrape", "manual_upload"]
    source_url: str | None = None
    filename: str | None = None
    content_text: str


class RagDocumentCreate(RagDocumentBase):
    pass


class RagDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    source_type: Literal["website_scrape", "manual_upload"]
    source_url: str | None
    filename: str | None
    content_text: str
    # embedding excluded — never serialise vector columns
    created_at: datetime
