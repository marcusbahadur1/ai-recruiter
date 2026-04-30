# AI Marketing Module — Phases 6–7: Celery Tasks & FastAPI Routers

*Full index: [marketing-module.md](marketing-module.md)*

## Phase 6 — Celery Tasks

**Claude CLI session prompt:**
```
You are adding Celery tasks for the AIRecruiterz Marketing Module.
Existing Celery setup is in backend/app/tasks/celery_app.py.
Existing tasks are in backend/app/tasks/scheduled_tasks.py — follow those patterns.
Create backend/app/tasks/marketing_tasks.py.
Update the beat schedule in celery_app.py or scheduled_tasks.py (wherever it lives).

All DB access must use SQLAlchemy async sessions in the same pattern as existing tasks.
Import the LinkedIn client, Unsplash client, and content generator from Phase 3-5.
```

### Tasks

**6.1 — `generate_and_schedule_posts`**
```
@celery_app.task — runs daily at 02:00 UTC

async logic:
1. Query all active MarketingSettings rows (platform + all tenants)
2. For each settings row:
   a. Is a post due today?
      daily:        always
      twice_weekly: weekday() in [0, 3]  (Monday=0, Thursday=3)
      weekly:       weekday() == 0
   b. Already posted or scheduled today for this account? -> skip
   c. Load linked MarketingAccount -> skip if none / is_active=False / token expired
   d. Count posts this week; skip if at plan limit
   e. Load last 30 MarketingPost rows for this account (for rotation helpers)
   f. topic = get_next_topic(settings, recent_posts)
      post_type = get_next_post_type(settings, recent_posts)
   g. result = await generate_post(settings, account, post_type, topic)
   h. INSERT MarketingPost:
        status = 'draft'   <- requires_approval=True by default for everyone
        scheduled_at = combine(today, settings.post_time_utc)
        all image fields from result
3. Log: "Marketing: {n} posts generated, {m} skipped, {p} failed"

Wrap each settings row in try/except — one failure must not block others.
```

**6.2 — `publish_scheduled_posts`**
```
@celery_app.task — runs every 15 minutes

async logic:
1. SELECT ... FOR UPDATE SKIP LOCKED on marketing_posts
   WHERE status='scheduled' AND scheduled_at <= now()
2. For each post:
   a. Load MarketingAccount; call refresh_access_token if expiring within 24h,
      re-encrypt and save new tokens
   b. tokens = account.get_decrypted_tokens()
   c. await LinkedInClient().create_post(
        access_token=tokens[0],
        author_urn=account.author_urn,
        text=post.content,
        hashtags=post.hashtags,
        image_url=post.image_url if post.include_image else None
      )
   d. Success: status='posted', posted_at=now(), platform_post_id=urn
   e. LinkedInRateLimitError: scheduled_at += 2h  (do not increment retry_count)
   f. LinkedInAuthError: status='failed', send alert email via sendgrid_email.py
   g. Other exception: retry_count += 1; if retry_count >= 3: status='failed'
```

**6.3 — `collect_post_stats`**
```
@celery_app.task — runs daily at 08:00 UTC

Query posted posts from last 30 days with platform_post_id set.
For each: get_post_stats() -> update likes, comments, impressions.
Bulk UPDATE in batches of 50 (executemany).
```

**6.4 — `auto_engage`**
```
@celery_app.task — runs daily at 10:00 UTC, route to 'marketing' queue

For each account with auto_engage=True and plan allows it:
  a. Count today's engagement rows for this account -> skip if at limit
  b. Derive keywords from settings.topics (first 3 topics, split to words)
  c. Search LinkedIn feed for recent matching posts via API
  d. For each candidate post (up to remaining daily limit):
     - Skip if (account_id, target_post_id, 'like') exists in marketing_engagement
     - await like_post()
     - Every 5th action: generate 1-sentence comment via ai_provider, 
       await comment_on_post()
     - INSERT marketing_engagement row
     - await asyncio.sleep(random.uniform(120, 300))  <- 2-5 min mandatory delay

Do NOT set a short task timeout on this — it runs slowly by design.
```

**6.5 — `refresh_linkedin_tokens`**
```
@celery_app.task — runs daily at 00:00 UTC

Query accounts where token_expires_at <= now() + 48h AND is_active=True.
For each:
  - await refresh_access_token(decrypted_refresh_token)
  - On success: re-encrypt, save new tokens + expiry
  - On failure: send alert email via sendgrid_email.py to:
      tenant_id IS NULL -> super_admin email (from env or config)
      tenant account    -> tenant.main_contact_email
    Include: account name, expiry datetime, reconnect URL
```

