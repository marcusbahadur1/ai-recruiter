# Spec §21–22: Development Tooling & Security

*Full spec index: see [spec.md](spec.md)*

---

## 21. Development Tooling

**Generation approach:** Claude Code CLI for initial scaffold → PyCharm + Junie for iteration.

**Generation order** (must follow dependency sequence):
1. Database models + Alembic migrations
2. Pydantic v2 schemas
3. FastAPI app factory + config + database session
4. Auth router + Supabase JWT middleware
5. Tenant + Job + Candidate + Application routers
6. AI provider facade (claude_ai.py + openai_ai.py + ai_provider.py)
7. Services: ScrapingDog, BrightData, email discovery, EmailDeductionService
8. Talent Scout service + Celery tasks
9. Resume Screener service + IMAP poller + Celery tasks
10. Audit trail service + Postgres trigger + SSE endpoint
11. RAG pipeline + widget endpoint
12. Stripe webhooks + promo codes
13. Email templates (Jinja2) + SendGrid service
14. Scheduled Celery beat tasks
15. Unit tests for all services
16. Integration tests for all routes
17. Next.js frontend (auth → dashboard → chat → jobs → candidates → applications → settings → super-admin)
18. Playwright E2E tests

---

## 22. Security Considerations

- Tenant API keys encrypted with Fernet before Supabase storage
- Supabase RLS enforced via Alembic migration `0013` — `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on all tables; implicit deny-all for `anon`/`authenticated` roles; `service_role` (backend) has `BYPASSRLS`
- Stripe webhook signatures verified with `stripe.Webhook.construct_event()`
- Test and interview tokens: signed JWTs, 7-day expiry, one-time-use flag
- IMAP credentials stored encrypted, connections use IMAP4_SSL
- EmailDeductionService rate-limited: 5 SMTP checks per minute per domain
- All inputs validated with Pydantic v2
- Public routes (`/test`, `/actions`, `/widget`) token-protected and rate-limited
- CORS: frontend domain only in production
- Audit log records all data access, deletions, exports, impersonations
- `/super-admin` routes require separate `super_admin` role guard
- OAuth tokens (LinkedIn): Fernet-encrypted at application layer; never logged
- Unsplash attribution MUST be displayed everywhere a photo appears (ToS requirement — failure results in API key revocation)
