# AI Recruiter — Application Specification v3.0 — Index

Full spec split across 15 focused files.

| File | Description |
|---|---|
| [spec-overview-tenancy.md](spec-overview-tenancy.md) | §1–2: Application overview, product goals, hosting, tech stack, multi-tenancy |
| [spec-auth-billing.md](spec-auth-billing.md) | §3–4: Authentication, user roles, self-serve sign-up, Stripe billing, plans |
| [spec-data-models.md](spec-data-models.md) | §5: Core data models — Jobs, Candidates, Applications, Chat Sessions, RAG, Audit |
| [spec-chat-interface.md](spec-chat-interface.md) | §6: AI Recruiter chat interface, 16-step job creation flow, evaluation report |
| [spec-talent-scout.md](spec-talent-scout.md) | §7: AI Talent Scout — candidate discovery, enrichment, scoring, email, outreach |
| [spec-screener.md](spec-screener.md) | §8: AI Resume Screener — IMAP polling, screening, competency test, interview workflow |
| [spec-features-dashboard.md](spec-features-dashboard.md) | §9–12: RAG/chat widget, candidate UI, super admin panel, admin dashboard pages |
| [spec-api-routes.md](spec-api-routes.md) | §13: All backend API routes (FastAPI) |
| [spec-background-tasks.md](spec-background-tasks.md) | §14: Background task architecture — Celery task chains and beat schedule |
| [spec-audit-trail.md](spec-audit-trail.md) | §15: Job audit trail — 45 event types, real-time SSE via Postgres NOTIFY, UI |
| [spec-gdpr-email.md](spec-gdpr-email.md) | §16–17: GDPR compliance rules and email templates |
| [spec-testing.md](spec-testing.md) | §18: Automated testing strategy — unit, integration, E2E, mock table |
| [spec-structure-env.md](spec-structure-env.md) | §19–20: Project folder structure and all environment variables |
| [spec-tooling-security.md](spec-tooling-security.md) | §21–22: Development tooling, generation order, security considerations |
| [spec-deployment.md](spec-deployment.md) | §23–24: Fly.io deployment checklist and resolved v1/v2 items |
