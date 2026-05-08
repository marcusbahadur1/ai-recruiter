# AI Provider Domain

Provider routing, failover, tenant key override, streaming, JSON mode.

---

## Facade Pattern

All AI calls go through `AIProvider(tenant)` facade — **never call Anthropic or OpenAI SDKs directly from routers or tasks**.

```python
ai = AIProvider(tenant)
result = await ai.complete(prompt, system=system_prompt, max_tokens=2000)
result_json = await ai.complete_json(prompt, system=system_prompt)
async for token in ai.stream_complete(prompt, system=system_prompt):
    yield token
```

---

## Provider Resolution

```
1. tenant.ai_provider → "anthropic" (default) or "openai"
2. API key resolution:
   - If tenant.ai_api_key set → decrypt it (tenant's own key)
   - Else if primary="openai" → settings.openai_api_key
   - Else → settings.anthropic_api_key
3. Primary service: ClaudeAIService or OpenAIService
4. Secondary service: the other one
```

---

## Failover Behavior

```python
try:
    return await primary_svc.complete(...)
except Exception as e:
    logger.warning("primary failed: %s — trying secondary", e)
    return await secondary_svc.complete(...)
```

- Transparent to caller
- Secondary uses platform keys (not tenant's key) regardless of tenant config
- Both fail → raise ValueError → Celery task retries

---

## Default Models

- Anthropic: `claude-sonnet-4-6` (set at Tenant creation and in ClaudeAIService default)
- OpenAI: `gpt-4o`
- Tenants can override `anthropic_model` and `openai_model` in settings

---

## Service Implementations

### `ClaudeAIService` (`services/claude_ai.py`)

```python
complete(prompt, system, max_tokens) → str
stream_complete(prompt, system, max_tokens) → AsyncGenerator[str, None]
complete_json(prompt, system, max_tokens) → dict
```

- Uses Anthropic Messages API
- JSON mode: parses model output as JSON (no native JSON mode in Anthropic API — relies on prompt engineering)
- Streaming: yields raw text deltas from `message_stream`

### `OpenAIService` (`services/openai_ai.py`)

```python
complete(prompt, system, max_tokens) → str
stream_complete(prompt, system, max_tokens) → AsyncGenerator[str, None]
complete_json(prompt, system, max_tokens) → dict
```

- Uses OpenAI Chat Completions API
- JSON mode: can use `response_format={"type": "json_object"}` for reliable JSON

---

## Tenant AI Configuration

Fields on `Tenant`:
- `ai_provider`: `"anthropic"` (default) | `"openai"`
- `ai_api_key`: encrypted tenant API key (optional override)
- `anthropic_model`: e.g. `"claude-sonnet-4-6"`
- `openai_model`: e.g. `"gpt-4o"`

Settings page: `/[locale]/(dashboard)/settings/ai-recruiter`

---

## Rate Limit / Overload Handling

In Celery tasks:
```python
def _is_overload_error(exc) -> bool:
    return any(x in str(exc) for x in ["429", "529", "rate_limit", "overloaded"])

if _is_overload_error(exc):
    raise self.retry(exc=exc, countdown=300)  # 5-min retry, unlimited
```

The facade itself does not retry — Celery's task retry handles it at the outer level.
