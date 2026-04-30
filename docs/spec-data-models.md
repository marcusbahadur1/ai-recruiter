# Spec §5: Core Data Models

*Full spec index: see [spec.md](spec.md)*

---

## 5. Core Data Models

### 5.1 Jobs

Key fields: `id`, `tenant_id`, `job_ref` (VARCHAR 20, unique), `title`, `title_variations` (JSONB), `job_type`, `description`, `required_skills` (JSONB), `experience_years`, `salary_min/max`, `location`, `location_variations` (JSONB), `work_type` (onsite\|hybrid\|remote\|remote_global), `tech_stack` (JSONB), `team_size`, `minimum_score` (default 6), `hiring_manager_email/name`, `evaluation_prompt`, `outreach_email_prompt`, `interview_questions_count` (default 5), `custom_interview_questions` (JSONB), `ai_recruiter_config` (JSONB), `status` (draft\|active\|paused\|closed).

### 5.2 Candidates

Key fields: `id`, `tenant_id`, `job_id`, `name`, `title`, `snippet`, `linkedin_url`, `email`, `email_source` (apollo\|hunter\|snov\|deduced\|manual\|unknown), `company`, `location`, `brightdata_profile` (JSONB), `resume_embedding` (vector 1536), `suitability_score` (1–10), `score_reasoning`, `status` (discovered\|profiled\|scored\|passed\|failed\|emailed\|applied\|tested\|interviewed\|rejected), `outreach_email_content`, `gdpr_consent_given`.

### 5.3 Applications

Key fields: `id`, `tenant_id`, `job_id`, `candidate_id` (NULLABLE), `applicant_name/email`, `resume_storage_path`, `resume_text`, `resume_embedding` (vector 1536), `screening_score`, `screening_status` (pending\|passed\|failed), `test_status` (not_started\|invited\|in_progress\|completed\|passed\|failed), `test_score`, `test_answers` (JSONB), `interview_invited`, `email_message_id` (deduplication), `gdpr_consent_given`.

### 5.4 Promo Codes

Fields: `id`, `tenant_id` (NULLABLE = platform-wide), `code` (UNIQUE), `type` (credits\|discount_pct\|full_access), `value`, `expires_at`, `max_uses`, `uses_count`, `is_active`.

### 5.5 Chat Sessions

Fields: `id`, `tenant_id`, `user_id`, `job_id` (NULLABLE — linked once job created), `messages` (JSONB — [{role, content, timestamp}]), `phase` (job_collection\|payment\|recruitment\|post_recruitment), `created_at`, `updated_at`.

> **IMPORTANT**: Chat history is stored server-side in `chat_sessions`, NOT in browser state. Frontend fetches latest session on page load via `GET /chat-sessions/current`.

### 5.6 RAG Documents

Fields: `id`, `tenant_id`, `source_type` (website_scrape\|manual_upload), `source_url`, `filename`, `content_text`, `embedding` (vector 1536), `created_at`.

### 5.7 Job Audit Events

Fields: `id`, `tenant_id`, `job_id`, `candidate_id` (NULLABLE), `application_id` (NULLABLE), `event_type` (VARCHAR 80), `event_category` (talent_scout\|resume_screener\|payment\|system), `severity` (info\|success\|warning\|error), `actor` (system\|recruiter\|candidate\|hiring_manager), `actor_user_id`, `summary` (VARCHAR 500), `detail` (JSONB), `duration_ms`, `created_at`.

> **IMPORTANT**: `job_audit_events` is **append-only**. No UPDATE or DELETE. GDPR erasure **redacts PII within detail JSONB in-place** rather than deleting rows. A Postgres trigger fires `NOTIFY audit_{job_id}` after every INSERT, enabling real-time SSE delivery.
