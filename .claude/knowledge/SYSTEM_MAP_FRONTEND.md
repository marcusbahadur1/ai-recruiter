# System Map — Frontend and Unusual Couplings

see SYSTEM_MAP.md for backend module map and layer overview

---

## Frontend Modules (`frontend/`)

| File/Dir | Responsibility |
|----------|---------------|
| `proxy.ts` | i18n routing + rewrites `/api/v1/*` → Fly.io API. **Never delete, never create middleware.ts alongside it** |
| `app/[locale]/(dashboard)/` | Auth-protected pages — Server Components by default, `'use client'` for interactive parts |
| `app/[locale]/(auth)/` | Login, signup, password reset — no JWT required |
| `app/[locale]/(public)/` | Token-protected public pages: test form `/test/[token]`, chat widget |
| `lib/api/client.ts` | Axios + Supabase auth interceptor, 401 → redirect login |
| `lib/api/index.ts` | All API functions: `authApi`, `jobsApi`, `chatApi`, `candidatesApi`, `applicationsApi`, `settingsApi`, `superAdminApi`, `marketingApi`. Chat streaming uses `fetch`+`ReadableStream`, not Axios |
| `lib/api/types.ts` | TypeScript interfaces matching backend Pydantic schemas — must stay in sync |
| `public/widget/widget.js` | Plain JS chat widget at `/widget/widget.js`. No bundler — edit directly |

---

## Unusual Couplings

1. **Payment shortcut in router** — `chat_sessions.py` router contains job creation logic (bypasses AI on "confirm"). Business logic in router, not service layer — intentional, see DECISIONS D4.

2. **Sync embeddings in Celery** — `embeddings.py` has both sync and async clients. Celery always uses sync to avoid "Event loop closed" — see DECISIONS D7.

3. **JSONB messages on ChatSession** — no normalized Message table; entire conversation is one JSONB column. Sessions are always read/written as a unit.

4. **Audit events in separate try/except** — audit failure must not roll back business writes. Committed separately in all task files — see DECISIONS D6.

5. **Super admin via API probe** — `layout.tsx` detects admin by calling `superAdminApi.getStats()` and checking HTTP status. No JWT claim, no env var.

6. **QueryClient per page** — each dashboard page creates `new QueryClient()` at module level. No cross-page cache invalidation — React Query fetches fresh on every page mount.

7. **`hydratedSessionRef` in chat page** — tracks the hydrated session ID so same-session refetches cannot overwrite mid-conversation state, while URL-driven new sessions can hydrate.
