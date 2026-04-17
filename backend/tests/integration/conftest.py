"""Shared fixtures for integration tests.

Uses httpx.AsyncClient with the FastAPI ASGI app.  Both ``get_db`` and
``get_current_tenant`` are overridden so no live database or Supabase instance
is required.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.routers.auth import get_current_tenant


# ── Tenant fixture ─────────────────────────────────────────────────────────────


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture()
def mock_tenant(tenant_id):
    t = MagicMock()
    t.id = tenant_id
    t.name = "Test Firm"
    t.slug = "test-firm"
    t.is_active = True
    t.ai_provider = "anthropic"
    t.ai_api_key = None
    t.sendgrid_api_key = None
    t.email_inbox = "jobs-test@airecruiterz.com"
    t.jobs_email = None
    t.credits_remaining = 10
    t.plan = "trial"
    t.recruiter_system_prompt = None
    t.widget_primary_color = None
    t.widget_bot_name = None
    return t


# ── DB mock factory ────────────────────────────────────────────────────────────


def make_db_mock() -> AsyncMock:
    """Create an AsyncMock session with begin() context manager support."""
    session = AsyncMock()

    # begin() as async context manager
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)

    # flush() is a no-op by default
    session.flush = AsyncMock(return_value=None)

    # SQLAlchemy sync methods — must NOT be AsyncMock or the coroutine is never awaited
    session.add = MagicMock()
    session.delete = MagicMock()
    session.refresh = MagicMock()
    session.expire = MagicMock()
    session.expunge = MagicMock()

    return session


@pytest.fixture()
def mock_db():
    return make_db_mock()


# ── httpx client fixture ───────────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def client(mock_tenant, mock_db):
    """AsyncClient with get_current_tenant and get_db overridden."""

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_current_tenant] = lambda: mock_tenant
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Reusable model factories ───────────────────────────────────────────────────


def make_job(tenant_id: uuid.UUID, **kwargs) -> MagicMock:
    j = MagicMock()
    j.id = kwargs.get("id", uuid.uuid4())
    j.tenant_id = tenant_id
    j.job_ref = kwargs.get("job_ref", "TEST1234")
    j.title = kwargs.get("title", "Java Developer")
    j.title_variations = kwargs.get("title_variations", [])
    j.job_type = kwargs.get("job_type", "Software Engineer")
    j.description = kwargs.get("description", "A great job")
    j.required_skills = kwargs.get("required_skills", ["Java", "Spring"])
    j.experience_years = kwargs.get("experience_years", 5)
    j.salary_min = kwargs.get("salary_min", None)
    j.salary_max = kwargs.get("salary_max", None)
    j.location = kwargs.get("location", "Sydney")
    j.location_variations = kwargs.get("location_variations", [])
    j.work_type = kwargs.get("work_type", "hybrid")
    j.tech_stack = kwargs.get("tech_stack", [])
    j.team_size = kwargs.get("team_size", None)
    j.minimum_score = kwargs.get("minimum_score", 6)
    j.hiring_manager_email = kwargs.get("hiring_manager_email", "hm@firm.com")
    j.hiring_manager_name = kwargs.get("hiring_manager_name", "Jane Smith")
    j.evaluation_prompt = kwargs.get("evaluation_prompt", None)
    j.outreach_email_prompt = kwargs.get("outreach_email_prompt", None)
    j.interview_questions_count = kwargs.get("interview_questions_count", 5)
    j.custom_interview_questions = kwargs.get("custom_interview_questions", None)
    j.ai_recruiter_config = kwargs.get("ai_recruiter_config", None)
    j.candidate_target = kwargs.get("candidate_target", 20)
    j.interview_type = kwargs.get("interview_type", "text")
    j.mode = kwargs.get("mode", "talent_scout")
    j.status = kwargs.get("status", "draft")
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    j.created_at = now
    j.updated_at = now
    return j


def make_candidate(tenant_id: uuid.UUID, job_id: uuid.UUID, **kwargs) -> MagicMock:
    c = MagicMock()
    c.id = kwargs.get("id", uuid.uuid4())
    c.tenant_id = tenant_id
    c.job_id = job_id
    c.name = kwargs.get("name", "Alice Example")
    c.title = kwargs.get("title", "Senior Engineer")
    c.snippet = kwargs.get("snippet", "LinkedIn snippet text")
    c.linkedin_url = kwargs.get("linkedin_url", "https://linkedin.com/in/alice")
    c.email = kwargs.get("email", "alice@example.com")
    c.email_source = kwargs.get("email_source", "apollo")
    c.company = kwargs.get("company", "Acme Corp")
    c.location = kwargs.get("location", "Sydney")
    c.brightdata_profile = kwargs.get("brightdata_profile", {})
    c.suitability_score = kwargs.get("suitability_score", 8)
    c.score_reasoning = kwargs.get("score_reasoning", "Strong match")
    c.status = kwargs.get("status", "discovered")
    c.outreach_email_sent_at = None
    c.outreach_email_content = None
    c.gdpr_consent_given = False
    c.gdpr_consent_at = None
    c.opted_out = kwargs.get("opted_out", False)
    from datetime import datetime, timezone

    c.created_at = datetime.now(timezone.utc)
    return c


def make_application(tenant_id: uuid.UUID, job_id: uuid.UUID, **kwargs) -> MagicMock:
    a = MagicMock()
    a.id = kwargs.get("id", uuid.uuid4())
    a.tenant_id = tenant_id
    a.job_id = job_id
    a.candidate_id = kwargs.get("candidate_id", None)
    a.applicant_name = kwargs.get("applicant_name", "Bob Applicant")
    a.applicant_email = kwargs.get("applicant_email", "bob@example.com")
    # Pipeline status
    a.status = kwargs.get("status", "received")
    # Resume
    a.resume_storage_path = kwargs.get("resume_storage_path", None)
    a.resume_filename = kwargs.get("resume_filename", None)
    a.resume_text = kwargs.get("resume_text", "Resume text here")
    a.resume_score = kwargs.get("resume_score", None)
    a.resume_reasoning = kwargs.get("resume_reasoning", None)
    a.resume_strengths = kwargs.get("resume_strengths", None)
    a.resume_gaps = kwargs.get("resume_gaps", None)
    # Legacy screening
    a.screening_score = kwargs.get("screening_score", 7)
    a.screening_reasoning = kwargs.get("screening_reasoning", "Good fit")
    a.screening_status = kwargs.get("screening_status", "pending")
    # Test
    a.test_status = kwargs.get("test_status", "not_started")
    a.test_score = kwargs.get("test_score", None)
    a.test_answers = kwargs.get("test_answers", None)
    a.test_evaluation = kwargs.get("test_evaluation", None)
    a.test_completed_at = kwargs.get("test_completed_at", None)
    # Interview
    a.interview_invited = kwargs.get("interview_invited", False)
    a.interview_invited_at = kwargs.get("interview_invited_at", None)
    a.email_message_id = kwargs.get("email_message_id", None)
    a.interview_type = kwargs.get("interview_type", None)
    a.gdpr_consent_given = True
    from datetime import datetime, timezone

    a.received_at = datetime.now(timezone.utc)
    a.created_at = datetime.now(timezone.utc)
    return a
