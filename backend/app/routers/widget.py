"""Public chat widget endpoint.

GET  /widget/{slug}/chat  — public, rate-limited, RAG-backed chat for firm websites.

The widget is embedded on the recruitment firm's own website via a JS snippet.
It is scoped by tenant slug (public, no auth required).  Rate limiting is applied
per IP address to prevent abuse.
"""

import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tenant import Tenant
from app.services import rag_pipeline
from app.services.ai_provider import AIProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/widget", tags=["widget"])

# ── Simple in-memory rate limiter ─────────────────────────────────────────────
# 20 requests per minute per IP.  In production use Redis + a sliding window.
_RATE_LIMIT_REQUESTS = 20
_RATE_LIMIT_WINDOW = 60  # seconds
_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_lock = Lock()


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if IP has exceeded the per-minute request budget."""
    now = time.monotonic()
    with _rate_lock:
        timestamps = _rate_store[ip]
        # Evict timestamps outside the current window.
        _rate_store[ip] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
        if len(_rate_store[ip]) >= _RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — please try again shortly",
            )
        _rate_store[ip].append(now)


# ── Schemas ───────────────────────────────────────────────────────────────────

class WidgetChatRequest(BaseModel):
    message: str
    conversation_history: list[dict[str, str]] = []  # [{role, content}, ...]


class WidgetChatResponse(BaseModel):
    reply: str
    tenant_name: str


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/{slug}/chat", response_model=WidgetChatResponse)
async def widget_chat(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WidgetChatResponse:
    """Handle a chat message from the embeddable firm website widget.

    Requires HTTP body passed as query params for GET compatibility with
    EventSource.  For full POST support use POST variant below.
    """
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Use POST /widget/{slug}/chat",
    )


@router.post("/{slug}/chat", response_model=WidgetChatResponse)
async def widget_chat_post(
    slug: str,
    body: WidgetChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WidgetChatResponse:
    """Process a chat message for the firm's public website widget.

    Pipeline:
    1. Resolve tenant by slug.
    2. Rate-limit by client IP.
    3. Embed the question → cosine search rag_documents → inject top-5 chunks.
    4. Call Claude/OpenAI via AIProvider facade with RAG context.
    5. Return AI reply.
    """
    # 1. Resolve tenant.
    result = await db.execute(
        select(Tenant).where(
            Tenant.slug == slug.lower(),
            Tenant.is_active.is_(True),
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    # Verify plan includes Chat Widget.
    if tenant.plan not in ("agency_small", "agency_medium", "enterprise"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat widget not available for this firm",
        )

    # 2. Rate limit.
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # 3. RAG retrieval.
    context_chunks = await rag_pipeline.query(
        db=db,
        tenant_id=tenant.id,
        question=body.message,
        top_k=5,
        tenant=tenant,
    )

    # 4. Build prompt with RAG context.
    rag_context = "\n\n---\n\n".join(context_chunks) if context_chunks else ""

    system_prompt = (
        f"You are a helpful assistant for {tenant.name}, a recruitment firm. "
        "Answer questions from website visitors about the firm, its services, "
        "open positions, and how to apply. Be friendly, professional, and concise.\n\n"
    )
    if rag_context:
        system_prompt += (
            "Use the following information about the firm to answer accurately:\n\n"
            f"{rag_context}\n\n"
            "If the answer is not in the provided information, say so politely and "
            "suggest contacting the firm directly."
        )
    else:
        system_prompt += (
            "No specific firm information is available yet. "
            "Advise visitors to contact the firm directly for details."
        )

    # Build prompt from conversation history + current message.
    history_lines: list[str] = []
    for turn in body.conversation_history[-6:]:  # last 3 exchanges
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            prefix = "Visitor" if role == "user" else "Assistant"
            history_lines.append(f"{prefix}: {content}")
    if history_lines:
        history_text = "\n".join(history_lines) + "\n\n"
    else:
        history_text = ""

    prompt = f"{history_text}Visitor: {body.message}"

    # 5. Call AI.
    ai = AIProvider(tenant)
    try:
        reply = await ai.complete(
            prompt=prompt,
            system=system_prompt,
            max_tokens=500,
        )
    except Exception as exc:
        logger.error("widget_chat: AI call failed for tenant %s: %s", tenant.id, exc)
        reply = (
            "I'm sorry, I'm unable to respond right now. "
            "Please contact us directly for assistance."
        )

    return WidgetChatResponse(reply=reply, tenant_name=tenant.name)
