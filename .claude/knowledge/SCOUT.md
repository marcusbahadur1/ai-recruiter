# Talent Scout Domain

5-stage pipeline: discover → enrich → score → email → outreach.
Each stage is a Celery task that queues the next on success.

---

## Stage 1: discover_candidates

**Trigger**: Queued at chat payment confirmation.
**Idempotency**: `if existing_count >= job.candidate_target: return`
- Build SERP queries (`TalentScoutService.build_search_queries`):
  - `onsite/hybrid`: `{title} site:linkedin.com/in {city}` per nearby city
  - `remote`: `{title} site:linkedin.com/in {country major cities}`
  - `remote_global`: `{title} site:linkedin.com/in` (no location filter)
- ScrapingDog SERP API, up to 10 pages/query, dedup by LinkedIn URL
- `CREATE Candidate(status=discovered)` — each committed atomically
- Queue `enrich_profile` per candidate. Retry: max 20, 30s→1h backoff.

## Stage 2: enrich_profile

**Idempotency**: `if status != "discovered": return`
- BrightData API → extract company, location, experience_years
- `status=profiled`, queue `score_candidate`
- Private profiles return `{}` — treated as success (see FRAGILE_ZONES F3)

## Stage 3: score_candidate

**Idempotency**: `if status != "profiled": return`
- `AIProvider.complete_json()` → `{score: 1-10, reasoning, strengths[], gaps[]}`
- `status = passed` if `score >= job.minimum_score` else `failed`
- Queue `discover_email` if passed. Retry: unlimited for 429/529 (300s); max 20 others.

## Stage 4: discover_email

**Idempotency**: if email set, trigger next if needed and return.
- Provider order: Apollo → Hunter → Snov → EmailDeductionService
- Skip provider if tenant's API key not set
- If found: queue `send_outreach`. If not: `status=failed`.

## Stage 5: send_outreach

**Idempotency**: `if outreach_email_sent_at is not None: return`
- `AIProvider.complete_json()` → `{subject, body}` (hyper-personalized)
- HTML + unsubscribe link `/unsubscribe/{candidate_id}` → SendGrid
- If `EMAIL_TEST_MODE=true`: redirect to `EMAIL_TEST_RECIPIENT`
- Retry: unlimited for 429/529; max 20 others.

## Candidate Status Flow

`discovered → profiled → passed → emailed` or `→ failed`

## Key Job Config

- `candidate_target` (default 20), `minimum_score` (default 6)
- `outreach_email_prompt`, `evaluation_prompt` (custom AI prompts)

## Audit Events

`scout.candidate_discovered`, `scout.profile_enrichment_*`, `scout.scoring_*`, `scout.email_found_{source}|not_found`, `scout.outreach_email_sent|failed`, `system.task_failed_permanent`
