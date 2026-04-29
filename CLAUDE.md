---
## Session End Rule
When the user says "done", "wrap up", "that's it for today", or "end session":
1. Update PROGRESS.md — append a brief summary of what we did
2. Update TODO.md — check off completed tasks, add any new ones that came up
3. Check CLAUDE.md — if anything task-related has crept in, move it out
4. Stage all changes: git add -A
5. Write a brief commit message summarising what was done today (max 72 chars)
6. Commit and push to the current branch
7. Confirm with: "Session files updated and pushed ✓"

Do not add anything to CLAUDE.md unless it is a permanent project-wide rule.
---

# AI Recruiter — Project Rules

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.12, async), SQLAlchemy 2.x, asyncpg |
| Database | Supabase PostgreSQL + pgvector, RLS on all tables |
| Workers | Celery + Redis (Fly.io Upstash) |
| Frontend | Next.js 16 TypeScript App Router |
| Auth | Supabase Auth (JWT) |
| AI | `ai_provider.py` facade → Claude Sonnet (primary) + OpenAI (optional) |
| Hosting | Fly.io `syd`: `airecruiterz-api`, `airecruiterz-worker`, `airecruiterz-app` |

## Folder Structure
```
backend/app/   models/  schemas/  routers/  services/  tasks/  templates/
frontend/      app/[locale]/(dashboard|auth|public)/   lib/api/   messages/
e2e/           tests/production/   tests/smoke/
```

## Key Commands
```bash
# Dev (3 terminals — activate venv first for backend/celery)
uvicorn app.main:app --reload                                  # backend/
npm run dev                                                    # frontend/
celery -A app.tasks.celery_app worker -Q celery,marketing --loglevel=info  # backend/

# Test
pytest                   # backend/
npm run prod:all         # e2e/ — full production smoke suite

# Deploy — see @frontend/AGENTS.md for Fly.io deploy commands
```

## Non-Obvious Project Rules

**Every DB query must include `tenant_id`** — never query without it, including inside Celery tasks (which receive `tenant_id` as a parameter, not from JWT).

**AI calls go through `AIProvider(tenant)` facade only** — never call `anthropic` or `openai` SDKs directly from routers or tasks.

**Celery tasks must be idempotent** (check status before acting), use `max_retries=3` with exponential backoff (`countdown=2 ** self.request.retries * 30`), and emit audit events via `audit_trail.py` on both success and failure.

**Chat session persistence uses a fresh `AsyncSessionLocal()` with an explicit `UPDATE`** — not ORM-level `session.messages = ...; await db.commit()`. After many async yields, the request-scoped `db` connection is unreliable with NullPool.

**Main SQLAlchemy engine uses `NullPool`** — prevents `DuplicatePreparedStatementError` with pgbouncer transaction mode. Do not add connection pooling to the main engine.

**Frontend uses `proxy.ts` not `middleware.ts`** — never delete `proxy.ts`, never create `middleware.ts` alongside it. All API calls use relative `/api/v1/...` paths.

## References
- Full coding rules (15 sections): @docs/guidelines.md
- Application specification: @docs/spec.md
- Local dev setup + test data: @docs/dev-setup.md
- Frontend rules + deploy commands: @frontend/AGENTS.md
- Marketing module plan: @docs/marketing-module.md

---
## Doc Structure Rule
- All .md files except CLAUDE.md live in docs/
- If any .md file exceeds 300 lines or covers more than one topic, split it into focused sub-files in docs/
- Architecture docs live in docs/architecture/ — if a module or feature grows complex, give it its own file there rather than expanding an existing one
- Keep docs/index.md updated with a one-line description of every file
- Apply this check during every session end routine

## Session Context (load on demand)
- Current progress: @PROGRESS.md
- Active todos: @TODO.md
---
