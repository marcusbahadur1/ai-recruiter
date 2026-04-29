# AIRecruiterz — Section 25: AI Marketing Module
## Claude CLI Implementation Plan (v3 — correct tech stack)

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
| Frontend | Next.js 16 TypeScript App Router (Vercel) |
| i18n | Next.js built-in routing — `/[locale]/marketing` |
| Testing | pytest + pytest-asyncio + httpx + Playwright |

### Confirmed product decisions
| # | Decision | Answer |
|---|----------|--------|
| 1 | Platform LinkedIn account type | **Company page** (`urn:li:organization:{id}`) |
| 2 | Tenant LinkedIn account type | **Both** — personal profile OR company page, tenant's choice |
| 3 | Approval mode default | **`requires_approval = True`** for all accounts, toggleable off |
| 4 | Post images | **Unsplash API** stock photos + global settings toggle + per-post toggle |

---

## Phase 1 — Alembic Migrations

**Claude CLI session prompt:**
```
You are adding the AI Marketing Module (Section 25) to AIRecruiterz.
Stack: FastAPI, SQLAlchemy 2.x async, Alembic, Supabase PostgreSQL.
This phase is Alembic migrations ONLY — no model or application code yet.
Migrations live in backend/migrations/versions/.
Follow the existing Alembic migration style already in that directory.
```

### Tasks

**1.1 — `marketing_accounts` table**
```
Create an Alembic migration that adds the marketing_accounts table:

Columns:
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
  tenant_id         UUID REFERENCES tenants(id) ON DELETE CASCADE NULLABLE
                    -- NULL means this is the platform-level account
  platform          VARCHAR NOT NULL CHECK (platform IN ('linkedin','twitter','facebook'))
  account_name      VARCHAR(200) NOT NULL
  account_type      VARCHAR NOT NULL DEFAULT 'company'
                    CHECK (account_type IN ('personal','company'))
                    -- determines LinkedIn URN format used when posting
  linkedin_urn      VARCHAR(200)
                    -- raw ID from LinkedIn: numeric for company, alphanumeric for personal
  access_token      TEXT  -- Fernet-encrypted at application layer
  refresh_token     TEXT  -- Fernet-encrypted at application layer
  token_expires_at  TIMESTAMPTZ
  is_active         BOOLEAN NOT NULL DEFAULT TRUE
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
  UNIQUE (tenant_id, platform, account_type)
  -- allows one personal + one company per tenant per platform

Indexes:
  idx_marketing_accounts_tenant_id ON marketing_accounts(tenant_id)
```

**1.2 — `marketing_settings` table**
```
Create an Alembic migration that adds the marketing_settings table:

Columns:
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid()
  tenant_id            UUID REFERENCES tenants(id) ON DELETE CASCADE NULLABLE
                       -- NULL = platform-level settings
  post_frequency       VARCHAR NOT NULL DEFAULT 'twice_weekly'
                       CHECK (post_frequency IN ('daily','twice_weekly','weekly'))
  post_time_utc        TIME NOT NULL DEFAULT '09:00'
  post_types_enabled   JSONB NOT NULL DEFAULT '["thought_leadership","industry_stat","tip"]'
  platforms_enabled    JSONB NOT NULL DEFAULT '["linkedin"]'
  target_audience      TEXT
  tone                 VARCHAR NOT NULL DEFAULT 'professional'
                       CHECK (tone IN ('professional','conversational','bold','educational'))
  topics               JSONB NOT NULL DEFAULT '[]'
  auto_engage          BOOLEAN NOT NULL DEFAULT TRUE
  engagement_per_day   INTEGER NOT NULL DEFAULT 10
  requires_approval    BOOLEAN NOT NULL DEFAULT TRUE   -- TRUE for all by default
  include_images       BOOLEAN NOT NULL DEFAULT TRUE   -- global Unsplash toggle
  is_active            BOOLEAN NOT NULL DEFAULT TRUE
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
  UNIQUE (tenant_id)  -- one settings row per tenant (NULL counts as unique)
```

**1.3 — `marketing_posts` table**
```
Create an Alembic migration that adds the marketing_posts table:

Columns:
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE NULLABLE
  account_id          UUID NOT NULL REFERENCES marketing_accounts(id) ON DELETE CASCADE
  platform            VARCHAR NOT NULL CHECK (platform IN ('linkedin','twitter','facebook'))
  post_type           VARCHAR NOT NULL
                      CHECK (post_type IN ('thought_leadership','industry_stat',
                             'success_story','tip','poll','carousel'))
  content             TEXT NOT NULL
  hashtags            JSONB NOT NULL DEFAULT '[]'
  include_image       BOOLEAN NOT NULL DEFAULT TRUE   -- per-post toggle
  image_search_query  TEXT                            -- sent to Unsplash
  image_url           TEXT                            -- returned Unsplash URL
  image_attribution   JSONB
                      -- {photographer_name, photographer_url, unsplash_url}
                      -- required by Unsplash ToS; must be displayed in UI
  scheduled_at        TIMESTAMPTZ NOT NULL
  posted_at           TIMESTAMPTZ
  status              VARCHAR NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','scheduled','posted','failed'))
  retry_count         INTEGER NOT NULL DEFAULT 0
  platform_post_id    VARCHAR(200)   -- URN returned by LinkedIn after posting
  likes               INTEGER NOT NULL DEFAULT 0
  comments            INTEGER NOT NULL DEFAULT 0
  impressions         INTEGER NOT NULL DEFAULT 0
  clicks              INTEGER NOT NULL DEFAULT 0
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()

Indexes:
  idx_marketing_posts_tenant_status   ON marketing_posts(tenant_id, status)
  idx_marketing_posts_account_status  ON marketing_posts(account_id, status)
  idx_marketing_posts_scheduled_at    ON marketing_posts(scheduled_at)
  idx_marketing_posts_posted_at       ON marketing_posts(posted_at)
```

