# Spec §6: AI Recruiter Chat Interface

*Full spec index: see [spec.md](spec.md)*

---

## 6. AI Recruiter Chat Interface

### 6.1 Server-Side Chat History

- History stored in `chat_sessions.messages` JSONB, never in browser
- Frontend loads via `GET /chat-sessions/current` on page load; welcome message renders immediately without waiting for this response
- Each turn: frontend POSTs to `POST /chat-sessions/{id}/message/stream` (SSE), tokens stream in real time; session state saved after stream completes
- **Payment-phase shortcuts**: `confirm` and `cancel` bypass Claude entirely — job creation must not depend on Claude's JSON formatting reliability
- `job_collection` and `payment` phases: `message` field extracted from Claude's JSON in real time via `_extract_streamed_message()`
- `recruitment` / `post_recruitment` phases: raw tokens streamed directly
- 'New Job' button creates fresh chat_session record
- Fallback non-streaming endpoint `POST /chat-sessions/{id}/message` retained for backwards compatibility

### 6.2 Configurable AI Recruiter Instructions

- System prompt stored in `tenants.recruiter_system_prompt` TEXT (NULL = use platform default)
- Platform default is `_JOB_COLLECTION_SYSTEM` in `backend/app/routers/chat_sessions.py`
- Tenant admin edits via Settings > AI Recruiter Prompt (plain-English editor with Reset to Default)
- Reset sets `recruiter_system_prompt = NULL`; backend falls back to hardcoded default
- Phase transitions (job_collection → payment → recruitment → post_recruitment) managed by backend logic, not AI prompt

### 6.3 Chat Flow — Job Creation (16 Steps)

1. Greeting — AI invites recruiter to paste job description or describe role
2. Title extraction — normalised 1–2 word title + display title, confirm both
3. Title variations — 3–5 similar titles suggested, recruiter edits
4. Required Skills — extracted from description, recruiter adds/removes
5. Experience — years confirmed
6. Salary Range — min/max (optional)
7. Location + Work Type — location confirmed, work_type asked, location_variations auto-generated
8. Tech Stack — extracted + recruiter additions
9. Team Size — optional
10. Job Description — clean summary presented for confirmation
11. Hiring Manager — name and email (can be recruiter themselves)
12. Minimum Suitability Score — 1–10 scale explained, threshold set (default: 6)
13. Candidate Count — recruiter sets target, AI explains multi-variation strategy
14. Email Outreach Prompt — default shown, recruiter customises if desired
15. Resume Evaluation Prompt — AI generates default, shown for customisation; also: AI test question count (default 5) + manual questions
16. Confirmation & Payment — structured job summary card, confirm/edit, credit cost displayed, promo code or payment, job created, Scout triggered

### 6.4 Evaluation Report (Real-Time in Chat)

Updated via SSE stream (`GET /jobs/{id}/audit-stream`). Columns: Name, Title, Location, Email (masked if not found), Status, Evaluation Summary (modal), Resume link, LinkedIn link, BrightData Profile modal, Score (N/10), Mailed (Yes/No), Invite Email, Follow-up Email.

### 6.5 Post-Recruitment — Interview Scheduling

Recruiter asks AI to schedule interviews. AI collects: candidate name(s), datetime, meeting link, additional notes. Backend sends calendar invitations.
