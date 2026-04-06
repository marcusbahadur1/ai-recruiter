import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class JobBase(BaseModel):
    title: str
    title_variations: list[Any] | None = None
    job_type: str | None = None
    description: str | None = None
    required_skills: list[Any] | None = None
    experience_years: int | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    location: str | None = None
    location_variations: list[Any] | None = None
    work_type: Literal["onsite", "hybrid", "remote", "remote_global"] | None = None
    tech_stack: list[Any] | None = None
    team_size: int | None = None
    minimum_score: int = 6
    hiring_manager_email: str | None = None
    hiring_manager_name: str | None = None
    evaluation_prompt: str | None = None
    outreach_email_prompt: str | None = None
    interview_questions_count: int = 5
    custom_interview_questions: list[Any] | None = None
    ai_recruiter_config: dict[str, Any] | None = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: str | None = None
    title_variations: list[Any] | None = None
    job_type: str | None = None
    description: str | None = None
    required_skills: list[Any] | None = None
    experience_years: int | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    location: str | None = None
    location_variations: list[Any] | None = None
    work_type: Literal["onsite", "hybrid", "remote", "remote_global"] | None = None
    tech_stack: list[Any] | None = None
    team_size: int | None = None
    minimum_score: int | None = None
    hiring_manager_email: str | None = None
    hiring_manager_name: str | None = None
    evaluation_prompt: str | None = None
    outreach_email_prompt: str | None = None
    interview_questions_count: int | None = None
    custom_interview_questions: list[Any] | None = None
    ai_recruiter_config: dict[str, Any] | None = None
    status: Literal["draft", "active", "paused", "closed"] | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    job_ref: str
    title: str
    title_variations: list[Any] | None
    job_type: str | None
    description: str | None
    required_skills: list[Any] | None
    experience_years: int | None
    salary_min: Decimal | None
    salary_max: Decimal | None
    location: str | None
    location_variations: list[Any] | None
    work_type: Literal["onsite", "hybrid", "remote", "remote_global"] | None
    tech_stack: list[Any] | None
    team_size: int | None
    minimum_score: int
    hiring_manager_email: str | None
    hiring_manager_name: str | None
    evaluation_prompt: str | None
    outreach_email_prompt: str | None
    interview_questions_count: int
    custom_interview_questions: list[Any] | None
    ai_recruiter_config: dict[str, Any] | None
    status: Literal["draft", "active", "paused", "closed"]
    created_at: datetime
    updated_at: datetime