**1.4 — `marketing_engagement` table**
```
Create an Alembic migration that adds the marketing_engagement table:

Columns:
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid()
  account_id     UUID NOT NULL REFERENCES marketing_accounts(id) ON DELETE CASCADE
  action_type    VARCHAR NOT NULL
                 CHECK (action_type IN ('like','comment','follow','group_post'))
  target_post_id VARCHAR(200) NOT NULL  -- external LinkedIn post URN
  target_author  VARCHAR(200) NOT NULL
  content        TEXT                   -- comment text if action_type='comment'
  performed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
  UNIQUE (account_id, target_post_id, action_type)
  -- prevents engaging the same post twice with the same action

Indexes:
  idx_marketing_engagement_account_performed ON marketing_engagement(account_id, performed_at)
```

**1.5 — Supabase RLS policies**
```
Add to the Alembic migration (or a separate one) the RLS policies for all 4 new tables.
Follow the same RLS pattern used for existing tables in the project.

For each table, enable RLS and add policies:
  - Tenants can only SELECT/INSERT/UPDATE/DELETE rows where tenant_id = auth.uid()
    (same jwt claim used elsewhere in the project)
  - Platform rows (tenant_id IS NULL) are accessible only to super_admin role
  - Use the exact same policy helper function already established in the codebase

Also add Supabase RLS to marketing_engagement via the account_id -> tenant_id join,
or add a tenant_id denormalised column to marketing_engagement for simpler RLS.
```

**1.6 — Seed default platform-level marketing_settings**
```
Create a standalone Alembic data migration that INSERTs the platform-level defaults:

INSERT INTO marketing_settings (
  tenant_id, post_frequency, post_time_utc, post_types_enabled, platforms_enabled,
  target_audience, tone, topics, auto_engage, engagement_per_day,
  requires_approval, include_images, is_active
) VALUES (
  NULL,
  'twice_weekly',
  '09:00',
  '["thought_leadership","industry_stat","success_story","tip"]',
  '["linkedin"]',
  'Recruitment agency owners and directors',
  'professional',
  '["AI recruitment","time-to-hire","passive candidates","recruitment automation"]',
  true,
  10,
  true,    -- requires approval on by default
  true,
  false    -- disabled until platform LinkedIn company page is connected
)
ON CONFLICT (tenant_id) DO NOTHING;
```

---

## Phase 2 — SQLAlchemy Models & Pydantic Schemas

**Claude CLI session prompt:**
```
You are adding SQLAlchemy 2.x async models and Pydantic v2 schemas for the 
AIRecruiterz Marketing Module.

Stack: SQLAlchemy 2.x (declarative, async), Pydantic v2, Fernet encryption.
Existing patterns to follow:
- Models live in backend/app/models/ — look at tenant.py for FK and Base patterns
- Schemas live in backend/app/schemas/ — look at existing schemas for Pydantic v2 style
- Fernet encryption is in backend/app/services/ — find the encrypt/decrypt helpers 
  used for tenant API keys and replicate that exact pattern for OAuth tokens
- Use the existing Base class and async session patterns throughout
```

### Tasks

**2.1 — SQLAlchemy models (`backend/app/models/marketing.py`)**
```
Create backend/app/models/marketing.py with four mapped classes:
MarketingAccount, MarketingSettings, MarketingPost, MarketingEngagement

MarketingAccount:
  - All columns from migration 1.1
  - Two helper methods (NOT columns) using Fernet:
      set_encrypted_tokens(access_token: str, refresh_token: str) -> None
      get_decrypted_tokens() -> tuple[str, str]
      Use the same encrypt/decrypt helpers already used for tenant AI API keys
  - Property: is_token_expired -> bool
  - Method: is_token_expiring_soon(hours: int = 24) -> bool
  - Property: author_urn -> str
      if account_type == 'company':  return f"urn:li:organization:{self.linkedin_urn}"
      if account_type == 'personal': return f"urn:li:person:{self.linkedin_urn}"

MarketingSettings:
  - All columns from migration 1.2
  - Relationship back to MarketingAccount (one settings -> many accounts via tenant_id)

MarketingPost:
  - All columns from migration 1.3
  - Property: has_image -> bool (True when image_url is not None)
  - Relationship to MarketingAccount

MarketingEngagement:
  - All columns from migration 1.4
  - Relationship to MarketingAccount

Add all four models to backend/app/models/__init__.py exports.
```

