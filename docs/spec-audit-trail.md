# Spec §15: Job Audit Trail

*Full spec index: see [spec.md](spec.md)*

---

## 15. Job Audit Trail

### 15.1 Data Model & Rules

See §5.7 for `job_audit_events` table definition. Key rules:
- Append-only — no UPDATE or DELETE ever
- GDPR erasure: redact PII in `detail` JSONB in-place, do not delete the row
- Postgres trigger fires `NOTIFY audit_{job_id}` JSON payload after every INSERT
- RLS: tenant can SELECT their own rows only

### 15.2 Talent Scout Event Types

| event_type | severity |
|---|---|
| scout.job_started | info |
| scout.search_query_built | info |
| scout.serp_call_success | success |
| scout.serp_call_failed | error |
| scout.candidate_discovered | info |
| scout.candidate_duplicate_skipped | info |
| scout.profile_enrichment_started | info |
| scout.profile_enrichment_success | success |
| scout.profile_enrichment_failed | warning |
| scout.scoring_started | info |
| scout.scoring_success | success |
| scout.scoring_failed_threshold | info |
| scout.scoring_error | error |
| scout.email_discovery_started | info |
| scout.email_found_apollo | success |
| scout.email_found_hunter | success |
| scout.email_found_snov | success |
| scout.email_found_deduced | success |
| scout.email_not_found | warning |
| scout.outreach_email_generated | info |
| scout.outreach_email_sent | success |
| scout.outreach_email_failed | error |
| scout.job_completed | success |

### 15.3 Resume Screener Event Types

| event_type | severity |
|---|---|
| screener.email_received | info |
| screener.job_ref_matched | success |
| screener.job_ref_not_found | warning |
| screener.resume_extracted | info |
| screener.no_attachment | warning |
| screener.duplicate_application | info |
| screener.screening_passed | success |
| screener.screening_failed | info |
| screener.rejection_email_sent | info |
| screener.test_invited | success |
| screener.test_started | info |
| screener.test_completed | success |
| screener.test_scored | success |
| screener.hm_notified | success |
| screener.interview_invited | success |
| screener.interview_invite_expired | warning |

### 15.4 Payment & System Events

| event_type | Description |
|---|---|
| payment.credit_charged | Credit deducted for job search |
| payment.promo_code_applied | Promo code applied at checkout |
| system.task_retry | Celery task retrying (attempt N/3) |
| system.task_failed_permanent | Task permanently failed after 3 attempts |
| system.gdpr_erasure | Candidate PII erased |
| system.data_export | Candidate data exported |

### 15.5 Real-Time Delivery

- FastAPI SSE endpoint: `GET /api/v1/jobs/{id}/audit-stream`
- asyncpg `add_listener()` subscribes to Postgres NOTIFY channel `audit_{job_id}`
- DB trigger fires NOTIFY with new event row as JSON after each INSERT
- Client reconnect: send `last_event_id` query param → server replays since that timestamp
- Single SSE stream drives both Evaluation Report table and Audit Trail feed

### 15.6 Audit Trail UI

Job detail page `/jobs/{id}` — tabbed interface: Tab 1 = Evaluation Report (SSE-driven candidate table), Tab 2 = Audit Trail (chronological feed).

Feed: colour-coded severity icon, category badge, timestamp (relative, absolute on hover), summary text, expand chevron → detail JSONB, candidate name → clickable link. Controls: filter by category/severity, search, Export CSV, live pulsing indicator.
