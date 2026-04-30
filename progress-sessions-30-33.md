# PROGRESS — Sessions 30–33 (Marketing Tests + Deploy + Scout Fix)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 33 — Talent Scout `DuplicatePreparedStatementError` Fix

- **Bug**: After posting a job via AI chat, Scout triggered but produced no candidates. Worker logs showed cascading `DuplicatePreparedStatementError` on `enrich_profile` and `score_candidate` retries.
- **Root cause**: Celery tasks use `asyncio.run()` with `NullPool` + asyncpg against Supabase's **transaction pooler** (pgbouncer port 6543). In transaction mode, pgbouncer reassigns the backend Postgres connection after every COMMIT. When a task fails mid-execution, asyncpg cannot send the `DEALLOCATE` protocol message for the named prepared statement it was using (e.g. `__asyncpg_stmt_34__`). That statement persists on the backend connection, which pgbouncer returns to its pool. When the task retries on a new asyncpg connection and reaches its 34th parameterized query, it tries to prepare `__asyncpg_stmt_34__` on the same backend — collision. This cascades as more tasks fail and leak more statement names.
- **Fix**: `_build_task_db_url()` in `backend/app/database.py` auto-switches the task engine URL from port 6543 (transaction pooler) to port 5432 (session pooler). In pgbouncer **session mode**, the same backend Postgres connection is held for the entire client session — prepared statements are unique to the connection and cleaned up on close. No collision possible. The API engine (port 6543) is unaffected.
- **Deployed**: worker redeployed to `airecruiterz-worker` (`syd`).

### Session 32 — Branch Strategy + Cleanup

- **Branch strategy established**: `main` (production, protected) → `develop` (integration) → `feature/*`. Hotfixes branch from `main`, merge back to both `main` and `develop`.
- **`develop` branch created** from `main` and pushed to origin.
- **`feature/marketing` updated**: merged `develop` to bring in Railway/Vercel deletion docs; fully up to date.
- **Tags**: `v1.0.0` already existed (session 10). Tagged current `main` as `v1.1.0` — Fly.io migration + production smoke suite baseline.
- **Railway deleted**: `laudable-upliftment` project deleted via Railway CLI (permanent 2026-04-28).
- **Vercel deleted**: `frontend` project deleted via Vercel CLI.
- **Next release**: `v1.2.0` — AI Marketing Module (`feature/marketing` → `develop` → `main`).

### Session 31 — AI Marketing Module: Phase 11 (Config & Deployment Prep)

**Phase 11 — Config & Deployment Prep** (`feature/marketing` branch)
- `backend/.env.example` — added `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`, `UNSPLASH_ACCESS_KEY` with registration instructions (developer.linkedin.com, per-environment redirect URIs, unsplash.com/oauth/applications)
- `backend/worker.sh` — added `-Q celery,marketing` so the Celery worker processes both the default `celery` queue and the `marketing` queue (`auto_engage` and `post_to_linkedin_groups` are routed to the `marketing` queue via `task_routes` in `celery_app.py`; without this flag they would be silently ignored)
- **Manual ops remaining before merging to main:**
  1. Register LinkedIn OAuth app at developer.linkedin.com; add production + staging redirect URIs
  2. Set on Fly.io (api + worker): `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`, `UNSPLASH_ACCESS_KEY`
  3. Run `alembic upgrade head` on production DB (migrations 0014–0020, marketing tables + RLS + seed)
  4. Merge `feature/marketing` → `main`; deploy to Fly.io

### Session 30 — AI Marketing Module: Phase 10 (Tests)

**Phase 10 — Tests**
- `backend/tests/unit/test_marketing_image_query.py` — 19 unit tests for `generate_image_search_query` and `_extract_keywords`: stop-word stripping, max_words limit, hyphens, non-alpha exclusion, per-post-type context word appending, industry_stat/poll fallbacks, all-stop-word topic fallback
- `backend/tests/unit/test_marketing_content_generator.py` — 27 unit tests for `MarketingContentGenerator`: `_validate` (empty content, first-person opener, banned phrases, hashtag format), `get_next_topic` (rotation, 14-day recency window, empty-topics fallback), `get_next_post_type` (round-robin, wrap-around, defaults), `generate_post` (returns expected keys, fetches image when enabled, raises on validation failure, swallows `UnsplashRateLimitError`)
- `backend/tests/integration/test_marketing_posts.py` — 16 integration tests covering all 7 posts routes: plan gate (403), list posts (empty / with posts / filter), generate (creates draft / 422 no account), approve/reject (status transitions / 422 guards), delete (204 / 422 posted), update (200 draft / 422 posted)
- `backend/tests/integration/test_marketing_settings.py` — 14 integration tests: plan gate (403), GET settings (existing row / auto-create from defaults / auto-create without defaults), PATCH settings (tone / topics / auto_engage blocked small / auto_engage allowed medium), POST toggle (activate / pause / 403 non-super for other tenant)
- `backend/tests/integration/test_marketing_analytics.py` — 11 integration tests: plan gate (403), GET analytics (empty / aggregated rows / date range), GET analytics/summary (zeros / with stats + top post), GET engagement (empty / actions / pagination)
- `backend/app/models/marketing.py` — added `ForeignKey("marketing_accounts.id")` to `MarketingPost.account_id` and `MarketingEngagement.account_id` (SQLAlchemy 2.x requires FK in mapped_column for relationship resolution, not just string primaryjoin)
- Total: 375 tests passing (was 294)
