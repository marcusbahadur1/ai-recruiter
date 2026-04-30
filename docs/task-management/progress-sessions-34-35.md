# PROGRESS — Sessions 34–35 (Most Recent)

*Full index: see [PROGRESS.md](PROGRESS.md)*

---

### Session 35 — AI Chat Test Suite: All 12 Tests Passing

- Rewrote `_JOB_COLLECTION_SYSTEM` prompt in `backend/app/routers/chat_sessions.py` — explicit RULE A/B/C/D structure; AI now always outputs `📋 **Job Summary**` block immediately on JD paste; no acknowledgment phrases before the block
- Fixed `openChatPage()` in `e2e/tests/chat/helpers/chat.ts` — added `minMessages` param; uses `page.waitForFunction` to wait for React Query hydration before asserting message counts
- Fixed T04/T06: pass `minMessages=2` so tests wait for real session messages, not just static welcome element
- Fixed T05: target sidebar `button.btn-ghost` (not header button) for `+ New Job`; assert `toBeLessThanOrEqual(1)` not `toBe(0)` since static welcome `.msg.bot` always present
- Fixed T06: replaced `waitForTimeout(2000)` with `waitForFunction` counting messages after `page.reload()`
- Fixed T02: loop checks `lastMessage` (latest AI response) for HM detection, not `r0.message` (turn 0)
- Fixed T03: `summaryShown` flag tracks block appearance across all turns; no longer re-checks `r0.message` in loop
- Fixed T08 title check: `.toMatch(/cfo|financial|officer|finance/)` handles "CFO" short form
- All credit checks changed to `toBeLessThan(creditsAtStart)` — handles parallel test credit deduction correctly
- Cleared test tenant's custom `recruiter_system_prompt` (was overriding new platform default with old 16-step prompt)
- Closed excess active jobs; upgraded test tenant to `agency_medium` plan (75 jobs, 30 credits) to prevent payment-phase job limit failures when tests run in parallel
- Deployed updated backend to `airecruiterz-api` (Fly.io)
- **Result: 12/12 chat tests passing** — `npm run chat:all` green

### Session 34 — Merge feature/marketing → main + CLAUDE.md reorganisation

- Merged `feature/marketing` (Phases 1–11 complete) into `develop` then `main` for v1.2.0
- Fixed chat "+ New Job" bug: `handleNewJob` now pushes session ID to URL and updates `sessionIdParam` so `GET /current` cannot return an abandoned `job_collection` session
- CLAUDE.md rewritten to ~580 tokens; all .md files reorganised into `docs/`; `docs/dev-setup.md` and `docs/index.md` created
