# Marketing Domain

LinkedIn OAuth, AI post generation, scheduling, analytics, auto-engagement.
All 11 phases merged to main. Tasks run on `marketing` Celery queue.

---

## Data Models

**MarketingAccount**: `tenant_id` (nullable), `platform="linkedin"`, `account_type=company|personal`, `linkedin_urn`, `access_token/refresh_token` (encrypted Fernet), `token_expires_at`

**MarketingPost**: `account_id`, `content`, `hashtags[]`, `image_url`, `image_attribution` (Unsplash), `scheduled_at`, `posted_at`, `status=draft|scheduled|posted|failed`, `platform_post_id`, `likes/comments/impressions/clicks`

**MarketingSettings**: `post_frequency=daily|twice_weekly|weekly`, `post_time_utc`, `enabled_post_types[]`, `topics[]`, `tone`, `target_audience`, `auto_engage`, `engagement_per_day`, `requires_approval`

**MarketingEngagement**: account + target post + `action_type=like|comment`

---

## LinkedIn OAuth

```
POST /marketing/accounts/linkedin/connect → LinkedIn OAuth redirect URL
GET /marketing/accounts/linkedin/callback?code=...
  → exchange code → encrypt tokens → store in MarketingAccount
```

Personal connect uses OIDC scopes `openid profile w_member_social` and `/v2/userinfo`.
Company page connect still needs MDP scopes/approval.

---

## Content Generation → Scheduling → Publishing

```
[02:00 UTC daily] generate_and_schedule_posts:
  check frequency/no post today/plan limit
  → AIProvider.complete_json() → {content, hashtags, image_query}
  → Unsplash API → image URL + attribution
  → CREATE MarketingPost(status=draft if requires_approval else scheduled)

[every 15 min] publish_scheduled_posts:
  status=scheduled AND scheduled_at<=now
  → refresh token if expiring → LinkedIn API POST
  → status=posted, platform_post_id

[08:00 UTC daily] collect_post_stats:
  → LinkedIn API GET stats → update likes/comments/impressions/clicks
```

Token refresh race condition — see FRAGILE_ZONES F10.

---

## Auto-Engagement

`[10:00 UTC] auto_engage`: if `auto_engage=true`, like+comment up to `engagement_per_day` posts from LinkedIn timeline. Creates `MarketingEngagement` records.

## Approval Workflow

If `requires_approval=true`: posts created as `draft`, tenant approves → `scheduled`, then published normally.
