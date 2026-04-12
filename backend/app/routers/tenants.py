from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.rag_document import RagDocument
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.tenant import TenantResponse, TenantUpdate
from app.services.crypto import encrypt

router = APIRouter(prefix="/tenants", tags=["tenants"])

_ENCRYPTED_FIELDS = {
    "ai_api_key",
    "scrapingdog_api_key",
    "brightdata_api_key",
    "apollo_api_key",
    "hunter_api_key",
    "snov_api_key",
    "sendgrid_api_key",
    "email_inbox_password",
}


@router.get("/me", response_model=TenantResponse)
async def get_me(
    tenant: Tenant = Depends(get_current_tenant),
) -> TenantResponse:
    """Return the authenticated tenant's profile."""
    return TenantResponse.from_orm_with_flags(tenant)


class QuickStartStep(BaseModel):
    key: str
    title: str
    description: str
    completed: bool
    href: str


class QuickStartStatus(BaseModel):
    steps: list[QuickStartStep]
    completed_count: int
    total_count: int
    all_done: bool


@router.get("/me/quickstart-status", response_model=QuickStartStatus)
async def get_quickstart_status(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> QuickStartStatus:
    """Return completion status for each onboarding step."""
    has_ai_key = bool(tenant.ai_api_key)
    has_imap = bool(tenant.email_inbox_host and tenant.email_inbox_user and tenant.email_inbox_password)
    rag_count = await db.scalar(select(func.count()).select_from(RagDocument).where(RagDocument.tenant_id == tenant.id)) or 0
    job_count = await db.scalar(select(func.count()).select_from(Job).where(Job.tenant_id == tenant.id)) or 0
    candidate_count = await db.scalar(select(func.count()).select_from(Candidate).where(Candidate.tenant_id == tenant.id)) or 0

    steps = [
        QuickStartStep(
            key="account",
            title="Account created",
            description="You've signed up and logged in to AI Recruiter.",
            completed=True,
            href="/",
        ),
        QuickStartStep(
            key="api_keys",
            title="Add your API keys",
            description="Connect your OpenAI or Anthropic key so the AI pipeline can run.",
            completed=has_ai_key,
            href="/settings?section=apiKeys",
        ),
        QuickStartStep(
            key="email_inbox",
            title="Set up your email inbox",
            description="Configure your IMAP inbox so the Resume Screener can receive applications.",
            completed=has_imap,
            href="/settings?section=email",
        ),
        QuickStartStep(
            key="knowledge_base",
            title="Upload your knowledge base",
            description="Add your company website or documents so the AI knows about your business.",
            completed=rag_count > 0,
            href="/settings?section=knowledgeBase",
        ),
        QuickStartStep(
            key="first_job",
            title="Create your first job",
            description="Post a job via the AI Recruiter chat and choose your pipeline mode.",
            completed=job_count > 0,
            href="/chat",
        ),
        QuickStartStep(
            key="first_candidate",
            title="Get your first candidate",
            description="Activate the Talent Scout or wait for resume applications to arrive.",
            completed=candidate_count > 0,
            href="/jobs",
        ),
    ]

    completed_count = sum(1 for s in steps if s.completed)
    return QuickStartStatus(
        steps=steps,
        completed_count=completed_count,
        total_count=len(steps),
        all_done=completed_count == len(steps),
    )


@router.patch("/me", response_model=TenantResponse)
async def update_me(
    body: TenantUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """Update the authenticated tenant's profile.

    Sensitive fields (API keys, passwords) are encrypted with Fernet before storage.
    """
    update_data = body.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field in _ENCRYPTED_FIELDS and value:
            setattr(tenant, field, encrypt(value))
        else:
            setattr(tenant, field, value)

    await db.commit()

    return TenantResponse.from_orm_with_flags(tenant)
