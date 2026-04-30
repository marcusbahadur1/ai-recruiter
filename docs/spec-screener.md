# Spec §8: AI Resume Screener Module

*Full spec index: see [spec.md](spec.md)*

---

## 8. AI Resume Screener Module

Sold independently. Candidates from Talent Scout and job boards both email to same tenant inbox.

### 8.1 Mailbox Polling

Celery periodic task every 5 minutes via IMAP4_SSL. Per email:

1. Parse subject for `job_ref` (e.g. "MI0T4AM3 – John Smith Application")
2. Look up job by `job_ref` + `tenant_id`. If not found: discard
3. Extract sender email and name from headers
4. Check for PDF/DOCX attachment. If none: auto-reply requesting resubmission
5. Store resume in Supabase Storage: `{tenant_id}/{job_id}/{applicant_email}/resume.{ext}`
6. Extract text: `pdfplumber` (PDF), `python-docx` (DOCX)
7. Generate embedding from resume text; store in `resume_embedding` (pgvector)
8. Create Application record. If email matches existing Candidate → set `candidate_id`
9. Deduplicate via email Message-ID header
10. Trigger screening task

IMAP config: platform-managed by default. Larger firms can override with own mail server. Audit: `screener.email_received`, `screener.job_ref_matched`, `screener.resume_extracted`, `screener.no_attachment`, `screener.duplicate_application`.

### 8.2 Resume Screening

- Cosine similarity: `resume_embedding` vs job spec embedding (pgvector)
- AI scored with `job.evaluation_prompt` and extracted resume text

Default evaluation prompt:
```
Given this is a {job_type} role requiring {experience_years}+ years with {required_skills},
evaluate the resume. Score 1–10. Return JSON:
{"score": N, "reasoning": "...", "strengths": [...], "gaps": [...], "recommended_action": "pass|fail"}
```

`score >= job.minimum_score` → `screening_status = 'passed'`; else `'failed'` + rejection email. Audit: `screener.screening_passed` / `screener.screening_failed` / `screener.rejection_email_sent`.

### 8.3 AI Competency Test

Test link: `/test/{application_id}/{token}` (public, token-protected). Questions: `job.interview_questions_count` AI-generated (default 5) + `job.custom_interview_questions`. Stored in `test_sessions` table.

Browser chat AI examiner (Claude Sonnet): asks one question at a time, probes with follow-ups if vague, friendly/professional tone, does not reveal correct/incorrect.

Scoring: overall 1–10, per-question assessment, recommended action pass|fail. If passed: `test_status = 'passed'`. If failed: polite rejection email, `test_status = 'failed'`. Audit: `screener.test_invited`, `screener.test_started`, `screener.test_completed`, `screener.test_scored`.

### 8.4 Interview Invitation Workflow

For `test_status = 'passed'`, email hiring manager with candidate summary + **'Invite to Interview' button** → `/actions/invite-interview/{application_id}/{token}`. Token = signed JWT (7-day expiry, one-time-use).

When hiring manager clicks:
1. Token verified (valid, not used, not expired)
2. `interview_invited = TRUE`, `interview_invited_at` stamped
3. Interview invitation email sent to candidate
4. Confirmation sent to hiring manager

Audit: `screener.hm_notified`, `screener.interview_invited`, `screener.interview_invite_expired`.
