#!/usr/bin/env python3
"""
Staging seed script — adds anonymised representative data to the staging DB.

Creates:
  - 1 staging recruiter login (pre-confirmed, no email required)
  - 2 active jobs (Talent Scout + Screener mode)
  - 10 candidates spread across pipeline stages
  - 5 applications in various screening/test states

Safe to run multiple times — all inserts are idempotent (skip if already exists).

Usage:
    cd backend && python scripts/seed_staging.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Must be on sys.path before app imports
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.tenant import Tenant
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
import app.models  # noqa: F401 — registers all mappers

DATABASE_URL       = os.environ["DATABASE_URL"]
SUPABASE_URL       = os.environ["SUPABASE_URL"]
SUPABASE_SVC_KEY   = os.environ["SUPABASE_SERVICE_KEY"]

# ── Staging login credentials ─────────────────────────────────────────────────
STAGING_EMAIL    = "staging@airecruiterz.com"
STAGING_PASSWORD = "StagingTest2026!"
STAGING_FIRM     = "Acme Recruitment (Staging)"
STAGING_SLUG     = "acme-staging"

# ── Database ──────────────────────────────────────────────────────────────────
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "apikey": SUPABASE_SVC_KEY,
        "Authorization": f"Bearer {SUPABASE_SVC_KEY}",
        "Content-Type": "application/json",
    }


def create_or_get_supabase_user(email: str, password: str) -> str:
    """Create a pre-confirmed Supabase auth user and return their ID."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            json={"email": email, "password": password, "email_confirm": True},
            headers=_headers(),
        )
        if resp.status_code in (200, 201):
            uid = resp.json()["id"]
            print(f"  ✓ Created Supabase user {email} (id={uid})")
            return uid

        # User already exists — look them up
        list_resp = client.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            params={"email": email},
            headers=_headers(),
        )
        users = list_resp.json().get("users", [])
        existing = next((u for u in users if u.get("email") == email), None)
        if existing:
            uid = existing["id"]
            print(f"  ✓ Supabase user already exists {email} (id={uid})")
            return uid

    raise RuntimeError(f"Failed to create/find Supabase user: {resp.status_code} {resp.text}")


def tag_supabase_user(user_id: str, tenant_id: str) -> None:
    with httpx.Client(timeout=15) as client:
        resp = client.put(
            f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            json={"app_metadata": {"tenant_id": tenant_id, "role": "admin"}},
            headers=_headers(),
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to tag user metadata: {resp.status_code} {resp.text}")
    print(f"  ✓ Tagged app_metadata → tenant_id={tenant_id}")


# ── Seed data definitions ─────────────────────────────────────────────────────

JOBS = [
    {
        "title": "Senior Python Engineer",
        "job_ref": "SEED-001",
        "job_type": "Software Engineering",
        "description": (
            "We're looking for a senior Python engineer to join our platform team. "
            "You'll work on high-throughput APIs, data pipelines, and internal tooling."
        ),
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
        "experience_years": 5,
        "salary_min": 130000,
        "salary_max": 160000,
        "location": "Sydney, NSW",
        "work_type": "hybrid",
        "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Redis", "AWS"],
        "minimum_score": 7,
        "hiring_manager_email": "hiring@acme-staging.example.com",
        "hiring_manager_name": "Alex Chen",
        "mode": "talent_scout",
        "interview_type": "text",
        "candidate_target": 20,
    },
    {
        "title": "Product Marketing Manager",
        "job_ref": "SEED-002",
        "job_type": "Marketing",
        "description": (
            "Drive go-to-market strategy for our SaaS products. "
            "You'll own positioning, messaging, and launch campaigns."
        ),
        "required_skills": ["Product Marketing", "B2B SaaS", "Copywriting", "Market Research"],
        "experience_years": 4,
        "salary_min": 110000,
        "salary_max": 140000,
        "location": "Melbourne, VIC",
        "work_type": "remote",
        "tech_stack": [],
        "minimum_score": 6,
        "hiring_manager_email": "hiring@acme-staging.example.com",
        "hiring_manager_name": "Sarah Mitchell",
        "mode": "screener",
        "interview_type": "text",
        "candidate_target": 15,
    },
]

