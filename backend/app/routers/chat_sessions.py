"""Chat Sessions router — AI Recruiter conversational job-creation interface.

Routes:
  GET  /chat-sessions/current      — return or create the current session
  POST /chat-sessions/{id}/message — one turn of the AI recruiter conversation
  POST /chat-sessions/new          — start a fresh session

The AI guides the recruiter through a 16-step job-creation flow (SPEC §6.3).
Phase transitions (job_collection → payment → recruitment) are managed by
backend logic — the frontend only sees the current phase in the response.
"""

import json
import logging
import random
import re
import string
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jose import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.chat_session import ChatSession
from app.models.job import Job
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.chat_session import ChatSessionListItem, ChatSessionResponse
from app.schemas.common import PaginatedResponse
from app.services.ai_provider import AIProvider
from app.services.audit_trail import AuditTrailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat-sessions", tags=["chat-sessions"])

# ── System prompts ─────────────────────────────────────────────────────────────

_JOB_COLLECTION_SYSTEM = (
    "You are a job data extraction assistant. Your ONLY job is to extract structured fields "
    "from recruiter input and return valid JSON. You do NOT write summaries or format messages "
    "— the system renders the display automatically from the fields you extract.\n\n"

    "=== WHEN THE RECRUITER PASTES A JOB DESCRIPTION ===\n"
    "Extract ALL of the following fields in one pass. Use null for fields not present.\n"
    "For work_type use ONLY: 'onsite', 'hybrid', 'remote', or 'remote_global'.\n"
    "Set message to empty string ''. The display is generated from job_fields automatically.\n\n"

    "=== WHEN THE RECRUITER IS DESCRIBING A ROLE CONVERSATIONALLY ===\n"
    "If no job details yet: set message to 'Please paste your job description or describe the role — "
    "I'll extract all the details automatically.'\n"
    "If you have partial details: set message to '' and extract what you have.\n\n"

    "=== PAYMENT ===\n"
    "Set ready_for_payment=true when the recruiter confirms "
    "(confirm / yes / looks good / proceed / launch / go ahead).\n\n"

    "Return ONLY valid JSON — no preamble, no markdown, nothing outside the JSON object.\n\n"
    'Example: {"message": "", '
    '"job_fields": {"title": "Senior Developer", "title_variations": null, "job_type": null, '
    '"description": null, "required_skills": ["JavaScript", "React"], "experience_years": 5, '
    '"salary_min": null, "salary_max": null, "location": null, '
    '"location_variations": null, "work_type": null, "tech_stack": null, '
    '"team_size": null, "hiring_manager_name": null, "hiring_manager_email": null, '
    '"minimum_score": null, "candidate_target": null, "interview_questions_count": null, '
    '"custom_interview_questions": null, "outreach_email_prompt": null, '
    '"evaluation_prompt": null, "interview_type": "text"}, '
    '"current_step": 1, "ready_for_payment": false}'
)


def _build_payment_system(credits_remaining: int) -> str:
    """Payment phase system prompt — injects the tenant's live credit balance."""
    return (
        "You are an AI Recruiter finalising a confirmed job listing for payment.\n\n"
        f"The recruiter currently has {credits_remaining} credit(s).\n\n"
        "Your FIRST message in this phase MUST output this EXACT block "
        "(substitute the real credit balance — never show a placeholder):\n\n"
        "---\n\n"
        "💳 **Ready to Launch**\n\n"
        "Your job listing is ready. Here's what happens next:\n\n"
        f"**Cost:** 1 credit  \n"
        f"**Credits remaining:** {credits_remaining} credit(s)  \n\n"
        "**To proceed, type one of the following:**\n"
        "- `confirm` — use 1 credit and launch the Talent Scout now\n"
        "- `promo [code]` — apply a promo code (e.g. `promo LAUNCH50`)\n"
        "- `cancel` — go back and edit the job details\n\n"
        "---\n\n"
        "CRITICAL: Output the block above verbatim inside the 'message' JSON field. "
        "Each line MUST be separated by a blank line (\\n\\n) so it renders correctly.\n\n"
        "After outputting the block, wait for the recruiter's response:\n"
        "- If they type 'confirm', 'yes', 'proceed', 'go ahead', 'launch', 'pay', "
        "'looks good', 'no promo code', or any clear affirmative: "
        "set payment_confirmed=true.\n"
        "- If they provide a promo code: set promo_code to the code string.\n"
        "- If they type 'cancel' or 'back': acknowledge and tell them to refresh to "
        "restart the job creation flow.\n\n"
        "Return ONLY valid JSON: "
        '{"message": "<text>", "promo_code": null, "payment_confirmed": false}'
    )


_RECRUITMENT_SYSTEM = (
    "You are an AI Recruiter providing updates on an active job search. "
    "Answer questions about the Scout pipeline, candidate status, screening results, "
    "and test progress. Be helpful, concise, and proactive. "
    "When the recruiter asks about scheduling interviews, help collect: "
    "candidate names, datetimes, meeting link, and notes."
)

_TOKEN_BUDGET = 3_000  # approximate tokens; trigger summarisation above this
_SUMMARY_KEEP_RECENT = 6


# ── Dependency: extract user_id from JWT ──────────────────────────────────────


