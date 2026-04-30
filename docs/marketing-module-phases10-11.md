# AI Marketing Module — Phases 10–11: Testing & Config/Deployment

*Full index: [marketing-module.md](marketing-module.md)*

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
Update .env.example, Fly.io secrets notes, and SPEC.md 
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
In the Fly.io worker config (`backend/fly.worker.toml`) and any local dev setup:

Add a dedicated marketing worker:
  celery -A app.tasks.celery_app worker -Q marketing --concurrency=1 --loglevel=info

Concurrency MUST be 1 for the marketing queue.
The auto_engage task sleeps 2-5 minutes between actions by design.
Increasing concurrency will cause LinkedIn rate limit violations.

Ensure the main worker also processes the 'celery' queue (see backend/worker.sh).
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