**2.2 — Pydantic v2 schemas (`backend/app/schemas/marketing.py`)**
```
Create backend/app/schemas/marketing.py with Pydantic v2 schemas.
Follow the existing schema style (model_config, validators, etc).

MarketingAccountRead
  - All readable fields; EXCLUDE access_token and refresh_token
  - Add: is_token_expiring_soon: bool (computed from model)
  - Add: author_urn: str (from model property)
  - Add: account_type_label: str ('Personal Profile' | 'Company Page')

MarketingPostRead
  - All fields including include_image, image_url
  - image_attribution: ImageAttributionSchema | None
  - Read-only: platform_post_id, posted_at, likes, comments, impressions, clicks

ImageAttributionSchema
  - photographer_name: str
  - photographer_url: str
  - unsplash_url: str

MarketingPostCreate
  - platform, post_type, content, hashtags, scheduled_at
  - include_image: bool = True
  - Validators: hashtags must be list of strings starting with '#'

MarketingPostUpdate
  - content: str | None
  - hashtags: list[str] | None
  - scheduled_at: datetime | None
  - include_image: bool | None

MarketingSettingsRead / MarketingSettingsUpdate
  - All fields
  - Update validator: engagement_per_day max 20, post_types_enabled non-empty,
    topics non-empty list

MarketingEngagementRead — read-only log

MarketingAnalyticsSummary
  - total_posts: int
  - total_impressions: int
  - avg_engagement_rate: float
  - top_post: MarketingPostRead | None
```

**2.3 — Plan gating constants**
```
In the plan/feature constants file (wherever plan feature flags are defined in the 
existing codebase), add marketing module limits following the existing pattern:

MARKETING_PLAN_FEATURES = {
  "marketing_visible":        ["agency_small", "agency_medium", "enterprise"],
  "linkedin_connect":         ["agency_small", "agency_medium", "enterprise"],
  "posts_per_week":           {"agency_small": 2, "agency_medium": 5, "enterprise": None},
  "auto_engage":              ["agency_medium", "enterprise"],
  "group_posting":            ["agency_medium", "enterprise"],
  "analytics_retention_days": {"agency_small": 30, "agency_medium": 90, "enterprise": 365},
}

Add helper: get_marketing_limits(tenant_plan: str) -> dict
Returns the applicable limits dict for the given plan string.
```

---

## Phase 3 — LinkedIn OAuth Integration

**Claude CLI session prompt:**
```
You are implementing LinkedIn OAuth 2.0 for the AIRecruiterz Marketing Module.
Stack: FastAPI async, httpx for HTTP calls (the project already uses httpx elsewhere).

IMPORTANT account type rules:
- Platform account: always connects as a company page
- Tenant accounts: personal profile OR company page — passed as account_type param

LinkedIn URN formats:
- Company page:      urn:li:organization:{numeric_id}
- Personal profile:  urn:li:person:{alphanumeric_id}

New env vars (add to .env and Railway):
  LINKEDIN_CLIENT_ID
  LINKEDIN_CLIENT_SECRET
  LINKEDIN_REDIRECT_URI=https://api.airecruiterz.com/api/v1/marketing/linkedin/callback

Look at how other external API services (brightdata.py, scrapingdog.py) are structured
in backend/app/services/ and follow that async httpx pattern.
```

### Tasks