**6.6 — `post_to_linkedin_groups` + beat schedule update**
```
@celery_app.task — runs Tuesday at 09:00 UTC (day_of_week=2)

For each account where plan allows group_posting:
  a. Find best post last 7 days (MAX impressions, status='posted')
  b. If none: generate a fresh post via content_generator
  c. await get_groups() 
  d. Select up to 3 groups — rotate using Redis key to avoid repetition
  e. await post_to_group() for each; INSERT marketing_posts records

Then update the Celery beat schedule dict with all 6 new tasks:
  generate_and_schedule_posts:  crontab(hour=2,  minute=0)
  publish_scheduled_posts:      crontab(minute='*/15')
  collect_post_stats:           crontab(hour=8,  minute=0)
  auto_engage:                  crontab(hour=10, minute=0)
  refresh_linkedin_tokens:      crontab(hour=0,  minute=0)
  post_to_linkedin_groups:      crontab(day_of_week=2, hour=9, minute=0)
```

---

## Phase 7 — FastAPI Routers

**Claude CLI session prompt:**
```
You are implementing FastAPI routers for the AIRecruiterz Marketing Module.
All routes under /api/v1/marketing/.
Follow the existing router patterns in backend/app/routers/ for:
  - async SQLAlchemy session dependency injection
  - Supabase JWT auth dependency (get_current_user)
  - Pydantic v2 request/response schemas
  - HTTPException patterns
  - Pagination (look at how candidates or jobs router paginates)
  
All phases before this are complete and importable.
```

### Tasks

**7.1 — Accounts router (`backend/app/routers/marketing_accounts.py`)**
```
(OAuth connect/callback/select-page routes were already done in Phase 3 router.
This router covers the remaining account management routes.)

GET /api/v1/marketing/accounts
  Returns list of MarketingAccountRead for current tenant.
  Super admin with ?tenant_id= can view any tenant's accounts.

DELETE /api/v1/marketing/accounts/{account_id}  (already in Phase 3 — skip if done)

Include in main.py.
```

**7.2 — Posts router (`backend/app/routers/marketing_posts.py`)**
```
GET /api/v1/marketing/posts
  Paginated. Query params: status, platform, date_from, date_to, page, page_size.
  Scoped to current tenant (RLS also enforces this).

POST /api/v1/marketing/posts
  Body: MarketingPostCreate
  Creates post with status='draft' if settings.requires_approval else 'scheduled'.

PATCH /api/v1/marketing/posts/{post_id}
  Body: MarketingPostUpdate
  Only allowed when status in ('draft', 'scheduled').
  Fields: content, hashtags, scheduled_at, include_image.

POST /api/v1/marketing/posts/{post_id}/approve
  Sets status='scheduled'. Only valid when status='draft'.

POST /api/v1/marketing/posts/{post_id}/reject
  Sets status='draft', clears scheduled_at. (Returns post to draft for editing.)

DELETE /api/v1/marketing/posts/{post_id}
  Only allowed when status != 'posted'.

POST /api/v1/marketing/posts/generate
  Triggers MarketingContentGenerator.generate_post() immediately.
  Returns the new MarketingPost (status='draft') — does NOT auto-publish.
  Optional body: {post_type: str | None, topic: str | None}
  If omitted, uses rotation helpers to pick type and topic.

Plan gating on all routes: plan must be in marketing_visible list else 403.
```

**7.3 — Settings router (`backend/app/routers/marketing_settings.py`)**
```
GET /api/v1/marketing/settings
  Returns MarketingSettingsRead for current tenant.
  Creates default row if none exists yet (copy platform defaults but set is_active=False).

PATCH /api/v1/marketing/settings
  Body: MarketingSettingsUpdate
  Validate plan limits:
  - auto_engage=True requires plan in auto_engage list; else 422
  - engagement_per_day capped at 20

POST /api/v1/marketing/toggle
  Body: {is_active: bool}
  Flips settings.is_active for the current tenant.
  Super admin can toggle any tenant or the platform account.
```

**7.4 — Analytics router (`backend/app/routers/marketing_analytics.py`)**
```
GET /api/v1/marketing/analytics
  Query params: date_from, date_to
  Enforce retention limit from get_marketing_limits():
    agency_small: max 30 days history
    agency_medium: max 90 days
    enterprise: max 365 days
  Returns list of {date, impressions, likes, comments, posts_count} grouped by day.

GET /api/v1/marketing/analytics/summary
  Returns MarketingAnalyticsSummary:
    total_posts, total_impressions, avg_engagement_rate, top_post

GET /api/v1/marketing/engagement
  Paginated log of marketing_engagement rows for current tenant's accounts.
```

---