# job_idx refers to index in JOBS list above
CANDIDATES = [
    {"name": "James O'Sullivan", "title": "Senior Software Engineer",     "company": "Atlassian",  "location": "Sydney, NSW",     "email": "j.osullivan@seed.example.com", "score": 9, "status": "emailed",     "job_idx": 0},
    {"name": "Priya Sharma",      "title": "Python Developer",             "company": "Canva",      "location": "Sydney, NSW",     "email": "p.sharma@seed.example.com",    "score": 8, "status": "applied",     "job_idx": 0},
    {"name": "Daniel Kwan",       "title": "Backend Engineer",             "company": "Atlassian",  "location": "Sydney, NSW",     "email": "d.kwan@seed.example.com",      "score": 7, "status": "tested",      "job_idx": 0},
    {"name": "Emma Walsh",        "title": "Platform Engineer",            "company": "Afterpay",   "location": "Melbourne, VIC",  "email": "e.walsh@seed.example.com",     "score": 6, "status": "scored",      "job_idx": 0},
    {"name": "Tom Baxter",        "title": "Software Engineer",            "company": "Xero",       "location": "Auckland, NZ",    "email": "t.baxter@seed.example.com",    "score": 4, "status": "failed",      "job_idx": 0},
    {"name": "Ananya Iyer",       "title": "Lead Developer",               "company": "REA Group",  "location": "Melbourne, VIC",  "email": "a.iyer@seed.example.com",      "score": 9, "status": "interviewed", "job_idx": 0},
    {"name": "Sophie Laurent",    "title": "Product Marketing Manager",    "company": "HubSpot",    "location": "Remote",          "email": "s.laurent@seed.example.com",   "score": 8, "status": "applied",     "job_idx": 1},
    {"name": "Marcus Webb",       "title": "Senior Marketing Manager",     "company": "Salesforce", "location": "Sydney, NSW",     "email": "m.webb@seed.example.com",      "score": 7, "status": "emailed",     "job_idx": 1},
    {"name": "Lena Fischer",      "title": "Growth Marketer",              "company": "Notion",     "location": "Remote",          "email": "l.fischer@seed.example.com",   "score": 6, "status": "scored",      "job_idx": 1},
    {"name": "Ryan Nguyen",       "title": "B2B Marketing Specialist",     "company": "Intercom",   "location": "Melbourne, VIC",  "email": "r.nguyen@seed.example.com",    "score": 5, "status": "discovered",  "job_idx": 1},
]

APPLICATIONS = [
    {
        "applicant_name": "James O'Sullivan", "applicant_email": "j.osullivan@seed.example.com",
        "status": "screened", "screening_status": "passed",  "resume_score": 88,
        "test_status": "invited",    "job_idx": 0,
    },
    {
        "applicant_name": "Priya Sharma", "applicant_email": "p.sharma@seed.example.com",
        "status": "received", "screening_status": "pending", "resume_score": None,
        "test_status": "not_started", "job_idx": 0,
    },
    {
        "applicant_name": "Sophie Laurent", "applicant_email": "s.laurent@seed.example.com",
        "status": "screened", "screening_status": "passed",  "resume_score": 82,
        "test_status": "completed",  "job_idx": 1,
    },
    {
        "applicant_name": "Marcus Webb", "applicant_email": "m.webb@seed.example.com",
        "status": "received", "screening_status": "pending", "resume_score": None,
        "test_status": "not_started", "job_idx": 1,
    },
    {
        "applicant_name": "Lena Fischer", "applicant_email": "l.fischer@seed.example.com",
        "status": "rejected", "screening_status": "failed",  "resume_score": 45,
        "test_status": "not_started", "job_idx": 1,
    },
]

RESUME_PLACEHOLDER = (
    "Anonymised seed data — curriculum vitae placeholder. "
    "This record was created by the staging seed script."
)


# ── Main seed logic ────────────────────────────────────────────────────────────