**3.1 — LinkedIn client (`backend/app/services/marketing/linkedin_client.py`)**
```
Create an async LinkedInClient class using httpx.AsyncClient.

Methods (all async):

get_authorization_url(state: str, account_type: str) -> str
  Build LinkedIn OAuth URL with appropriate scopes:
  - personal: r_liteprofile, w_member_social
  - company:  r_liteprofile, w_member_social, r_organization_social, w_organization_social
  Encode account_type inside the state string (sign it as a short JWT or HMAC).

exchange_code_for_tokens(code: str) -> dict
  POST https://www.linkedin.com/oauth/v2/accessToken
  Returns {access_token, refresh_token, expires_in}

refresh_access_token(refresh_token: str) -> dict
  Same endpoint with grant_type=refresh_token

get_personal_profile(access_token: str) -> dict
  GET https://api.linkedin.com/v2/me
  Returns {id, localizedFirstName, localizedLastName}

get_company_pages(access_token: str) -> list[dict]
  GET https://api.linkedin.com/v2/organizationAcls?q=roleAssignee
  Returns [{organizationId, organizationName}, ...]

create_post(access_token: str, author_urn: str, text: str,
            hashtags: list[str], image_url: str | None) -> str
  POST https://api.linkedin.com/v2/ugcPosts
  author_urn is pre-formatted (urn:li:organization:... or urn:li:person:...)
  If image_url is provided:
    1. POST /v2/assets?action=registerUpload to register
    2. GET image bytes from image_url (Unsplash URL), PUT to uploadUrl
    3. Include asset URN in ugcPost media array
  Returns ugcPost URN (platform_post_id)

get_post_stats(access_token: str, post_urn: str) -> dict
  GET https://api.linkedin.com/v2/socialActions/{post_urn}
  Returns {num_likes, num_comments, impressions}
  For company posts also call /v2/organizationalEntityShareStatistics

like_post(access_token: str, actor_urn: str, post_urn: str) -> bool
  POST https://api.linkedin.com/v2/socialActions/{post_urn}/likes

comment_on_post(access_token: str, actor_urn: str, post_urn: str, text: str) -> bool
  POST https://api.linkedin.com/v2/socialActions/{post_urn}/comments

get_groups(access_token: str) -> list[dict]
  GET https://api.linkedin.com/v2/groups

post_to_group(access_token: str, group_id: str, text: str) -> str
  POST https://api.linkedin.com/v2/groups/{group_id}/posts

Custom exceptions (in the same file or a shared exceptions.py):
  LinkedInRateLimitError — raised when X-RateLimit-Remaining == 0
  LinkedInAuthError      — raised on 401 response
All methods: log at DEBUG level, never include tokens in logs.
```

**3.2 — OAuth FastAPI router (`backend/app/routers/marketing_oauth.py`)**
```
Create FastAPI router with prefix /api/v1/marketing, tag "marketing-oauth".
Use the existing JWT dependency (get_current_user / require_role) from the auth router.

POST /accounts/linkedin/connect
  Body: LinkedInConnectRequest(account_type: Literal['personal','company'])
  - Check tenant plan allows linkedin_connect (use get_marketing_limits)
  - Generate state token encoding account_type, store in Redis with 10min TTL
  - Return {"authorization_url": str}

GET /accounts/linkedin/callback
  Query params: code, state
  - Validate state from Redis; extract account_type
  - Exchange code for tokens via LinkedInClient
  - account_type == 'personal':
      get_personal_profile() -> get name + URN
      Upsert MarketingAccount (conflict on tenant_id + platform + account_type)
      Redirect to {FRONTEND_URL}/{locale}/marketing?connected=true
  - account_type == 'company':
      get_company_pages()
      If 1 page: upsert MarketingAccount, redirect to ?connected=true
      If multiple: store tokens in Redis (15min TTL, temp key),
        redirect to {FRONTEND_URL}/{locale}/marketing/linkedin/select-page?token={key}
  - On error: redirect to {FRONTEND_URL}/{locale}/marketing?error=auth_failed

POST /accounts/linkedin/select-page
  Body: SelectPageRequest(temp_token: str, organization_id: str, organization_name: str)
  - Retrieve tokens from Redis
  - Upsert MarketingAccount(account_type='company', linkedin_urn=organization_id)
  - Return {"success": true}

DELETE /accounts/{account_id}
  - Verify account belongs to current tenant
  - Set is_active=False
  - Set all scheduled posts for this account back to status='draft'
  - Return 204

Include this router in backend/app/main.py alongside the other routers.
```

---

## Phase 4 — Unsplash Image Integration

**Claude CLI session prompt:**
```
You are adding Unsplash stock photo integration to the AIRecruiterz Marketing Module.
Stack: FastAPI async, httpx, Redis for caching.
New env var: UNSPLASH_ACCESS_KEY

Unsplash API terms require:
1. attribution stored with every photo used (photographer name + links)
2. trigger_download() called every time a photo is selected for use
3. "Photo by X on Unsplash" displayed in any UI showing the photo

Free tier limit: 50 requests/hour — use Redis caching to stay well within this.

Follow the async httpx service pattern used in brightdata.py and scrapingdog.py.
```

### Tasks

**4.1 — Unsplash client (`backend/app/services/marketing/unsplash_client.py`)**
```
Create async UnsplashClient class using httpx.AsyncClient.

async def search_photo(query: str, orientation: str = 'landscape') -> dict | None
  Cache key: f"unsplash:{hashlib.md5(query.encode()).hexdigest()}"
  Check Redis first — return cached result if present (TTL 1 hour).
  GET https://api.unsplash.com/search/photos
      ?query={query}&orientation={orientation}&per_page=5&client_id={UNSPLASH_ACCESS_KEY}
  Pick best result: highest resolution, landscape/square.
  Cache the result in Redis.
  Return:
  {
    "image_url": photo.urls.regular,        -- 1080px width
    "download_trigger_url": photo.links.download_location,
    "attribution": {
      "photographer_name": photo.user.name,
      "photographer_url":  photo.user.links.html + "?utm_source=airecruiterz&utm_medium=referral",
      "unsplash_url":      "https://unsplash.com/?utm_source=airecruiterz&utm_medium=referral"
    }
  }
  Return None if results list is empty.
  Raise UnsplashRateLimitError on 429.

async def trigger_download(download_location_url: str) -> None
  GET {download_location_url}?client_id={UNSPLASH_ACCESS_KEY}
  Required by Unsplash ToS every time a photo is used.
  Swallow all exceptions — log warning only, never propagate.
```

