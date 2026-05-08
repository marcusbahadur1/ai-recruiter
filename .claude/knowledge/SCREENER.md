# Resume Screener Domain

IMAP polling → resume scoring → competency test → HM notification.

Pipeline: `poll_mailboxes → screen_resume → invite_to_test → [submit] → score_test → notify_hiring_manager`
Rejection exits: screen_resume and score_test both queue `send_rejection_email` on fail.

---

## poll_mailboxes (Beat: every 5 min)

- Only runs for tenants with all 4 IMAP fields set: `email_inbox_host/user/password/port`
- Blocking `imaplib` in `run_in_executor()` — see FRAGILE_ZONES F5
- Fetches UNSEEN emails, parses `[JOB-{job_ref}]` from subject → lookup Job
- Deduplicates by `email_message_id` (unique constraint)
- Extracts PDF/DOCX attachment → text, `CREATE Application(screening_status=pending)`
- Failure: IMAP fail (retry), corrupt PDF (skip), job_ref not found (skip)

## screen_resume

**Idempotency**: `if screening_status != "pending": return`
- Embed resume text (OpenAI). RAG query top-5 chunks if knowledge base exists.
- `AIProvider.complete_json()` → `{score, reasoning, strengths[], gaps[]}`
- `screening_status = passed|failed` vs `job.minimum_score`

## invite_to_test

**Idempotency**: `if test_status != "not_started": return`
- `AIProvider.complete_json()` → `interview_questions_count` questions (default 5)
- `CREATE TestSession(questions, expires_at = +72h)`
- `UPDATE Application(test_status=invited, interview_invite_token, expires_at)`
- SendGrid: test link `{frontend_url}/test/{token}` to applicant

## Candidate Test (Public Frontend)

Route: `/[locale]/(public)/test/[token]`
- `GET /screener/test/{token}` → questions
- `POST /screener/test/{token}/submit` → save answers, queue `score_test`
- Check token not expired (unconfirmed — see low-confidence areas)

## score_test

**Idempotency**: `if test_status != "completed": return`
- `AIProvider.complete_json()` → `{score, per_question[], recommended_action}`
- `test_status = passed|failed` → queue `notify_hiring_manager` or `send_rejection_email`

## notify_hiring_manager

- SendGrid to `job.hiring_manager_email` with scores + "Invite to Interview" button (7-day token)
- `Application.interview_invited = true`

## Job Config

`interview_questions_count` (default 5), `custom_interview_questions`, `interview_type` (text|audio), `hiring_manager_email/name`