async def seed() -> None:
    now = datetime.now(timezone.utc)

    # 1. Supabase auth user
    print("\n── Supabase Auth ────────────────────────────────────────────")
    user_id = create_or_get_supabase_user(STAGING_EMAIL, STAGING_PASSWORD)

    async with AsyncSessionLocal() as db:

        # 2. Tenant
        print("\n── Tenant ───────────────────────────────────────────────────")
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == STAGING_SLUG))
        if tenant:
            print(f"  ✓ Tenant already exists: {tenant.name} (id={tenant.id})")
        else:
            tenant = Tenant(
                id=uuid.uuid4(),
                name=STAGING_FIRM,
                slug=STAGING_SLUG,
                user_id=uuid.UUID(user_id),
                email_inbox=f"jobs-{STAGING_SLUG}@airecruiterz.com",
                credits_remaining=50,
                plan="recruiter",
                trial_started_at=now,
                trial_ends_at=now + timedelta(days=14),
                main_contact_name="Staging Admin",
                main_contact_email=STAGING_EMAIL,
                is_active=True,
            )
            db.add(tenant)
            await db.flush()
            print(f"  ✓ Created tenant: {tenant.name} (id={tenant.id})")

        tag_supabase_user(user_id, str(tenant.id))

        # 3. Jobs
        print("\n── Jobs ─────────────────────────────────────────────────────")
        job_records: list[Job] = []
        for jd in JOBS:
            existing = await db.scalar(select(Job).where(Job.job_ref == jd["job_ref"]))
            if existing:
                job_records.append(existing)
                print(f"  ✓ Job already exists: {existing.title} ({jd['job_ref']})")
                continue
            job = Job(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                job_ref=jd["job_ref"],
                title=jd["title"],
                job_type=jd["job_type"],
                description=jd["description"],
                required_skills=jd["required_skills"],
                experience_years=jd["experience_years"],
                salary_min=jd["salary_min"],
                salary_max=jd["salary_max"],
                location=jd["location"],
                work_type=jd["work_type"],
                tech_stack=jd["tech_stack"],
                minimum_score=jd["minimum_score"],
                hiring_manager_email=jd["hiring_manager_email"],
                hiring_manager_name=jd["hiring_manager_name"],
                mode=jd["mode"],
                interview_type=jd["interview_type"],
                candidate_target=jd["candidate_target"],
                status="active",
            )
            db.add(job)
            await db.flush()
            job_records.append(job)
            print(f"  ✓ Created job: {job.title} ({jd['job_ref']})")

        # 4. Candidates
        print("\n── Candidates ───────────────────────────────────────────────")
        candidate_by_email: dict[str, Candidate] = {}
        for cd in CANDIDATES:
            job = job_records[cd["job_idx"]]
            existing = await db.scalar(
                select(Candidate).where(
                    Candidate.email == cd["email"],
                    Candidate.tenant_id == tenant.id,
                )
            )
            if existing:
                candidate_by_email[cd["email"]] = existing
                print(f"  ✓ Candidate already exists: {cd['name']}")
                continue
            candidate = Candidate(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                job_id=job.id,
                name=cd["name"],
                title=cd["title"],
                company=cd["company"],
                location=cd["location"],
                email=cd["email"],
                email_source="apollo",
                suitability_score=cd["score"],
                score_reasoning=(
                    f"Strong match based on {cd['title']} experience at {cd['company']}. "
                    "Anonymised seed record."
                ),
                strengths=["Relevant domain experience", "Strong technical background"],
                gaps=["Could benefit from more senior leadership exposure"],
                status=cd["status"],
                gdpr_consent_given=True,
            )
            db.add(candidate)
            await db.flush()
            candidate_by_email[cd["email"]] = candidate
            print(f"  ✓ Created candidate: {cd['name']} [{cd['status']}]")

        # 5. Applications
        print("\n── Applications ─────────────────────────────────────────────")
        for ap in APPLICATIONS:
            job = job_records[ap["job_idx"]]
            existing = await db.scalar(
                select(Application).where(
                    Application.applicant_email == ap["applicant_email"],
                    Application.job_id == job.id,
                )
            )
            if existing:
                print(f"  ✓ Application already exists: {ap['applicant_name']}")
                continue
            linked = candidate_by_email.get(ap["applicant_email"])
            application = Application(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                job_id=job.id,
                candidate_id=linked.id if linked else None,
                applicant_name=ap["applicant_name"],
                applicant_email=ap["applicant_email"],
                status=ap["status"],
                screening_status=ap["screening_status"],
                resume_score=ap["resume_score"],
                test_status=ap["test_status"],
                resume_text=RESUME_PLACEHOLDER,
                resume_filename="cv_seed_anonymised.pdf",
                gdpr_consent_given=True,
                received_at=now,
            )
            db.add(application)
            await db.flush()
            print(f"  ✓ Created application: {ap['applicant_name']} [{ap['status']}]")

        await db.commit()

    await engine.dispose()

    print("\n── Complete ─────────────────────────────────────────────────")
    print(f"  Staging login →  {STAGING_EMAIL}  /  {STAGING_PASSWORD}")
    print(f"  Plan: recruiter  |  Credits: 50")
    print(f"  Jobs: {len(JOBS)}  |  Candidates: {len(CANDIDATES)}  |  Applications: {len(APPLICATIONS)}")


if __name__ == "__main__":
    asyncio.run(seed())
