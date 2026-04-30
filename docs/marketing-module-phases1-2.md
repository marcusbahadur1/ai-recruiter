# AI Marketing Module — Phases 1–2: Migrations, Models & Schemas

*Full index: [marketing-module.md](marketing-module.md)*

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
