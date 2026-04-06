import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class CandidateBase(BaseModel):
    name: str
    title: str | None = None
    snippet: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    email_source: (
        Literal["apollo", "hunter", "snov", "deduced", "manual", "unknown"] | None
    ) = None
    company: str | None = None
    location: str | None = None


class CandidateCreate(CandidateBase):
    job_id: uuid.UUID


class CandidateUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    snippet: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    email_source: (
        Literal["apollo", "hunter", "snov", "deduced", "manual", "unknown"] | None
    ) = None
    company: str | None = None
    location: str | None = None
    suitability_score: int | None = None
    score_reasoning: str | None = None
    status: (
        Literal[
            "discovered",
            "profiled",
            "scored",
            "passed",
            "failed",
            "emailed",
            "applied",
            "tested",
            "interviewed",
            "rejected",
        ]
        | None
    ) = None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    job_id: uuid.UUID
    name: str
    title: str | None
    snippet: str | None
    linkedin_url: str | None
    email: str | None
    email_source: Literal["apollo", "hunter", "snov", "deduced", "manual", "unknown"] | None
    company: str | None
    location: str | None
    brightdata_profile: dict[str, Any] | None
    # resume_embedding excluded — never serialise vector columns
    suitability_score: int | None
    score_reasoning: str | None
    status: Literal[
        "discovered",
        "profiled",
        "scored",
        "passed",
        "failed",
        "emailed",
        "applied",
        "tested",
        "interviewed",
        "rejected",
    ]
    outreach_email_sent_at: datetime | None
    outreach_email_content: str | None
    gdpr_consent_given: bool
    gdpr_consent_at: datetime | None
    opted_out: bool
    created_at: datetime
