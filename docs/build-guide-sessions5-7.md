> **Historical document** — used to bootstrap code generation in sessions 1–10. Not needed for active development.

# Build Guide Part 3: Sessions 5–7 (Pipeline + Frontend)

*Full index: see [build-guide.md](build-guide.md)*

---

## SESSION 5 — Talent Scout Celery pipeline

```
Read SPEC.md and guidelines.md.

1. backend/app/tasks/celery_app.py — Celery app with Redis broker + beat schedule (SPEC.md §14.2)

2. backend/app/services/talent_scout.py:
   - build_search_queries(job) -> list[str] — all title × location combos (§7.1.1, location rules by work_type)
   - All methods emit correct audit events per SPEC.md §15.2

3. backend/app/tasks/talent_scout_tasks.py — Celery chord:
   - discover_candidates(job_id, tenant_id) — SERP calls for all queries, create Candidate records,
     deduplicate, fan out chord to tasks 2–5
   - enrich_profile(candidate_id, tenant_id) — BrightData call
   - score_candidate(candidate_id, tenant_id) — AI scoring via ai_provider facade
   - discover_email(candidate_id, tenant_id) — Apollo/Hunter/Snov by tenant.email_discovery_provider,
     then EmailDeductionService fallback
   - send_outreach(candidate_id, tenant_id) — AI-generated personalised email, SendGrid,
     GDPR unsubscribe link required

   ALL tasks: max_retries=3, exponential backoff, idempotent (check status before acting),
   emit audit events on success AND failure.

4. Unit tests for talent_scout.py, integration tests for task chain.
   Mock all external APIs per SPEC.md §18.4
```

After: run `pytest backend/tests/ -v`, commit: `"Session 5: Talent Scout Celery pipeline"`.

---

## SESSION 6 — Resume Screener + IMAP + chat sessions

```
Read SPEC.md and guidelines.md.

1. backend/app/tasks/screener_tasks.py:
   - poll_mailboxes() — polls IMAP for all active tenants, full flow from SPEC.md §8.1
   - screen_resume(application_id, tenant_id) — cosine similarity + AI evaluation (§8.2)
   - invite_to_test(application_id, tenant_id) — generate questions, create test_session, send invitation
   - score_test(application_id, tenant_id) — score full transcript

2. backend/app/routers/applications.py — add test chat endpoints:
   - GET /test/{id}/{token} — public, token-protected
   - POST /test/{id}/message — public, one turn of test conversation via AI
   - GET /actions/invite-interview/{id}/{token} — public, processes hiring manager click

3. backend/app/routers/chat_sessions.py — full implementation:
   - GET /chat-sessions/current — returns or creates current session
   - POST /chat-sessions/{id}/message — appends to DB, calls AI, returns response
   - POST /chat-sessions/new
   - AI system prompt for job collection follows SPEC.md §6.3 (16 steps)
   - Phase detection (job_collection → payment → recruitment) handled in backend

4. Integration tests for all screener tasks and chat session routes.
   Mock IMAP with pre-loaded test emails.
```

After: run `pytest backend/tests/ -v`, commit: `"Session 6: Resume Screener, IMAP poller, chat sessions"`.

---

## SESSION 7 — Stripe, promo codes, webhooks, RAG, email templates

```
Read SPEC.md and guidelines.md.

1. backend/app/routers/webhooks.py:
   - POST /webhooks/stripe — handles all 4 events from SPEC.md §4.3
   - POST /webhooks/email-received — HMAC verified

2. backend/app/routers/promo_codes.py — full CRUD

3. backend/app/services/rag_pipeline.py:
   - scrape_website(tenant_id, url) — crawl4ai scrape, chunk, embed, store in rag_documents
   - upload_document(tenant_id, file_content, filename) — extract, chunk, embed, store
   - query(tenant_id, question, top_k=5) -> list[str] — cosine search rag_documents

4. backend/app/routers/rag.py and backend/app/routers/widget.py — full implementation

5. backend/app/templates/ — Jinja2 HTML email templates for all 12 templates in SPEC.md §17.
   Each template: subject, html_body, text_fallback.
   Every outreach template MUST include unsubscribe link placeholder.

6. backend/app/routers/super_admin.py — full implementation per SPEC.md §11
```

After: run `pytest backend/tests/ -v`, commit: `"Session 7: Stripe, RAG, email templates, super admin"`.

---

## SESSION 9 — Next.js frontend

```
Read SPEC.md and guidelines.md.

1. Scaffold: npx create-next-app@latest frontend --typescript --app --tailwind --no-src-dir
2. Install: npm install next-intl @supabase/supabase-js react-hook-form zod @tanstack/react-query axios
3. Set up i18n with next-intl for EN, DE, ES, FR — frontend/app/[locale]/layout.tsx as root layout
4. Generate all pages per SPEC.md §12 in order:
   (auth) login, signup
   (dashboard) layout (sidebar+topbar), home, chat, jobs list, job detail (tabbed),
   candidates list/profile, application detail, settings, super-admin
   (public) test page

5. frontend/lib/api/ — typed API client matching all backend routes
6. SSE hook: frontend/hooks/useAuditStream.ts — EventSource with reconnect + replay

Colour scheme: --navy: #0D1B2A, --blue: #1B6CA8, --cyan: #00C2E0. Dark theme, DM Sans font.
```

After: run `cd frontend && npm run build`, fix TypeScript errors, commit: `"Session 9: Next.js frontend"`.
