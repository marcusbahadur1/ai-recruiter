# PROGRESS — Session 26 (AI Marketing Module: Phases 1–6)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 26 — AI Marketing Module: Phases 1–6

**Branch:** `feature/marketing` (local development only — not deployed to staging/production)

**Phase 1 — Alembic Migrations**
- `0014_marketing_accounts` — `marketing_accounts` table: platform + tenant OAuth accounts, Fernet-encrypted token columns, NULLS NOT DISTINCT unique index on `(tenant_id, platform, account_type)` so one personal + one company per tenant per platform is enforced correctly including the platform-level NULL row
- `0015_marketing_settings` — `marketing_settings` table: per-tenant/platform config, NULLS NOT DISTINCT unique on `tenant_id`, post_frequency/tone CHECK constraints, all JSONB defaults wired
- `0016_marketing_posts` — `marketing_posts` table: full post lifecycle (draft → scheduled → posted/failed), image fields (`include_image`, `image_url`, `image_attribution` JSONB for Unsplash ToS), 4 indexes on tenant_id+status, account_id+status, scheduled_at, posted_at
- `0017_marketing_engagement` — `marketing_engagement` table: like/comment/follow/group_post action log, unique on `(account_id, target_post_id, action_type)` to prevent duplicate actions
- `0018_marketing_rls` — ENABLE + FORCE ROW LEVEL SECURITY on all 4 marketing tables (same pattern as migration 0013)
- `0019_marketing_settings_seed` — platform-level default settings row (tenant_id IS NULL), `is_active=FALSE` until LinkedIn company page connected, ON CONFLICT DO NOTHING

**Phase 6 — Celery Tasks**
- `backend/app/tasks/marketing_tasks.py` — 6 Celery tasks:
  - `generate_and_schedule_posts`: checks frequency cadence (daily/twice-weekly/weekly skip logic), plan weekly limit, token expiry guard, calls `MarketingContentGenerator`, inserts posts as `draft` status
  - `publish_scheduled_posts`: `SELECT FOR UPDATE SKIP LOCKED` for concurrent-safe publishing, token refresh on AuthError before retrying, `LinkedInClient.create_post()`, RateLimitError → reschedule +2h, AuthError after refresh → mark failed + alert, other errors → increment `retry_count`, fail at 3
  - `collect_post_stats`: batches of 50 posted posts, `get_post_stats()`, updates likes/comments/impressions
  - `auto_engage`: queue="marketing", respects `engagement_per_day` limit, mandatory `asyncio.sleep(random.uniform(120, 300))` between actions; LinkedIn feed search API requires MDP access (placeholder empty list with clear logger.debug warning)
  - `refresh_linkedin_tokens`: 48h lookahead, proactive refresh before expiry, sends alert email on failure
  - `post_to_linkedin_groups`: find best post last 7 days or generate fresh, Redis rotation key (7d TTL), post to up to 3 groups; queue="marketing"
- `backend/app/tasks/celery_app.py` — added `app.tasks.marketing_tasks` to `include` list; 6 beat schedule entries (UTC clock times); task routing for `auto_engage` + `post_to_linkedin_groups` → `marketing` queue

**Phase 5 — Content Generation Engine**
- `backend/migrations/versions/0020_marketing_posts_topic.py` — adds nullable `topic` TEXT column to `marketing_posts` (needed by rotation logic)
- `backend/app/services/marketing/content_generator.py` — `MarketingContentGenerator`: `generate_post()` builds structured prompt (length guideline + hashtag count per post type, tone description, audience), calls `AIProvider.complete_json()`, validates output (`_validate`: no empty content, no "I " opener, no banned phrases, hashtags start with `#`), fetches Unsplash image if `settings.include_images` with fire-and-forget `trigger_download` via `asyncio.create_task`. `get_next_topic()` excludes topics used in last 14 days, falls back to `random.choice`. `get_next_post_type()` round-robin through enabled types, never repeats last. `ContentGenerationError` with `.detail` field.

**Phase 4 — Unsplash Image Integration**
- `backend/app/services/marketing/unsplash_client.py` — `UnsplashClient`: `search_photo()` with Redis cache (1hr TTL, key = MD5 of query), returns `{image_url, download_trigger_url, attribution}`. `trigger_download()` per Unsplash ToS — swallows all exceptions. `UnsplashRateLimitError` on 429. Returns `None` when key not set or no results. Redis helpers non-fatal.
- `backend/app/services/marketing/image_query.py` — `generate_image_search_query(post_type, topic)`: rule-based, no AI. Stop-word stripping, 2-word extraction + context suffix. `industry_stat` + `poll` use generic fallbacks for better imagery.

**Phase 3 — LinkedIn OAuth Integration**
- `backend/app/services/marketing/linkedin_client.py` — `LinkedInClient` async class: `get_authorization_url` (personal vs company scopes), `exchange_code_for_tokens`, `refresh_access_token`, `get_personal_profile`, `get_company_pages`, `create_post` (with image upload via `registerUpload` + PUT binary), `get_post_stats`, `like_post`, `comment_on_post`, `get_groups`, `post_to_group`. `_upload_image` returns `None` on failure so post goes out without image. `LinkedInRateLimitError` / `LinkedInAuthError` exceptions. Tokens never logged.
- `backend/app/routers/marketing_oauth.py` — 6 routes under `/api/v1/marketing`: `POST /accounts/linkedin/connect` (plan gate, Redis state 10min TTL), `GET /accounts/linkedin/callback` (exchange code, single page → upsert + redirect, multi-page → Redis temp token 15min + redirect to picker), `GET /accounts/linkedin/select-page/pages` (return pages from Redis for picker UI), `POST /accounts/linkedin/select-page` (upsert chosen page, clean up temp token), `GET /accounts` (list active accounts), `DELETE /accounts/{id}` (disconnect, revert scheduled posts to draft)
- `backend/app/config.py` — `linkedin_client_id`, `linkedin_client_secret`, `linkedin_redirect_uri`, `unsplash_access_key` optional settings fields added
- `backend/app/main.py` — `marketing_oauth` router registered at `/api/v1`

**Phase 2 — SQLAlchemy Models + Pydantic Schemas + Plan Limits**
- `backend/app/models/marketing.py` — 4 mapped classes:
  - `MarketingAccount`: `set_encrypted_tokens()` / `get_decrypted_tokens()` Fernet helpers, `is_token_expired` property, `is_token_expiring_soon(hours)` method, `author_urn` property (urn:li:organization vs urn:li:person), relationships to posts + engagements
  - `MarketingSettings`: all config columns, `Time` column for `post_time_utc`, JSONB defaults via lambdas (avoids shared-state mutation)
  - `MarketingPost`: full lifecycle columns, image fields, `has_image` property, account relationship
  - `MarketingEngagement`: action log, account relationship
- `backend/app/schemas/marketing.py` — Pydantic v2 schemas: `ImageAttributionSchema`, `MarketingAccountRead` (computed fields via `from_orm()`, tokens excluded), `MarketingSettingsRead/Update` (validators: engagement_per_day ≤ 20, non-empty lists), `MarketingPostRead/Create/Update` (hashtag `#` prefix validator), `MarketingEngagementRead`, `MarketingAnalyticsSummary`
- `backend/app/models/__init__.py` — all 4 marketing models exported
- `backend/app/config.py` — `MARKETING_PLAN_FEATURES` dict + `get_marketing_limits(tenant_plan)` helper