**4.2 — Image query helper**
```
Create backend/app/services/marketing/image_query.py

def generate_image_search_query(post_type: str, topic: str) -> str
  Rule-based — no AI call. Returns 2-4 word Unsplash search term.

  Mapping:
  'thought_leadership' -> extract 2 key nouns from topic string
                          e.g. "AI recruitment" -> "recruitment technology"
  'industry_stat'      -> "business data analytics"
  'success_story'      -> "team success collaboration"
  'tip'                -> extract topic keywords, e.g. "job interview tips"
  'poll'               -> "business decision survey"
  'carousel'           -> "modern office workspace"

  Simple keyword extraction: split topic on spaces, take first 2 meaningful words,
  append a context word based on post_type.
```

---

## Phase 5 — Content Generation Engine

**Claude CLI session prompt:**
```
You are implementing AI content generation for the AIRecruiterz Marketing Module.
Stack: FastAPI async, existing AI provider facade at backend/app/services/ai_provider.py.
Use the existing ai_provider.py pattern to call Claude Sonnet — do NOT call 
the Anthropic SDK directly. Follow the same prompt/response pattern used in 
talent_scout.py or resume_screener.py.

Unsplash helpers from Phase 4 are complete — import and call them from this service.
```

### Tasks

**5.1 — Content generator (`backend/app/services/marketing/content_generator.py`)**
```
Create MarketingContentGenerator class (async methods throughout).

async def generate_post(
    settings: MarketingSettings,
    account: MarketingAccount,
    post_type: str,
    topic: str
) -> dict

Steps:
1. Build prompt per Section 25.3 of the spec:
   - Substitute account.account_name, settings.target_audience, settings.tone,
     post_type, topic, length_guideline (see below), hashtag_count
   - length_guideline by post_type:
       thought_leadership -> "150-200 words"
       industry_stat      -> "80-100 words"
       success_story      -> "120-150 words"
       tip                -> "100-120 words"
       poll               -> "30-40 words (question only)"
       carousel           -> "5 slide titles with one sentence each"
   - hashtag_count: 5 for thought_leadership/success_story, 3 for others

2. Call ai_provider.generate(prompt, response_format="json") 
   Expect JSON: {"content": "...", "hashtags": [...]}

3. Validate response:
   - content is non-empty string
   - hashtags is list of strings, each starts with '#'
   - content does not start with "I " (first word)
   - content does not contain any of: "game-changer", "excited to share",
     "thrilled", "delighted"
   Raise ContentGenerationError(detail: str) if any check fails.

4. If settings.include_images is True:
   - query = generate_image_search_query(post_type, topic)
   - result = await UnsplashClient().search_photo(query)
   - If result: fire-and-forget trigger_download (use asyncio.create_task)
   - image fields = result values, or all None if result is None or rate limited

5. Return {
     content, hashtags,
     image_search_query, image_url, image_attribution  <- None if no image
   }

def get_next_topic(settings: MarketingSettings, recent_posts: list[MarketingPost]) -> str
  Exclude topics used in posts created within last 14 days.
  Rotate through remaining topics.
  Fall back to random.choice(settings.topics) if all recently used.

def get_next_post_type(settings: MarketingSettings, recent_posts: list[MarketingPost]) -> str
  Round-robin through settings.post_types_enabled.
  Never repeat the same type as the most recent post.
```

---

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

## Phase 8 — Frontend: Tenant Marketing Dashboard

**Claude CLI session prompt:**
```
You are building the tenant-facing Marketing dashboard for AIRecruiterz.
Stack: Next.js 16 TypeScript App Router, Tailwind CSS.
i18n routing: all pages under /[locale]/ — e.g. /en/marketing.
Match the existing sidebar layout, tab navigation component, and design system exactly.
Look at /[locale]/candidates or /[locale]/jobs for the tab+sidebar pattern to copy.
All Phase 7 API routes are available.
```

### Tasks

**8.1 — Sidebar entry & plan gate**
```
Add "Marketing" to the tenant sidebar component.
- Visible only for plans: agency_small, agency_medium, enterprise
- Icon: Megaphone (match existing icon library and size)
- Route: /[locale]/marketing
- trial / recruiter plans: show entry greyed-out with a lock icon
  Tooltip on hover: "Available from Agency Small plan — upgrade to access"
```

**8.2 — Page layout with tabs**
```
Create app/[locale]/marketing/page.tsx

5 tabs: LinkedIn Account | Settings | Content Calendar | Post Queue | Performance

Use the existing tab component. Default tab: "LinkedIn Account".
Support ?tab= query param for deep-linking (e.g. from notification emails).
Fetch tenant plan on load — pass to child components for plan-gated UI sections.
```

