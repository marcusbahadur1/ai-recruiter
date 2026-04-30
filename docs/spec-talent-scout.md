# Spec §7: AI Talent Scout Module

*Full spec index: see [spec.md](spec.md)*

---

## 7. AI Talent Scout Module

Background Celery pipeline triggered after job confirmed and paid.

### 7.1 Step 1 — Candidate Discovery

For each `title_variation × location_variation`, call SERP API (up to 100 results per combo). Query format: `"{title_variant} {location_variant} site:linkedin.com/in/"`. Location rules by work_type: onsite/hybrid = nearby cities; remote = major cities same country; remote_global = no filter.

**ScrapingDog API:** `GET https://api.scrapingdog.com/google` — params `api_key`, `query`, `results=10`, `start=0..90`. Cost: 5 credits per request. **BrightData SERP** used when `search_provider = brightdata` or `both`.

Candidate creation: parse name from LinkedIn title, `status = 'discovered'`. Deduplication: skip if `linkedin_url` already exists for this job. Audit: `scout.candidate_discovered` / `scout.candidate_duplicate_skipped`.

### 7.2 Step 2 — LinkedIn Profile Enrichment

Call BrightData **LinkedIn People Profiles** dataset (collect by LinkedIn URL). Store full profile JSON in `candidates.brightdata_profile`. Status → `'profiled'`. On error: flag as `profile_unavailable`, skip scoring. Audit: `scout.profile_enrichment_success` / `scout.profile_enrichment_failed`.

### 7.3 Step 3 — Candidate Scoring

Call AI provider (Claude Sonnet default) with full job spec + candidate BrightData profile. AI returns:
```json
{"score": 8, "reasoning": "2–3 sentence explanation", "strengths": ["..."], "gaps": ["..."]}
```
`score >= job.minimum_score` → status = `'passed'`; else status = `'failed'`. Audit: `scout.scoring_success` / `scout.scoring_failed_threshold` / `scout.scoring_error`.

### 7.4 Step 4 — Email Discovery

Priority order by `tenant.email_discovery_provider`:
- **Apollo.io**: `POST https://api.apollo.io/v1/people/match` — `email_source = 'apollo'`
- **Hunter.io**: email-finder API, store if confidence > 70% — `email_source = 'hunter'`
- **Snov.io**: `POST https://api.snov.io/v1/get-emails-from-names` — `email_source = 'snov'`
- **EmailDeductionService** (always available): domain lookup → SMTP verify formats (firstname.lastname, f.lastname, firstname, flastname) — rate limited: 5 SMTP checks/min/domain; `email_source = 'deduced'` or `'unknown'`

Audit: `scout.email_found_*` / `scout.email_not_found`.

### 7.5 Step 5 — Hyper-Personalised Email Outreach

For each `status = 'passed'` candidate with discovered email:
- AI generates email using `job.outreach_email_prompt` as system prompt
- Includes job ref + application instructions: `"To apply, email resume to {tenant.email_inbox} with subject: {job_ref} – {your_name}"`
- **GDPR**: unsubscribe link in every outreach email
- Sends via SendGrid; status → `'emailed'`

Audit: `scout.outreach_email_sent` / `scout.outreach_email_failed`.

### 7.6 Step 6 — Daily Candidate Summary

Celery beat task, daily 08:00 AEST. Email to `job.hiring_manager_email` for each active job with activity in last 24h. Contents: newly discovered/contacted candidates with scores, candidates who applied, link to evaluation report.
