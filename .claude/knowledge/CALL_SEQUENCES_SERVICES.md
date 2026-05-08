# Call Sequences — AI Provider, Billing, RAG, Marketing, Celery

see CALL_SEQUENCES.md for Auth, Chat, Scout, Screener flows

---

## 5. AI Provider Facade

```
AIProvider(tenant).complete(prompt, system, max_tokens)
  1. primary = tenant.ai_provider (default "anthropic")
  2. api_key = decrypt(tenant.ai_api_key) if set
               else settings.anthropic_api_key | settings.openai_api_key
  3. try primary_svc.complete() → return result
     except → log warning, try secondary_svc.complete()
  4. both fail → raise ValueError → Celery retries
```

---

## 6. Stripe Billing + Webhook

```
POST /billing/create-checkout {plan}
  → stripe.checkout.Session.create(metadata={plan, tenant_id})
  → frontend redirects to stripe.com/pay/{session_id}

[Webhook] checkout.session.completed
  → verify STRIPE_WEBHOOK_SECRET
  → UPDATE Tenant: plan, credits_remaining += N, stripe IDs

[Webhook] invoice.payment_succeeded
  → credits_remaining += plan_credits, subscription_ends_at +30d

[Webhook] invoice.payment_failed → warning email

[Webhook] subscription.deleted → downgrade plan
```
Warning: no event dedup by event.id — see FRAGILE_ZONES F7.

---

## 7. RAG Pipeline

```
POST /rag/scrape {url}
  → crawl4ai.AsyncCrawler (30s) | fallback httpx+BS4
  → chunk ~500 tokens, 100-char overlap
  → generate_embedding() → CREATE RagDocument(tenant_id, content, embedding)

POST /rag/upload (PDF/DOCX/TXT)
  → extract text → same chunk→embed→store flow

POST /rag/query {question}
  → embed question
  → SELECT content FROM rag_documents WHERE tenant_id=?
    ORDER BY embedding <=> query_embedding LIMIT 5
```

---

## 8. Marketing Post Lifecycle

```
[Beat daily 02:00 UTC] generate_and_schedule_posts
  → load MarketingSettings(is_active=true)
  → check frequency / no post today / plan limit
  → generate_post() → CREATE MarketingPost(status=draft|scheduled)

[Beat every 15min] publish_scheduled_posts
  → find status=scheduled AND scheduled_at <= now
  → refresh token if expiring
  → LinkedIn API POST → status=posted, platform_post_id

[Beat daily 08:00 UTC] collect_post_stats
  → LinkedIn API GET stats → update likes/comments/impressions/clicks
```

---

## 9. Celery Task Retry Pattern

```python
@celery_app.task(bind=True, max_retries=20)
def task_name(self, entity_id, tenant_id):
    try:
        asyncio.run(_async_impl(entity_id, tenant_id))
    except Exception as exc:
        if _is_overload_error(exc):   # 429 / 529 / "rate_limit"
            raise self.retry(exc=exc, countdown=300)  # indefinite
        raise self.retry(
            exc=exc,
            countdown=min(2 ** self.request.retries * 30, 3600)
        )  # 30s → 60s → … → 1h cap

# Idempotency at top of _async_impl:
if entity.status != "expected_status":
    return  # skip — safe to retry
```