**8.3 — LinkedIn Account tab**
```
Create components/marketing/LinkedInAccountTab.tsx

Not connected state:
  Two CTA buttons: "Connect Personal Profile" and "Connect Company Page"
  Each calls POST /api/v1/marketing/accounts/linkedin/connect {account_type}
  then window.location = response.authorization_url

Company page selector page (app/[locale]/marketing/linkedin/select-page/page.tsx):
  Fetch available pages using the ?token= query param.
  Show radio list of company page names.
  "Connect this page" -> POST /api/v1/marketing/accounts/linkedin/select-page
  On success: redirect to /[locale]/marketing?connected=true

Connected state:
  Card per connected account:
    - Badge chip: "Personal Profile" or "Company Page"
    - Account name (bold)
    - Status chip: Active (green) / Expiring Soon (amber, < 7 days) / Expired (red)
    - Token expiry date in locale format
    - "Reconnect" button (if expired/expiring) | "Disconnect" button (confirm dialog)
  "Add account" button if both types not yet connected.

On page load with ?connected=true: show success toast, clean URL.
On page load with ?error=auth_failed: show error banner with "Try again" button.
```

**8.4 — Settings tab**
```
Create components/marketing/SettingsTab.tsx

Form fields (all from Section 25.6 of spec):
  Target audience:         Textarea (placeholder: "e.g. CTOs and HR Directors at Sydney tech companies")
  Agency specialisation:   Text input
  Posting frequency:       Radio group: Daily / Twice a week / Weekly
  Preferred posting time:  Time picker — display in browser local time,
                           store/send as UTC (show "Times are in UTC" note)
  Tone:                    Segmented control: Professional | Conversational | Bold | Educational
  Topics:                  Tag input — user types to add chip, clicks × to remove
  Post types enabled:      Checkbox group, one per type with short description
  Include images:          Toggle — "Attach a Unsplash stock photo to each post"
  Auto-engage:             Toggle
                           If plan doesn't allow: show lock icon + 
                           "Available on Agency Medium and above" label, disable toggle
  Max engagements/day:     Number slider 5–20 (hidden when auto-engage off)
  Content approval:        Toggle — default ON
                           Helper text below: "When on, posts are saved as drafts for 
                           you to review before they go live. Recommended."

On save: PATCH /api/v1/marketing/settings
Show save confirmation toast. Warn "Unsaved changes" if navigating away.
```

**8.5 — Content Calendar tab**
```
Create components/marketing/ContentCalendarTab.tsx

Weekly grid layout:
  7 columns (Mon–Sun), time-slot rows (show slots with posts; collapse empty hours)
  Each post renders as a card at its scheduled_at time slot:
    - post_type badge (colour-coded: thought_leadership=blue, stat=green, etc.)
    - First 60 characters of content
    - Status chip (Draft=amber, Scheduled=blue, Posted=green, Failed=red)
    - Small image thumbnail if post.image_url set

Click card -> open PostDrawer (right-side panel):
  - Full content (editable <textarea> if status in ['draft','scheduled'])
  - Hashtag chips display
  - If image: show preview image with attribution line below:
      "Photo by [photographer_name link] on [Unsplash link]"
      (REQUIRED by Unsplash ToS — must always be shown)
  - "Include image" toggle (per-post) — calls PATCH post with include_image
  - Approve button (if status='draft') -> POST /approve -> update UI optimistically
  - Reject button (if status='draft') -> POST /reject
  - Save button (if content edited)
  - Delete button (confirm dialog)

"Generate Post" floating button:
  Calls POST /api/v1/marketing/posts/generate
  On response: add post to calendar, open drawer in draft state

Week navigation: < Previous | This Week | Next > buttons
```

**8.6 — Post Queue tab**
```
Create components/marketing/PostQueueTab.tsx

Table columns:
  Scheduled | Post Type | Platform | Status | Image | Content Preview | Actions

Filter bar:
  Status dropdown (All / Draft / Scheduled / Posted / Failed)
  Date range picker
  Platform filter (show only if multiple platforms connected)

Row actions:
  draft:     ✓ Approve (green) | ✗ Reject (red)
  scheduled: ✏ Edit (inline textarea + include_image row toggle) | 🗑 Delete
  failed:    ↺ Retry (re-sets status='scheduled') | 🗑 Delete
  posted:    (read-only)

Image column:
  - Thumbnail if image_url set + include_image=True
  - Camera-off icon if include_image=False
  - Click thumbnail: modal with full image + attribution (photographer name + Unsplash link)

Pagination: 20 rows per page with page controls.
```