async def _get_user_id(authorization: Annotated[str, Header()]) -> uuid.UUID:
    """Extract the Supabase Auth user UUID from the JWT sub claim.

    The token is already validated by get_current_tenant; here we just decode
    the claims without signature verification to extract the user id.
    """
    try:
        token = authorization.removeprefix("Bearer ").strip()
        claims = jwt.get_unverified_claims(token)
        return uuid.UUID(str(claims["sub"]))
    except Exception:
        # Fallback — session will be created with a random user_id this turn
        return uuid.uuid4()


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/current", response_model=ChatSessionResponse)
async def get_current_session(
    tenant: Tenant = Depends(get_current_tenant),
    user_id: uuid.UUID = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Return the latest active session for this tenant/user, or create one.

    Active means phase is job_collection, payment, or recruitment.
    """
    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.tenant_id == tenant.id,
            ChatSession.user_id == user_id,
            # Only resume in-progress job creation sessions.
            # recruitment / post_recruitment mean the job was already created —
            # returning to /chat should start a fresh job_collection session,
            # not re-open the old post-creation conversation.
            ChatSession.phase.in_(["job_collection", "payment"]),
        )
        .order_by(ChatSession.updated_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if not session:
        session = await _create_session(db, tenant.id, user_id)

    return ChatSessionResponse.model_validate(session)


@router.post(
    "/new", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED
)
async def new_session(
    tenant: Tenant = Depends(get_current_tenant),
    user_id: uuid.UUID = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Start a fresh chat session in job_collection phase."""
    session = await _create_session(db, tenant.id, user_id)
    return ChatSessionResponse.model_validate(session)


@router.get("", response_model=PaginatedResponse[ChatSessionListItem])
async def list_sessions(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[ChatSessionListItem]:
    """List all chat sessions for the tenant, newest first.

    Filtered by tenant_id only — not by user_id — so the history page shows
    every session regardless of which team member started it, and is not
    broken by the user_id fallback that generates a fresh UUID when JWT
    parsing fails.
    """
    conditions = [
        ChatSession.tenant_id == tenant.id,
    ]

    sessions_result = await db.execute(
        select(ChatSession)
        .where(*conditions)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = list(sessions_result.scalars().all())

    count_result = await db.execute(
        select(func.count()).select_from(ChatSession).where(*conditions)
    )
    total = count_result.scalar_one()

    # Resolve job titles in one query for all sessions that have a job_id
    job_ids = [s.job_id for s in sessions if s.job_id]
    job_titles: dict[uuid.UUID, str] = {}
    if job_ids:
        jobs_result = await db.execute(
            select(Job.id, Job.title).where(Job.id.in_(job_ids))
        )
        for job_id, title in jobs_result.all():
            job_titles[job_id] = title

    items: list[ChatSessionListItem] = []
    for s in sessions:
        msgs = s.messages or []
        user_msgs = [m for m in msgs if m.get("role") == "user"]
        preview = (user_msgs[0]["content"] or "")[:80] if user_msgs else "New session"
        real_msg_count = len(
            [m for m in msgs if m.get("role") in ("user", "assistant")]
        )
        items.append(
            ChatSessionListItem(
                id=s.id,
                phase=s.phase,
                job_id=s.job_id,
                job_title=job_titles.get(s.job_id) if s.job_id else None,
                preview=preview,
                message_count=real_msg_count,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Return a single session by ID (for read-only history view)."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == tenant.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return ChatSessionResponse.model_validate(session)


@router.post("/{session_id}/message")
async def send_message(
    session_id: uuid.UUID,
    body: dict,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """One turn of the AI recruiter conversation.

    Body: ``{"message": "<recruiter text>"}``

    Response::

        {
          "session_id": "...",
          "message": "<AI reply>",
          "phase": "job_collection|payment|recruitment|post_recruitment",
          "job_fields": {...},        # present in job_collection phase
          "payment_confirmed": false  # present in payment phase
        }
    """
    user_text: str = (body.get("message") or "").strip()
    if not user_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="message field required",
        )

    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == tenant.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    messages: list[dict[str, Any]] = list(session.messages or [])
    messages.append(
        {
            "role": "user",
            "content": user_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    messages = await _summarise_if_needed(messages, tenant)

    # ── Server-side shortcuts (bypass AI for unambiguous user intent) ──────────

    # 1. Job summary confirmation — user confirmed the step-16 summary → move to payment
    if session.phase == "job_collection" and _detect_job_summary_confirmation(
        user_text, messages
    ):
        reply_text = _build_payment_block(tenant.credits_remaining)
        job_fields, new_phase, extras = None, "payment", None

    # 2. Payment confirm/cancel — skip the round-trip to Claude
    elif session.phase == "payment" and _detect_payment_intent(user_text) == "confirm":
        # reply_text is a placeholder — updated with job details after _create_job_on_payment
        reply_text = "Payment confirmed! Your job is being created..."
        job_fields, new_phase, extras = None, "recruitment", {"payment_confirmed": True}

    elif session.phase == "payment" and _detect_payment_intent(user_text) == "cancel":
        reply_text = (
            "No problem — your job details are saved. "
            "Start a new session whenever you're ready to re-launch."
        )
        job_fields, new_phase, extras = (
            None,
            "post_recruitment",
            {"payment_confirmed": False},
        )

    else:
        ai_raw = await _call_ai(tenant, session.phase, messages, user_text)
        reply_text, job_fields, new_phase, extras = _parse_ai_response(
            ai_raw, session.phase
        )

    # Persist any newly extracted job fields into the session's hidden metadata entry.
    if job_fields:
        messages = _accumulate_job_fields(messages, job_fields)

    messages.append(
        {
            "role": "assistant",
            "content": reply_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    resolved_phase = new_phase or session.phase

    # ── Payment confirmed — create job, deduct credit, trigger Scout ─────────
    if extras and extras.get("payment_confirmed") and new_phase == "recruitment":
        # Check plan job limit
        plan_job_limit = settings.plan_limits.get(tenant.plan, {}).get("jobs", 0)
        from sqlalchemy import func as _func
        from app.models.job import Job as _Job

        active_jobs_result = await db.execute(
            select(_func.count(_Job.id)).where(
                _Job.tenant_id == tenant.id,
                _Job.status.in_(["active", "paused"]),
            )
        )
        active_jobs_count = active_jobs_result.scalar() or 0

        if active_jobs_count >= plan_job_limit:
            reply_text = (
                f"You've reached your plan limit of {plan_job_limit} jobs per month. "
                "Please upgrade your plan to post more jobs."
            )
            resolved_phase = session.phase  # stay in payment
            extras["payment_confirmed"] = False
            messages[-1] = {
                "role": "assistant",
                "content": reply_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        elif tenant.credits_remaining < 1:
            # Insufficient credits: veto the phase transition and tell the user.
            reply_text = (
                "I'm sorry, you don't have enough credits to start a search. "
                "Please top up your account and try again."
            )
            resolved_phase = session.phase  # stay in payment
            extras["payment_confirmed"] = False
            messages[-1] = {
                "role": "assistant",
                "content": reply_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            print(f"Payment confirmed, creating job for tenant {tenant.id}")
            job = await _create_job_on_payment(db, tenant, messages)
            session.job_id = job.id
            # Replace the placeholder message with job-specific success details.
            location_part = f" in {job.location}" if job.location else ""
            reply_text = (
                f"🎉 Your job is live! The Talent Scout is now searching for "
                f"**{job.title}** candidates{location_part}. "
                f"You'll see candidates appearing in your Evaluation Report shortly.\n\n"
                f"**Job Reference:** `{job.job_ref}`"
            )
            messages[-1] = {
                "role": "assistant",
                "content": reply_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    session.messages = messages
    session.phase = resolved_phase
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()

    response: dict[str, Any] = {
        "session_id": str(session_id),
        "message": reply_text,
        "phase": resolved_phase,
    }
    if extras:
        response.update(extras)
    return response


# ── Streaming endpoint ────────────────────────────────────────────────────────


def _extract_streamed_message(buffer: str) -> tuple[str, bool]:
    """Extract the 'message' field value from a partial JSON buffer.

    Scans the accumulated stream buffer and returns:
      (message_text, is_complete)

    message_text — the unescaped message content seen so far (safe to display)
    is_complete  — True once the closing quote of the field has been found

    Handles standard JSON escape sequences (\\n, \\t, \\", \\\\).
    Stops before an incomplete escape at the end of the buffer so we never
    yield half an escape sequence to the client.
    """
    # Skip any preamble before the JSON object
    json_start = buffer.find("{")
    if json_start < 0:
        return "", False
    buf = buffer[json_start:]

    key_idx = buf.find('"message"')
    if key_idx < 0:
        return "", False

    rest = buf[key_idx + len('"message"'):]
    colon_idx = rest.find(":")
    if colon_idx < 0:
        return "", False

    after_colon = rest[colon_idx + 1 :].lstrip(" \t\n")
    if not after_colon.startswith('"'):
        return "", False

    content = after_colon[1:]  # skip opening quote
    result: list[str] = []
    i = 0
    while i < len(content):
        c = content[i]
        if c == "\\":
            if i + 1 >= len(content):
                break  # incomplete escape at end of buffer — stop here
            nc = content[i + 1]
            result.append(
                {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "r": "\r"}.get(nc, nc)
            )
            i += 2
        elif c == '"':
            return "".join(result), True  # message field complete
        else:
            result.append(c)
            i += 1

    return "".join(result), False


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/{session_id}/message/stream")
async def send_message_stream(
    session_id: uuid.UUID,
    body: dict,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Streaming variant of send_message — returns text/event-stream SSE.

    Events::

        data: {"token": "<text chunk>"}
        data: {"done": true, "phase": "...", "final_message": "...", ...}
        data: {"error": "<message>"}
    """
    user_text: str = (body.get("message") or "").strip()
    if not user_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="message field required",
        )

    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == tenant.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    messages: list[dict] = list(session.messages or [])
    messages.append(
        {
            "role": "user",
            "content": user_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    messages = await _summarise_if_needed(messages, tenant)

    gen = _stream_generator(session, tenant, db, messages, user_text)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_generator(
    session: ChatSession,
    tenant: Tenant,
    db: AsyncSession,
    messages: list[dict],
    user_text: str,
):
    """Async generator powering the SSE streaming endpoint.

    Yields token events as text arrives, then a final done event after the
    session has been persisted.

    Payment-phase shortcuts (confirm/cancel) bypass the AI entirely — the
    same shortcuts as the non-streaming path — so job creation is reliable
    regardless of whether Claude formats its JSON response correctly.

    Persistence uses a fresh AsyncSession with an explicit UPDATE rather than
    relying on the request-scoped `db` session.  After many async yields
    during streaming, the request-scoped session's connection can be in an
    inconsistent state (especially with NullPool), causing the final commit
    to silently skip the UPDATE.  A fresh session bypasses this entirely.
    """
    # ── Server-side shortcuts (payment phase) ─────────────────────────────────
    # Mirror the non-streaming path: bypass the AI for unambiguous payment
    # intents so job creation doesn't depend on Claude's JSON formatting.
    reply_text: str | None = None
    job_fields: dict | None = None
    new_phase: str | None = None
    extras: dict | None = None

    if session.phase == "payment":
        intent = _detect_payment_intent(user_text)
        if intent == "confirm":
            reply_text = "Payment confirmed! Your job is being created..."
            new_phase = "recruitment"
            extras = {"payment_confirmed": True}
        elif intent == "cancel":
            reply_text = (
                "No problem — your job details are saved. "
                "Start a new session whenever you're ready to re-launch."
            )
            new_phase = "post_recruitment"
            extras = {"payment_confirmed": False}

    if reply_text is not None:
        # Shortcut path — stream the reply text as a single token then skip
        # the AI section entirely and fall through to payment processing.
        yield _sse({"token": reply_text})
    else:
        # ── AI streaming path ─────────────────────────────────────────────────
        system = _get_system_prompt(
            session.phase, credits_remaining=tenant.credits_remaining, tenant=tenant
        )
        history = _format_history_for_ai(messages[:-1])
        base_prompt = f"{history}\nRecruiter: {user_text}" if history else user_text
        if session.phase == "job_collection":
            prompt = (
                base_prompt
                + "\n\n[SYSTEM REMINDER: Return ONLY valid JSON. "
                "Extract ALL job fields into job_fields. Set message to empty string '' — "
                "the display summary is generated automatically from the fields. "
                "DO NOT write a summary in the message field. DO NOT ask follow-up questions.]"
            )
        else:
            prompt = base_prompt

        full_buffer = ""
        streamed_up_to = 0  # chars of message text already yielded to client
        ai = AIProvider(tenant)

        try:
            async for token in ai.stream_complete(
                prompt=prompt, system=system, max_tokens=3000
            ):
                full_buffer += token

                if session.phase in ("recruitment", "post_recruitment"):
                    # Plain-text phase — stream raw tokens directly
                    yield _sse({"token": token})
                else:
                    # JSON phase — extract message field in real time
                    msg_text, _ = _extract_streamed_message(full_buffer)
                    if len(msg_text) > streamed_up_to:
                        yield _sse({"token": msg_text[streamed_up_to:]})
                        streamed_up_to = len(msg_text)

        except Exception as exc:
            err = str(exc).lower()
            if (
                "credit balance is too low" in err
                or "insufficient_quota" in err
                or "rate limit" in err
            ):
                provider = getattr(tenant, "ai_provider", "anthropic") or "anthropic"
                detail = (
                    "Your OpenAI account has insufficient credits. "
                    "Please top up at platform.openai.com or switch to Anthropic in Settings."
                    if provider == "openai"
                    else "Your Anthropic account has insufficient credits. "
                    "Please top up at console.anthropic.com or switch to OpenAI in Settings."
                )
                yield _sse({"error": detail})
            else:
                logger.exception("_stream_generator: AI call failed")
                yield _sse({"error": "Something went wrong. Please try again."})
            return

        # Parse the accumulated response for business logic
        reply_text, job_fields, new_phase, extras = _parse_ai_response(
            full_buffer, session.phase
        )

    # ── Accumulate job fields ─────────────────────────────────────────────────
    if job_fields:
        messages = _accumulate_job_fields(messages, job_fields)

    # ── Payment processing ────────────────────────────────────────────────────
    resolved_phase = new_phase or session.phase
    new_job_id = session.job_id  # may be updated below

    if extras and extras.get("payment_confirmed") and new_phase == "recruitment":
        plan_job_limit = settings.plan_limits.get(tenant.plan, {}).get("jobs", 0)
        from sqlalchemy import func as _func
        from app.models.job import Job as _Job

        active_jobs_result = await db.execute(
            select(_func.count(_Job.id)).where(
                _Job.tenant_id == tenant.id,
                _Job.status.in_(["active", "paused"]),
            )
        )
        active_jobs_count = active_jobs_result.scalar() or 0

        if active_jobs_count >= plan_job_limit:
            reply_text = (
                f"You've reached your plan limit of {plan_job_limit} jobs per month. "
                "Please upgrade your plan to post more jobs."
            )
            resolved_phase = session.phase
            extras["payment_confirmed"] = False
        elif tenant.credits_remaining < 1:
            reply_text = (
                "I'm sorry, you don't have enough credits to start a search. "
                "Please top up your account and try again."
            )
            resolved_phase = session.phase
            extras["payment_confirmed"] = False
        else:
            job = await _create_job_on_payment(db, tenant, messages)
            new_job_id = job.id
            location_part = f" in {job.location}" if job.location else ""
            reply_text = (
                f"🎉 Your job is live! The Talent Scout is now searching for "
                f"**{job.title}** candidates{location_part}. "
                f"You'll see candidates appearing in your Evaluation Report shortly.\n\n"
                f"**Job Reference:** `{job.job_ref}`"
            )
            # Commit job creation + credit deduction + audit events via the
            # request-scoped db (they were flushed inside _create_job_on_payment).
            try:
                await db.commit()
            except Exception as _exc:
                logger.exception(
                    "_stream_generator: payment db.commit failed for session %s", session.id
                )
                reply_text = "An error occurred creating your job. Please try again."
                resolved_phase = session.phase
                new_job_id = session.job_id
                extras["payment_confirmed"] = False

    # ── Persist session (fresh session + explicit UPDATE) ─────────────────────
    # We intentionally do NOT reuse the request-scoped `db` here.  After many
    # async yields during streaming the connection managed by `db` may be in an
    # inconsistent state (NullPool behaviour + FastAPI dependency lifecycle),
    # causing the ORM-level commit to silently skip the UPDATE.  An explicit
    # UPDATE through a brand-new AsyncSession is always reliable.
    messages.append(
        {
            "role": "assistant",
            "content": reply_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    from sqlalchemy import update as _update_stmt
    from app.database import AsyncSessionLocal as _ASL

    try:
        async with _ASL() as _save_db:
            await _save_db.execute(
                _update_stmt(ChatSession)
                .where(ChatSession.id == session.id)
                .values(
                    messages=messages,
                    phase=resolved_phase,
                    job_id=new_job_id,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await _save_db.commit()
            logger.debug("_stream_generator: session %s persisted", session.id)
    except Exception as _exc:
        logger.exception(
            "_stream_generator: failed to persist session %s", session.id
        )

    # ── Final done event ──────────────────────────────────────────────────────
    done: dict = {
        "done": True,
        "phase": resolved_phase,
        "final_message": reply_text,
    }
    if extras:
        done.update(extras)
    yield _sse(done)


# ── AI orchestration ──────────────────────────────────────────────────────────


async def _call_ai(
    tenant: Tenant,
    phase: str,
    messages: list[dict[str, Any]],
    latest_user_message: str,
) -> str:
    """Build a prompt from conversation history and call the AI provider."""
    system = _get_system_prompt(
        phase, credits_remaining=tenant.credits_remaining, tenant=tenant
    )
    history = _format_history_for_ai(messages[:-1])  # exclude the turn just added
    base_prompt = (
        f"{history}\nRecruiter: {latest_user_message}"
        if history
        else latest_user_message
    )
    if phase == "job_collection":
        prompt = (
            base_prompt
            + "\n\n[SYSTEM REMINDER: Return ONLY valid JSON. "
            "Your 'message' field MUST begin with '📋 **Job Summary**' if you have job data. "
            "NEVER output 'I've noted', 'I've captured', 'Could you confirm everything looks correct', "
            "or any acknowledgment phrase. Jump straight to the summary block.]"
        )
    else:
        prompt = base_prompt
    ai = AIProvider(tenant)
    try:
        return await ai.complete(prompt=prompt, system=system, max_tokens=3000)
    except Exception as exc:
        err = str(exc).lower()
        if (
            "credit balance is too low" in err
            or "insufficient_quota" in err
            or "rate limit" in err
        ):
            provider = getattr(tenant, "ai_provider", "anthropic") or "anthropic"
            if provider == "openai":
                detail = (
                    "Your OpenAI account has insufficient credits (and the Anthropic fallback also failed). "
                    "Please top up at platform.openai.com or switch your AI provider to Anthropic in Settings."
                )
            else:
                detail = (
                    "Your Anthropic account has insufficient credits (and the OpenAI fallback also failed). "
                    "Please top up at console.anthropic.com or switch your AI provider to OpenAI in Settings."
                )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=detail,
            )
        raise


def _get_system_prompt(
    phase: str, credits_remaining: int = 0, tenant: "Tenant | None" = None
) -> str:
    if phase == "payment":
        return _build_payment_system(credits_remaining)
    if phase in ("recruitment", "post_recruitment"):
        return _RECRUITMENT_SYSTEM
    # Use tenant's custom prompt for job_collection phase if set.
    # Always append the JSON format rules so a custom prompt can't bypass them.
    if tenant and getattr(tenant, "recruiter_system_prompt", None):
        return (
            tenant.recruiter_system_prompt
            + "\n\n"
            + "=== OUTPUT FORMAT (MANDATORY — OVERRIDES ALL OTHER INSTRUCTIONS) ===\n"
            "Return ONLY valid JSON. No preamble, no markdown, no extra text.\n"
            "NEVER say 'I've noted', 'I've captured', 'I've recorded', 'I understand', "
            "'Could you confirm everything looks correct', or any acknowledgment phrase.\n"
            "When you have job data, your 'message' MUST begin immediately with "
            "'📋 **Job Summary**' and include the full block. No text before it.\n"
            'Example: {"message": "📋 **Job Summary**\\n\\n**Title:** ...", '
            '"job_fields": {...}, "current_step": 1, "ready_for_payment": false}'
        )
    return _JOB_COLLECTION_SYSTEM


def _format_history_for_ai(messages: list[dict[str, Any]]) -> str:
    """Convert recent messages to a readable conversation string.

    Skips internal metadata entries (role starts with '_').
    """
    parts = []
    for msg in messages[-20:]:
        if str(msg.get("role", "")).startswith("_"):
            continue
        role = "Recruiter" if msg["role"] == "user" else "AI Recruiter"
        parts.append(f"{role}: {msg['content']}")
    return "\n".join(parts)


def _parse_ai_response(
    raw: str, current_phase: str
) -> tuple[str, dict[str, Any] | None, str | None, dict[str, Any] | None]:
    """Return (reply_text, job_fields, new_phase, extras)."""
    if current_phase == "job_collection":
        return _parse_job_collection(raw)
    if current_phase == "payment":
        return _parse_payment(raw)
    return raw.strip(), None, None, None


def _format_job_summary(fields: dict[str, Any]) -> str:
    """Render a clean, emoji-decorated job summary from extracted job_fields.

    Always called when the AI has extracted job data — the AI's own 'message'
    text is discarded in favour of this deterministic Python rendering so the
    format is guaranteed regardless of which AI model or temperature is used.
    """
    def skills_str(v: Any) -> str:
        if isinstance(v, list):
            return ", ".join(str(x) for x in v if x)
        return str(v) if v else "Not specified"

    work_type_labels = {
        "onsite": "On-site",
        "hybrid": "Hybrid",
        "remote": "Remote",
        "remote_global": "Global Remote",
    }

    title = fields.get("title") or "Not specified"
    location = fields.get("location") or "Not specified"
    work_type = work_type_labels.get(str(fields.get("work_type") or ""), str(fields.get("work_type") or "Not specified"))
    experience = fields.get("experience_years")
    salary_min = fields.get("salary_min")
    salary_max = fields.get("salary_max")
    required_skills = skills_str(fields.get("required_skills"))
    tech_stack = skills_str(fields.get("tech_stack")) if fields.get("tech_stack") else "Not specified"
    hm_name = fields.get("hiring_manager_name") or "Not specified"
    hm_email = fields.get("hiring_manager_email") or "Not specified"
    min_score = fields.get("minimum_score") or 6
    candidates = fields.get("candidate_target") or 20
    description = str(fields.get("description") or "").strip()

    salary_str = "Not specified"
    if salary_min and salary_max:
        salary_str = f"${int(salary_min):,} – ${int(salary_max):,}"
    elif salary_min:
        salary_str = f"${int(salary_min):,}+"
    elif salary_max:
        salary_str = f"Up to ${int(salary_max):,}"

    exp_str = f"{experience}+ years" if experience else "Not specified"
    location_str = f"{location} ({work_type})" if location != "Not specified" else work_type

    lines = [
        "📋 **Job Summary**",
        "",
        f"🎯 **Role:** {title}",
        f"📍 **Location:** {location_str}",
        f"⏱️ **Experience:** {exp_str}",
        f"💰 **Salary:** {salary_str}",
        f"🛠️ **Required Skills:** {required_skills}",
        f"💻 **Tech Stack:** {tech_stack}",
        f"👤 **Hiring Manager:** {hm_name} — {hm_email}",
        f"⭐ **Min Score:** {min_score}/10  |  🎯 **Target Candidates:** {candidates}",
        "",
        "---",
        "",
    ]

    if description:
        lines += ["📝 **About the Role**", "", description, "", "---", ""]

    lines += [
        "Does this look right? Type **confirm** to launch the Talent Scout, or tell me what to change."
    ]

    return "\n".join(lines)


def _parse_job_collection(
    raw: str,
) -> tuple[str, dict[str, Any] | None, str | None, dict[str, Any] | None]:
    try:
        data = json.loads(_extract_json(raw))
        message = str(data.get("message", ""))
        fields = {
            k: v for k, v in (data.get("job_fields") or {}).items() if v is not None
        }
        new_phase = "payment" if data.get("ready_for_payment") else None
        # If the AI extracted job data, always render from fields (ignore AI message).
        if fields.get("title") or fields.get("required_skills"):
            message = _format_job_summary(fields)
        elif not message:
            raise ValueError("empty message and no job fields")
        return message, fields or None, new_phase, None
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        # JSON may be malformed (e.g. unescaped quotes inside the description).
        # Try a regex-based extraction of just the "message" value before giving up.
        logger.debug("job_collection: JSON parsing failed (%s), trying regex fallback", type(e).__name__)
        m = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
        if m:
            message = (
                m.group(1)
                .replace("\\n", "\n")
                .replace('\\"', '"')
                .replace("\\\\", "\\")
            )
            logger.warning(
                "job_collection: fell back to regex extraction (%.60s…)", message
            )
            ready = (
                '"ready_for_payment": true' in raw or '"ready_for_payment":true' in raw
            )
            return message, None, "payment" if ready else None, None
        # Total failure — restart with manual flow to collect fields step by step.
        logger.error("job_collection: unparseable response: %.200s", raw)
        return (
            "I had trouble processing that. Let me ask you a few questions to make sure I get everything right.\n\n"
            "**What's the job title, and what are the key required skills? (e.g., 'Senior React Developer — React, TypeScript, Node.js')**",
            None,
            None,
            None,
        )


def _parse_payment(
    raw: str,
) -> tuple[str, dict[str, Any] | None, str | None, dict[str, Any] | None]:
    try:
        data = json.loads(_extract_json(raw))
        message = str(data.get("message", ""))
        if not message:
            raise ValueError("empty message field")
        confirmed = bool(data.get("payment_confirmed", False))
        new_phase = "recruitment" if confirmed else None
        extras: dict[str, Any] = {"payment_confirmed": confirmed}
        if data.get("promo_code"):
            extras["promo_code"] = data["promo_code"]
        return message, None, new_phase, extras
    except (json.JSONDecodeError, TypeError, ValueError):
        m = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
        if m:
            message = (
                m.group(1)
                .replace("\\n", "\n")
                .replace('\\"', '"')
                .replace("\\\\", "\\")
            )
            confirmed = (
                '"payment_confirmed": true' in raw or '"payment_confirmed":true' in raw
            )
            return (
                message,
                None,
                "recruitment" if confirmed else None,
                {"payment_confirmed": confirmed},
            )
        logger.error("payment: unparseable response: %.200s", raw)
        return (
            "Let me know when you're ready to proceed with payment.",
            None,
            None,
            {"payment_confirmed": False},
        )


# Words/phrases that unambiguously mean "yes, charge the credit and proceed".
_CONFIRM_WORDS: frozenset[str] = frozenset(
    {
        "confirm",
        "confirmed",
        "proceed",
        "yes",
        "go ahead",
        "go",
        "launch",
        "pay",
        "looks good",
        "no promo code",
        "no promo",
        "start",
        "proceed with credit",
        "do it",
        "yep",
        "yeah",
        "ok",
        "okay",
    }
)


def _detect_payment_intent(text: str) -> str | None:
    """Return 'confirm' or 'cancel' if the message is an unambiguous shortcut.

    Returns None when the message needs to be forwarded to the AI (e.g. a
    promo code, a question, or an ambiguous phrase).
    """
    normalised = text.lower().strip().rstrip(".").rstrip("!")
    if normalised in _CONFIRM_WORDS:
        return "confirm"
    if normalised in {"cancel", "back", "go back", "stop", "exit", "quit", "abort"}:
        return "cancel"
    return None


# Words that mean "yes, this job summary looks good — proceed to payment".
_JOB_CONFIRM_WORDS: frozenset[str] = frozenset(
    {
        "confirm",
        "confirmed",
        "yes",
        "yep",
        "yeah",
        "yup",
        "ok",
        "okay",
        "looks good",
        "looks correct",
        "all good",
        "all looks good",
        "proceed",
        "go ahead",
        "go",
        "launch",
        "start",
        "great",
        "perfect",
        "correct",
        "that's correct",
        "that's right",
        "that looks good",
        "approve",
        "approved",
        "good",
        "done",
        "ready",
        "lets go",
        "let's go",
    }
)


def _detect_job_summary_confirmation(
    user_text: str, messages: list[dict[str, Any]]
) -> bool:
    """Return True when the user is confirming the step-16 job summary.

    Only fires when BOTH conditions hold:
    1. The user's text is an unambiguous affirmative.
    2. The last assistant message contained the 📋 Job Summary block,
       meaning the conversation is at the right point in the flow.
    """
    normalised = user_text.lower().strip().rstrip(".").rstrip("!")
    if normalised not in _JOB_CONFIRM_WORDS:
        return False
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = str(msg.get("content", ""))
            return "📋" in content and "Job Summary" in content
    return False


def _build_payment_block(credits_remaining: int) -> str:
    """Return the inline payment options block shown after the user confirms the job summary."""
    return (
        "Your job listing is confirmed! To launch the Talent Scout, choose an option below:\n\n"
        "---\n\n"
        "💳 **Ready to Launch**\n\n"
        f"**Cost:** 1 credit  \n"
        f"**Credits remaining:** {credits_remaining} credit(s)  \n\n"
        "**Type one of the following:**\n\n"
        "- `confirm` — use 1 credit and launch the Talent Scout now\n\n"
        "- `promo CODE` — apply a promo code first (e.g. `promo LAUNCH50`)\n\n"
        "- `cancel` — go back and edit the job details"
    )


def _extract_json(text: str) -> str:
    """Pull the first {...} block out of a potentially padded string."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


# ── Job-fields accumulation & job creation ────────────────────────────────────

_JOB_DATA_ROLE = "_job_data"  # hidden metadata entry in the messages list


def _accumulate_job_fields(
    messages: list[dict[str, Any]], new_fields: dict[str, Any]
) -> list[dict[str, Any]]:
    """Merge new_fields into the session's hidden _job_data metadata entry.

    The entry is stored as the first element of the list so it is never
    rotated out by summarisation (which only trims from the tail).
    """
    for i, msg in enumerate(messages):
        if msg.get("role") == _JOB_DATA_ROLE:
            existing: dict[str, Any] = msg.get("content") or {}  # type: ignore[assignment]
            messages[i] = {
                "role": _JOB_DATA_ROLE,
                "content": {**existing, **new_fields},
            }
            return messages
    # First time — prepend the entry
    return [{"role": _JOB_DATA_ROLE, "content": dict(new_fields)}] + messages


def _get_accumulated_fields(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the accumulated job fields from the hidden metadata entry."""
    for msg in messages:
        if msg.get("role") == _JOB_DATA_ROLE:
            content = msg.get("content")
            return dict(content) if isinstance(content, dict) else {}
    return {}


def _generate_job_ref() -> str:
    """8-character alphanumeric job reference (e.g. MI0T4AM3)."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


_WORK_TYPE_MAP: dict[str, str] = {
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
    "hybrid": "hybrid",
    "remote": "remote",
    "remote_global": "remote_global",
    "remote global": "remote_global",
    "global remote": "remote_global",
}


def _coerce_work_type(value: Any) -> str | None:
    if not value:
        return None
    return _WORK_TYPE_MAP.get(str(value).lower().strip(), "onsite")


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return (
            float(str(value).replace(",", "").replace("$", "").strip())
            if value is not None
            else None
        )
    except (TypeError, ValueError):
        return None


async def _create_job_on_payment(
    db: AsyncSession,
    tenant: Tenant,
    messages: list[dict[str, Any]],
) -> Job:
    """Create a Job record from accumulated chat fields, deduct 1 credit, emit audit, queue Scout.

    Called exactly once when the payment phase confirms successfully.
    """
    fields = _get_accumulated_fields(messages)
    print(f"Payment confirmed, creating job for tenant {tenant.id}")
    print(f"Job fields: {fields}")
    logger.info(
        "_create_job_on_payment: tenant=%s accumulated fields=%s",
        tenant.id,
        list(fields.keys()),
    )

    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        tenant_id=tenant.id,
        job_ref=_generate_job_ref(),
        title=str(fields.get("title") or "Untitled Role"),
        title_variations=fields.get("title_variations"),
        job_type=str(fields.get("job_type") or ""),
        description=str(fields.get("description") or ""),
        required_skills=fields.get("required_skills") or [],
        experience_years=_to_int(fields.get("experience_years")),
        salary_min=_to_float(fields.get("salary_min")),
        salary_max=_to_float(fields.get("salary_max")),
        location=str(fields.get("location") or ""),
        location_variations=fields.get("location_variations"),
        work_type=_coerce_work_type(fields.get("work_type")),
        tech_stack=fields.get("tech_stack") or [],
        team_size=_to_int(fields.get("team_size")),
        minimum_score=_to_int(fields.get("minimum_score")) or 6,
        candidate_target=_to_int(fields.get("candidate_target")) or 20,
        hiring_manager_email=str(fields.get("hiring_manager_email") or ""),
        hiring_manager_name=str(fields.get("hiring_manager_name") or ""),
        evaluation_prompt=str(fields.get("evaluation_prompt") or ""),
        outreach_email_prompt=str(fields.get("outreach_email_prompt") or ""),
        interview_questions_count=_to_int(fields.get("interview_questions_count")) or 5,
        custom_interview_questions=fields.get("custom_interview_questions"),
        interview_type=str(fields.get("interview_type") or "text"),
        status="active",
    )
    db.add(job)

    # Deduct 1 credit
    tenant.credits_remaining = tenant.credits_remaining - 1

    await db.flush()  # assign IDs before audit event

    # Emit audit events
    audit = AuditTrailService(db, tenant.id)
    await audit.emit(
        job_id=job_id,
        event_type="payment.credit_charged",
        event_category="payment",
        severity="info",
        actor="system",
        summary=f"1 credit deducted — job '{job.title}' created via AI Recruiter chat",
        detail={"credits_remaining": tenant.credits_remaining, "job_ref": job.job_ref},
    )
    await audit.emit(
        job_id=job_id,
        event_type="scout.job_started",
        event_category="talent_scout",
        severity="info",
        actor="system",
        summary=f"Talent Scout started for job '{job.title}'",
        detail={"job_ref": job.job_ref, "job_title": job.title},
    )

    # Queue the Celery task
    try:
        from app.tasks.talent_scout_tasks import discover_candidates

        discover_candidates.delay(str(job_id), str(tenant.id))
        logger.info(
            "_create_job_on_payment: queued discover_candidates for job %s", job_id
        )
    except Exception as exc:
        logger.error("_create_job_on_payment: could not queue Celery task: %s", exc)

    logger.info(
        "_create_job_on_payment: job %s (%s) created, credits_remaining=%d",
        job.job_ref,
        job.title,
        tenant.credits_remaining,
    )
    return job


# ── Conversation summarisation ────────────────────────────────────────────────


def _count_tokens(messages: list[dict[str, Any]]) -> int:
    """Approximate token count as total characters ÷ 4."""
    return sum(len(str(m.get("content", ""))) for m in messages) // 4


async def _summarise_if_needed(
    messages: list[dict[str, Any]], tenant: Tenant
) -> list[dict[str, Any]]:
    """Condense old messages into a single summary when the token budget is exceeded.

    Keeps the most recent _SUMMARY_KEEP_RECENT messages intact so the AI has
    full fidelity on what was just said.  Everything older is replaced with a
    single system message: "Previous conversation summary: {text}".

    Hidden metadata entries (role starts with '_', e.g. _job_data) are ALWAYS
    preserved at the front of the list regardless of summarisation — they must
    never be rotated out because job creation reads from them at payment time.

    The condensed list is saved back to the session by the caller so subsequent
    turns start from the smaller footprint.
    """
    # Split metadata entries from the real conversation before any token checks.
    meta = [m for m in messages if str(m.get("role", "")).startswith("_")]
    convo = [m for m in messages if not str(m.get("role", "")).startswith("_")]

    if _count_tokens(convo) <= _TOKEN_BUDGET:
        return messages  # nothing to do

    older = convo[:-_SUMMARY_KEEP_RECENT]
    recent = convo[-_SUMMARY_KEEP_RECENT:]

    text = _format_history_for_ai(older)
    ai = AIProvider(tenant)
    try:
        summary_text = await ai.complete(
            prompt=(
                "Summarise the following recruiter-AI conversation concisely. "
                "Preserve every confirmed detail: job title, required skills, "
                "experience years, salary, location, work type, hiring manager "
                "name/email, minimum score, and any other decisions made.\n\n"
                f"{text}"
            ),
            system=(
                "You are summarising a conversation for context compression. "
                "Be concise but complete. Output plain text, no JSON."
            ),
            max_tokens=400,
        )
    except Exception as exc:
        logger.warning(
            "_summarise_if_needed: AI call failed (%s) — falling back to truncation",
            exc,
        )
        summary_text = f"[Earlier conversation — {len(older)} messages omitted]"

    summary_msg: dict[str, Any] = {
        "role": "system",
        "content": f"Previous conversation summary: {summary_text}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        "_summarise_if_needed: compressed %d messages → 1 summary + %d recent (kept %d meta entries)",
        len(older),
        len(recent),
        len(meta),
    )
    # Re-prepend metadata so _job_data is never lost.
    return meta + [summary_msg] + recent


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _create_session(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> ChatSession:
    """Create a new job_collection phase session."""
    session = ChatSession(
        tenant_id=tenant_id,
        user_id=user_id,
        phase="job_collection",
        messages=[],
    )
    db.add(session)
    await db.commit()
    return session
