# Marketing Domain

LinkedIn OAuth, AI post generation, scheduling, analytics, auto-engagement.
All 11 phases merged to main. Showcase page posting added session 43. Tasks run on `marketing` Celery queue.

---

## Data Models

**MarketingAccount**: `tenant_id` (nullable), `platform="linkedin"`, `account_type=company|personal`, `linkedin_urn`, `access_token/refresh_token` (encrypted Fernet), `token_expires_at`, `needs_reconnect` (bool)

**LinkedInPage** (migration 0029): `tenant_id`, `linkedin_account_id` (FK), `page_type=personal|company|showcase`, `page_name`, `page_urn`, `page_id`, `vanity_name`, `logo_url`, `follower_count`, `is_active`, `last_synced_at`. Unique per (tenant_id, page_urn).

**MarketingPost**: `account_id`, `content`, `hashtags[]`, `image_url`, `image_attribution` (Unsplash), `scheduled_at`, `posted_at`, `status=draft|scheduled|posted|partial|failed`, `platform_post_id`, `target_pages` (JSONB array of page URNs), `publish_results` (JSONB: {urn: {status, post_id, posted_at, error}})

**MarketingSettings**: `post_frequency=daily|twice_weekly|weekly`, `post_time_utc`, `tone`, `auto_engage`, `engagement_per_day`, `requires_approval`

**MarketingEngagement**: account + target post + `action_type=like|comment`

---

## LinkedIn OAuth + Page Discovery

```
POST /marketing/accounts/linkedin/connect → OAuth redirect URL
GET  /marketing/accounts/linkedin/callback?code=...
  → exchange code → encrypt tokens → store MarketingAccount
  → sync_linkedin_pages()  ← auto-discovers personal + company + showcase pages
```

Scopes (all in one flow): `openid profile w_member_social w_organization_social`.
Page discovery: `GET /rest/organizationAcls?q=roleAssignee` + `GET /rest/organizations/{id}`.
Showcase pages: detected by `parentOrganization` field in org response.
`w_organization_social`: self-service, no LinkedIn review — see `linkedin_client.py` comment block.

Page management:
  GET  `/marketing/linkedin/pages` — list all pages for tenant
  POST `/marketing/linkedin/pages/sync` — re-discover from LinkedIn API
  PATCH `/marketing/linkedin/pages/:id` — toggle is_active

---

## Content → Scheduling → Publishing

```
[02:00 UTC] generate_and_schedule_posts → create MarketingPost (draft or scheduled)
[every 15m] publish_scheduled_posts:
  → publish_post_to_all_pages(post, db)  ← publish_service.py
     → for each URN in post.target_pages:
          refresh token if expiring within 7 days
          → create_post_v2() → LinkedIn /rest/posts (LinkedIn-Version: 202502)
          → update publish_results[urn]
     → status = posted | partial | failed
[08:00 UTC] collect_post_stats → update likes/comments/impressions/clicks
```

Key service: `backend/app/services/marketing/publish_service.py`
  `sync_linkedin_pages()` — upserts personal + admin pages after OAuth
  `publish_single_page()` — posts to one URN, updates publish_results
  `publish_post_to_all_pages()` — full multi-page flow, sets overall status

Token refresh threshold: 168 hours (7 days). On failure → `needs_reconnect=True`.
LinkedIn API version: `settings.linkedin_api_version` (default `"202502"`). Read from env.

Content tab extra routes:
  PATCH `:id/target-pages` — update which pages a post targets
  POST  `:id/retry-failed` — retry only failed pages (for partial/failed posts)

---

## Auto-Engagement

`[10:00 UTC] auto_engage`: like+comment on LinkedIn timeline. Creates `MarketingEngagement` records.

## Approval Workflow

`requires_approval=true` → posts start as `draft` → tenant approves → `scheduled` → published.