**8.7 — Performance tab**
```
Create components/marketing/PerformanceTab.tsx

Summary cards row:
  Total Posts This Month | Total Impressions | Avg Engagement Rate | Best Post preview

Line chart — Impressions over time:
  Toggle: 30 days / 90 days / 1 year
  agency_small: show "Upgrade for extended history" overlay on 90-day/1-year tabs
  Use the existing chart library already in the project (recharts or chart.js)

Bar chart — Engagement by post type:
  Grouped bars: impressions + (likes + comments) per post_type

Top Posts table (top 5 by impressions):
  Date | Type | Image thumb | Preview | Impressions | Likes | Comments | Eng. Rate
  Click row -> opens PostDrawer (same component as Calendar tab)

Data: GET /api/v1/marketing/analytics + /analytics/summary
```

---

## Phase 9 — Super Admin Marketing Dashboard

**Claude CLI session prompt:**
```
You are building the Super Admin marketing dashboard at /super-admin/marketing.
Match the existing super admin panel UI patterns in app/super-admin/ exactly.
The platform account always uses a LinkedIn company page.
Reuse the marketing tab components from Phase 8 with an isPlatformAdmin prop 
where needed to scope API calls and show additional controls.
```

### Tasks

**9.1 — Nav + layout**
```
Add "Marketing" to the super admin sidebar.
Create app/super-admin/marketing/page.tsx with 5 tabs:
  Platform Account | Content Calendar | Post Queue | Performance | Settings

Content Calendar, Post Queue, and Performance reuse Phase 8 components 
with isPlatformAdmin=true (scopes to tenant_id=null API calls).
```

**9.2 — Platform Account tab**
```
Top half: Connect the AIRecruiterz LinkedIn company page.
  Same LinkedInAccountTab component, account_type hardcoded to 'company'.
  No "Connect Personal Profile" option here.

Bottom half: Tenant accounts table
  Columns: Tenant Name | Plan | Account Name | Type | Status | Posts This Month | Last Post | Actions
  Actions: "View Posts" (link to post list filtered to that tenant) | "Disconnect" (confirm)
  Sortable columns. Search by tenant name. Paginated 25/page.
```

**9.3 — Settings tab**
```
Reuse SettingsTab component with isPlatformAdmin=true, plus additional fields:
  - requires_approval: toggle (always visible, controls platform default)
  - "Marketing module active" master on/off toggle
    On toggle OFF: confirmation modal —
    "This will pause all platform scheduled posts. Are you sure?"
    Calls POST /api/v1/marketing/toggle {is_active: false/true}
```

**9.4 — Post Queue with approval workflow**
```
Reuse PostQueueTab component with isPlatformAdmin=true, plus:
  - "Pending Approval" banner when draft_count > 0:
    "You have {N} posts waiting for review"  [Review Now] button -> filters to Draft
  - Checkbox per draft row + "Approve Selected ({n})" bulk action button
  - After approve/reject: optimistic row removal + undo toast (5 second window)
    On undo: revert status locally, call reject/un-approve endpoint
```

---

## Phase 10 — Testing

**Claude CLI session prompt:**
```
You are writing tests for the AIRecruiterz Marketing Module.
Stack: pytest + pytest-asyncio + httpx (for FastAPI route tests).
Follow existing test patterns in backend/tests/ — look at conftest.py for 
fixtures, async session setup, and factory patterns.
Mock all external HTTP calls (LinkedIn, Unsplash, AI provider).
Use pytest-mock / unittest.mock for service mocking.
```

### Tasks

**10.1 — Model & encryption tests (`backend/tests/unit/test_marketing_models.py`)**
```
- set_encrypted_tokens() -> stored value != plaintext original
- get_decrypted_tokens() -> round-trips back to original values
- is_token_expiring_soon(24) -> True when expires_in < 24h, False otherwise
- author_urn property -> correct urn:li:organization:... for account_type='company'
- author_urn property -> correct urn:li:person:... for account_type='personal'
- UNIQUE constraint (tenant_id, platform, account_type) -> raises IntegrityError on duplicate
- UNIQUE constraint on marketing_engagement -> raises IntegrityError on re-engagement
```

**10.2 — Unsplash client tests (`backend/tests/unit/test_unsplash_client.py`)**
```
- search_photo() -> returns dict with correct keys and attribution structure
- search_photo() -> returns None when API response has empty results list
- search_photo() -> returns cached result on second identical call (assert 1 HTTP call total)
- trigger_download() -> calls the correct URL
- trigger_download() -> does not raise when request fails (swallows exception)
- UnsplashRateLimitError raised on 429 response
Mock all HTTP with respx (async httpx mock library).
```

**10.3 — Content generator tests (`backend/tests/unit/test_content_generator.py`)**
```
- generate_post() -> calls ai_provider with prompt containing correct length_guideline
- generate_post() -> raises ContentGenerationError when content starts with "I "
- generate_post() -> raises ContentGenerationError when banned phrase present
- generate_post() -> populates image fields when settings.include_images=True and Unsplash returns result
- generate_post() -> image fields all None when settings.include_images=False
- generate_post() -> image fields all None when Unsplash returns None (no error raised)
- get_next_topic() -> skips topics used in last 14 days
- get_next_post_type() -> never returns same type as most recent post
Parameterise across all 6 post_types. Mock ai_provider and UnsplashClient.
```

