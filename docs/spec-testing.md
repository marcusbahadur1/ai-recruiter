# Spec §18: Automated Testing Strategy

*Full spec index: see [spec.md](spec.md)*

---

## 18. Automated Testing Strategy

No manual tester. All external APIs mocked. CI via GitHub Actions on every push to main.

### 18.1 Unit Tests (pytest)

- `EmailDeductionService` — all format variants, SMTP mock, rate limiter
- Scoring prompts — construction for various job types and providers
- Title variation generator — AI mock
- Location variation generator — per work_type logic
- Job creation — field extraction, job_ref uniqueness
- Promo code validation — expiry, usage limits
- Stripe webhook handler — each event type
- GDPR erasure — verify PII anonymisation
- Embedding generation — mock embedding API, verify vector stored
- Audit trail — event written after each pipeline step, GDPR redaction, SSE order

### 18.2 Integration Tests (pytest + httpx AsyncClient)

- Full auth flow: signup → login → JWT → protected route
- Job creation via chat session: POST message → mock AI → verify job created
- Talent Scout pipeline: mock ScrapingDog + BrightData + Claude + SendGrid → verify candidate records
- Multi-variation search: verify all title × location query combinations generated
- Resume Screener: mock IMAP + upload → verify Application + embedding created
- Test session: mock Claude → simulate answers → verify scoring
- Interview invitation: token generation, HM email, candidate email on click
- Stripe webhooks: plan changes, credit grants, downgrade
- GDPR delete: verify anonymisation
- RAG pipeline: mock scrape → verify rag_documents + embeddings
- Widget chat: mock RAG retrieval → verify response
- Audit trail: full Scout mock pipeline → verify all event_types in order

### 18.3 End-to-End Tests (Playwright)

- Recruiter posts job via AI chat → verify job in DB
- Evaluation report updates (mock SSE)
- Hiring manager clicks Invite to Interview → confirmation page
- Candidate completes test → test_status updated
- Super admin impersonates tenant → scoped access
- i18n: switch to DE/ES/FR → verify translated UI
- **Smoke test suite** (8 specs, 47 tests) — `e2e/tests/smoke/` — 47/47 passing
- **Production smoke suite** — `e2e/tests/production/` — auto-creates/deletes test account, full chat→job flow

### 18.4 Mock Strategy

| Service | Mock |
|---|---|
| ScrapingDog / BrightData SERP | Fixture JSON with sample organic_results |
| BrightData LinkedIn | Fixture JSON with sample profiles |
| Claude API / OpenAI | respx mock → deterministic JSON (use `using='httpx'`) |
| SendGrid | Mock client capturing emails in-memory |
| Apollo / Hunter / Snov | Fixture JSON with sample enrichment |
| SMTP (deduction) | Mock socket returning 250 |
| IMAP | Mock mailbox with pre-loaded test emails |
| Stripe | stripe-mock or raw POST with test payloads |
| Embedding API | Mock returning deterministic 1536-dim zero vectors |

### 18.5 Test Configuration

- Separate Supabase project for testing (`TEST_DATABASE_URL`)
- Each run creates/destroys own tenant via fixtures
- `pytest-asyncio` for all async tests
- Coverage target: 75% minimum
- GitHub Actions: Python 3.12 on ubuntu-latest
