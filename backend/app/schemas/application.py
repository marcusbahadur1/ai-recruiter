import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ApplicationBase(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID | None = None
    applicant_name: str
    applicant_email: str
    resume_storage_path: str | None = None
    gdpr_consent_given: bool = True


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    screening_score: int | None = None
    screening_reasoning: str | None = None
    screening_status: Literal["pending", "passed", "failed"] | None = None
    test_status: (
        Literal[
            "not_started",
            "invited",
            "in_progress",
            "completed",
            "passed",
            "failed",
        ]
        | None
    ) = None
    test_score: int | None = None
    test_answers: list[Any] | dict[str, Any] | None = None
    interview_invited: bool | None = None
    interview_invited_at: datetime | None = None


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID | None
    applicant_name: str
    applicant_email: str
    # ── Pipeline status ───────────────────────────────────────────────────────
    status: str = "received"
    # ── Resume ────────────────────────────────────────────────────────────────
    resume_storage_path: str | None
    resume_filename: str | None
    resume_text: str | None
    # resume_embedding excluded — never serialise vector columns
    resume_score: int | None
    resume_reasoning: str | None
    resume_strengths: list[Any] | None
    resume_gaps: list[Any] | None
    # ── Legacy screening fields (kept for backward compat) ────────────────────
    screening_score: int | None
    screening_reasoning: str | None
    screening_status: Literal["pending", "passed", "failed"]
    # ── Test ──────────────────────────────────────────────────────────────────
    test_status: Literal[
        "not_started",
        "invited",
        "in_progress",
        "completed",
        "passed",
        "failed",
    ]
    test_score: int | None
    test_answers: list[Any] | dict[str, Any] | None
    test_evaluation: list[Any] | dict[str, Any] | None
    test_completed_at: datetime | None
    # ── Interview ─────────────────────────────────────────────────────────────
    interview_invited: bool
    interview_invited_at: datetime | None
    email_message_id: str | None
    gdpr_consent_given: bool
    received_at: datetime | None
    created_at: datetime
    # ── Recording (from TestSession) ──────────────────────────────────────────
    recording_urls: list[Any] | None = None
    transcripts: list[Any] | None = None
    interview_type: str | None = None
