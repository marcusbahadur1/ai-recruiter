# Knowledge Base Index

Read this first. Select only relevant files — never read all.

## Core Files

| File | Covers | Updated |
|------|--------|---------|
| SYSTEM_MAP.md | Backend layers, modules, services, task files | 2026-05-06 |
| SYSTEM_MAP_FRONTEND.md | Frontend modules, unusual couplings | 2026-05-06 |
| CALL_SEQUENCES.md | Auth, chat 16-step, scout summary, screener summary | 2026-05-06 |
| CALL_SEQUENCES_SERVICES.md | AI provider, billing webhook, RAG, marketing, Celery retry | 2026-05-06 |
| DECISIONS.md | D1–D7: NullPool, two engines, fresh session, payment shortcut, proxy.ts, audit events, sync embeddings | 2026-05-06 |
| DECISIONS_PRODUCT.md | D8–D13: JSONB messages, dashboard URL, super admin probe, relative URLs, unlimited retries, job_ref | 2026-05-06 |
| FRAGILE_ZONES.md | F1–F6: discover loop, AI fallover, BrightData empty, chat persistence, IMAP blocking, RAG threshold | 2026-05-06 |
| FRAGILE_ZONES_B.md | F7–F11: Stripe dedup, promo expiry, asyncio nesting, token race, test expiry | 2026-05-06 |
| BUG_HISTORY.md | B1–B5: DuplicatePreparedStatement, chat loss, BrightData JSON, SendGrid sender, task queue | 2026-05-06 |
| BUG_HISTORY_B.md | B6–B9: model default, IMAP HTML, marketing queue, E2E parallel | 2026-05-06 |

## Domain Files

| File | Covers | Updated |
|------|--------|---------|
| AUTH.md | JWT flow, tenant resolution, plan limits, trial middleware | 2026-05-06 |
| CHAT.md | 4 phases, payment shortcut, streaming, credits, promo codes | 2026-05-06 |
| SCOUT.md | 5-stage pipeline, idempotency, retry, audit events | 2026-05-06 |
| SCREENER.md | IMAP poll, resume scoring, competency test, HM notify | 2026-05-06 |
| BILLING.md | Plans, checkout, webhook events, credit system | 2026-05-06 |
| RAG.md | Scrape, upload, pgvector retrieval, widget | 2026-05-06 |
| AI_PROVIDER.md | Provider routing, failover, models, rate-limit handling | 2026-05-06 |
| CELERY.md | Wrapper pattern, retry backoff, idempotency, Beat schedule | 2026-05-06 |
| DATABASE.md | Two engines, NullPool, tenant scoping, pgvector, encrypted fields | 2026-05-06 |
| MARKETING.md | LinkedIn OAuth, post generation, scheduling, MDP status | 2026-05-06 |

## Task Selection Guide

| Task | Read |
|------|------|
| Chat / job creation | CHAT.md, CALL_SEQUENCES.md, DECISIONS.md |
| Scout pipeline | SCOUT.md, FRAGILE_ZONES.md, BUG_HISTORY.md, CELERY.md |
| Screener / IMAP | SCREENER.md, CELERY.md, DATABASE.md |
| AI provider / models | AI_PROVIDER.md, DECISIONS.md |
| Billing / Stripe | BILLING.md, FRAGILE_ZONES_B.md, BUG_HISTORY.md |
| DB / migrations | DATABASE.md, DECISIONS.md, FRAGILE_ZONES.md |
| Marketing | MARKETING.md, CELERY.md, AI_PROVIDER.md |
| Auth / tenant | AUTH.md, DATABASE.md |
| Frontend / routing | SYSTEM_MAP_FRONTEND.md, DECISIONS_PRODUCT.md |
| New feature | SYSTEM_MAP.md, DECISIONS.md, FRAGILE_ZONES.md |
| Any bug | BUG_HISTORY.md + BUG_HISTORY_B.md + domain file |