**10.4 — LinkedIn client tests (`backend/tests/unit/test_linkedin_client.py`)**
```
- create_post() -> sends correct ugcPosts JSON payload with organization URN
- create_post() -> registers image asset and includes asset URN when image_url provided
- create_post() -> sends text-only ugcPost when image_url=None
- get_authorization_url() -> includes r_organization_social scope for 'company' type
- get_authorization_url() -> does NOT include organization scopes for 'personal' type
- refresh_access_token() -> returns dict with new tokens
- LinkedInRateLimitError raised when X-RateLimit-Remaining=0 header present
- LinkedInAuthError raised on 401 response
Mock all HTTP with respx.
```

**10.5 — Celery task tests (`backend/tests/unit/test_marketing_tasks.py`)**
```
- generate_and_schedule_posts -> creates post with status='draft' (not 'scheduled')
- generate_and_schedule_posts -> skips account that already has a post today
- generate_and_schedule_posts -> skips when weekly post limit reached for plan
- publish_scheduled_posts -> sets status='posted' and saves platform_post_id on success
- publish_scheduled_posts -> passes image_url when post.include_image=True
- publish_scheduled_posts -> passes image_url=None when post.include_image=False
- publish_scheduled_posts -> extends scheduled_at by 2 hours on LinkedInRateLimitError
- publish_scheduled_posts -> sets status='failed' when retry_count reaches 3
- auto_engage -> stops when engagement_per_day limit reached
- refresh_linkedin_tokens -> sends email when token refresh fails
Use Celery task .apply() in eager mode. Mock LinkedInClient and ai_provider.
```

**10.6 — API route tests (`backend/tests/integration/test_marketing_routes.py`)**
```
Use httpx AsyncClient with FastAPI test app and async DB session.

- trial / recruiter plan -> 403 on GET /marketing/settings
- agency_small -> 200 on GET /marketing/settings
- agency_small -> 422 when trying to set auto_engage=True
- agency_small -> analytics date range clipped to 30 days (data before cutoff is empty)
- POST /marketing/posts/generate -> returns 201 with draft post + image_url populated
- POST /marketing/posts/generate -> returns 201 with draft post, image fields null when Unsplash fails
- POST /marketing/posts/{id}/approve -> status becomes 'scheduled'
- PATCH /marketing/posts/{id} with include_image=false -> saved correctly
- POST /marketing/toggle -> flips settings.is_active, returns updated settings
- Tenant A cannot access Tenant B's posts (RLS / 404)
```

---

## Phase 11 — Configuration & Deployment

**Claude CLI session prompt:**
```
You are finalising deployment configuration for the AIRecruiterz Marketing Module.
Update .env.example, Railway config notes, docker-compose (if used), and SPEC.md 
Section 20 (Environment Variables) to document the new variables.
```

### Tasks

**11.1 — Environment variables**
```
Add to backend/.env.example and update SPEC.md Section 20:

# LinkedIn OAuth — register at developer.linkedin.com
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=https://api.airecruiterz.com/api/v1/marketing/linkedin/callback

# Unsplash — register at unsplash.com/developers  
UNSPLASH_ACCESS_KEY=

Document in comments:
LinkedIn Developer App requirements:
  - Products: Sign In with LinkedIn, Share on LinkedIn, Marketing Developer Platform
  - Redirect URIs: prod URL + http://localhost:8000/api/v1/marketing/linkedin/callback
  - Must be admin of the company page used for the platform account

Unsplash plan:
  - Free tier: 50 requests/hour (Redis caching keeps well within this)
  - Production tier needed at scale — requires Unsplash manual approval
  - Attribution MUST be displayed everywhere a photo appears (ToS requirement)
```

**11.2 — Celery queue configuration**
```
In Railway worker config and any local docker-compose:

Add a dedicated marketing worker:
  celery -A app.tasks.celery_app worker -Q marketing --concurrency=1 --loglevel=info

Concurrency MUST be 1 for the marketing queue.
The auto_engage task sleeps 2-5 minutes between actions by design.
Increasing concurrency will cause LinkedIn rate limit violations.

Ensure the main worker also processes the 'default' queue (unchanged).
Update railway.toml with the new worker service if not already structured that way.
```

**11.3 — Unsplash attribution note in README/SPEC**
```
Add to project README and/or SPEC.md:

IMPORTANT — Unsplash Attribution (ToS Requirement)
Every UI component that renders a post image MUST display:
  "Photo by [photographer_name] on Unsplash"
with photographer_url and unsplash_url as clickable links.

The image_attribution JSONB on MarketingPost contains all required values.

Applies to: Content Calendar cards, Post Queue rows, Analytics top-posts table,
the post drawer/modal, and any email notification showing a post preview.

Failure to display attribution violates Unsplash ToS and will result in 
API key revocation.
```

---

## Implementation Order Summary

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

---

*Generated from Section 25 of the AIRecruiterz product spec (SPEC.md v3.0) — v3, correct tech stack applied throughout.*
