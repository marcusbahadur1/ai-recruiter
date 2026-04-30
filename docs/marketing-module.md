# AI Marketing Module — Index

Section 25 of the AIRecruiterz spec. Implementation plan split across 11 phases.

| File | Description |
|---|---|
| [marketing-module-overview.md](marketing-module-overview.md) | Tech stack, product decisions, implementation order summary |
| [marketing-module-phases1-2.md](marketing-module-phases1-2.md) | Phase 1: Alembic migrations (4 tables + RLS + seed); Phase 2: SQLAlchemy models, Pydantic schemas, plan limits |
| [marketing-module-phases3-5.md](marketing-module-phases3-5.md) | Phase 3: LinkedIn OAuth client + FastAPI router; Phase 4: Unsplash image integration; Phase 5: AI content generation engine |
| [marketing-module-phases6-7.md](marketing-module-phases6-7.md) | Phase 6: Celery tasks (6 tasks, beat schedule); Phase 7: FastAPI routers (accounts, posts, settings, analytics) |
| [marketing-module-phases8-9.md](marketing-module-phases8-9.md) | Phase 8: Tenant marketing dashboard (5 tabs); Phase 9: Super admin marketing dashboard |
| [marketing-module-phases10-11.md](marketing-module-phases10-11.md) | Phase 10: Testing (unit + integration tests for all services); Phase 11: Config & deployment (env vars, Celery queues, attribution note) |
