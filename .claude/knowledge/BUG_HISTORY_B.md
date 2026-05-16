# Bug History — B6–B10

see BUG_HISTORY.md for B1–B5

---

## B6 — Claude Default Model Too Heavy / Wrong

**Symptom**: High AI costs and slow responses.
**Root cause**: Default `anthropic_model` set to a heavier model (Haiku, then intermediate).
**Fix**: Default switched to `claude-sonnet-4-6` on Tenant creation and in ClaudeAIService.
**Must not revert**: `claude-sonnet-4-6` default. Do not regress to Haiku for production.

---

## B7 — IMAP Resume Extraction Garbled for HTML Emails

**Symptom**: `resume_text` often empty or full of raw HTML tags.
**Root cause**: Email bodies were HTML; code read raw bytes without stripping tags.
**Fix**: Added BeautifulSoup HTML stripping as fallback text extraction in `poll_mailboxes`.

---

## B8 — Marketing Tasks Never Ran

**Symptom**: Marketing Beat tasks scheduled but never executed.
**Root cause**: Celery worker started with `-Q celery` only; marketing tasks on `marketing` queue.
**Fix**: `worker.sh` updated to `-Q celery,marketing`.
**Must not revert**: Worker must always start with both queues.

---

## B9 — E2E Tests Timeout in Parallel

**Symptom**: Playwright E2E suite with `--workers=4` produced 2.1-minute timeouts.
**Root cause**: Parallel workers contested shared auth session and DB state between modules.
**Fix**: Run modules individually with `workers:1`.
**Must not revert**: Never use `--workers > 1` for E2E module runs.

---

## B10 — LinkedIn Personal OAuth Scope Rejected

**Symptom**: Personal LinkedIn connect showed LinkedIn "Bummer" page, then returned to marketing.
**Root cause**: OAuth requested unauthorized legacy `r_liteprofile` scope.
**Fix**: Personal connect uses `openid profile w_member_social` and `/v2/userinfo`.
**Must not revert**: Do not use `/v2/me` or `r_liteprofile` for personal connect.

## B11 — Short Chat Input Triggered Job Summary

**Symptom**: "Need a senior Python developer in Sydney" rendered the job summary.
**Root cause**: Chat prompt/reminders and parser treated any extracted title/skills as summary-ready.
**Fix**: Absolute short-input prompt rule plus parser guard: empty `message` renders summary only for pasted JD or five required fields.
