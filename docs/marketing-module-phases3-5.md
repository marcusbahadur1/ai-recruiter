# AI Marketing Module — Phases 3–5: LinkedIn OAuth, Unsplash, Content Generation

*Full index: [marketing-module.md](marketing-module.md)*

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

New env vars (add to .env and Fly.io secrets):
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
