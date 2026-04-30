# AIRecruiterz — AI Marketing Module: Overview

*Full index: [marketing-module.md](marketing-module.md)*

> **How to use this plan:** Each phase maps to a focused Claude CLI session. Start a session
> with the provided prompt, then paste the numbered tasks as follow-up messages.
> Complete one phase before starting the next.

### Tech stack (from SPEC.md)
| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (async) |
| ORM | SQLAlchemy 2.x async (asyncpg driver) |
| Migrations | Alembic |
| Schemas | Pydantic v2 |
| Database | Supabase PostgreSQL 17 |
| Auth | Supabase Auth (JWT + RLS) |
| Tasks | Celery + Redis |
| Encryption | Fernet via `ENCRYPTION_KEY` env var (same pattern as tenant API key encryption) |
| AI | Anthropic Claude Sonnet via `services/ai_provider.py` facade |
| Email | SendGrid via `services/sendgrid_email.py` |
| Frontend | Next.js 16 TypeScript App Router (Fly.io) |
| i18n | Next.js built-in routing — `/[locale]/marketing` |
| Testing | pytest + pytest-asyncio + httpx + Playwright |

### Confirmed product decisions
| # | Decision | Answer |
|---|----------|--------|
| 1 | Platform LinkedIn account type | **Company page** (`urn:li:organization:{id}`) |
| 2 | Tenant LinkedIn account type | **Both** — personal profile OR company page, tenant's choice |
| 3 | Approval mode default | **`requires_approval = True`** for all accounts, toggleable off |
| 4 | Post images | **Unsplash API** stock photos + global settings toggle + per-post toggle |

### Implementation Order Summary

| Phase | Description | Est. Sessions |
|-------|-------------|--------------|
| 1 | Alembic Migrations | 1 |
| 2 | SQLAlchemy Models + Pydantic Schemas | 1 |
| 3 | LinkedIn OAuth Integration | 1–2 |
| 4 | Unsplash Image Integration | 1 |
| 5 | Content Generation Engine | 1 |
| 6 | Celery Tasks | 2 |
| 7 | FastAPI Routers | 2 |
| 8 | Frontend Tenant Dashboard | 3 |
| 9 | Super Admin Dashboard | 1–2 |
| 10 | Testing | 2 |
| 11 | Config & Deployment | 1 |

**Total estimated Claude CLI sessions: ~18–20**
