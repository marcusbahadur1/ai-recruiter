## Session Start Protocol — Non Negotiable

Before any action in any session:
1. Read `.claude/knowledge/INDEX.md`
2. Select only the knowledge files relevant to the current task
3. Read those files and form a hypothesis before touching any code
4. If the knowledge base has a gap, fill it after the task is done

## Knowledge File Size Rule — Non Negotiable

Every file in `.claude/knowledge/` must stay under 600 tokens.
When any update would push a file over this limit:
1. Split at a logical boundary before saving
2. Create a new descriptively named file for the split content
3. Leave a pointer line in the original file
4. Add the new file to INDEX.md and update last-updated dates for both files

---
## Session End Rule
When the user says "done", "wrap up", "that's it for today", or "end session":
1. Update docs/task-management/PROGRESS.md — append a brief summary of what we did
2. Update docs/task-management/TODO.md — check off completed tasks, add any new ones that came up
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

## Knowledge Base Protocol

`.claude/knowledge/INDEX.md` is the single source of truth for all project knowledge. CLAUDE.md will never grow beyond this pointer.

BEFORE every debug session, bug fix, or feature addition:
1. Read `.claude/knowledge/INDEX.md`
2. Identify which knowledge files relate to the current task
3. Read only those files
4. Use call sequences and fragile zone notes to narrow the search space before writing any diagnostic or test code

AFTER every bug fix or enhancement:
1. Update the relevant call sequence in `CALL_SEQUENCES.md` if any flow changed
2. Add a fingerprint entry to `BUG_HISTORY.md` if a bug was fixed
3. Update `FRAGILE_ZONES.md` if new risk was discovered
4. Update `DECISIONS.md` if a non-obvious choice was made
5. Update the last-updated date in `INDEX.md` for every file touched
6. If a new domain emerged, create its domain file and add it to `INDEX.md`
7. Remove outdated entries rather than leaving them to accumulate

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
- No .md file (except CLAUDE.md) may exceed 1000 tokens. If a file would exceed this, split it into focused sub-files and replace the original with an index file listing each part with its path and a one-line description. The index file must itself stay under 1000 tokens.

## Session Context (load on demand)
- Current progress: @docs/task-management/PROGRESS.md
- Active todos: @docs/task-management/TODO.md
---
