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
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat-sessions", tags=["chat-sessions"])

# ── System prompts ─────────────────────────────────────────────────────────────

_JOB_COLLECTION_SYSTEM = (
    "You are an expert AI Recruiter helping a recruiter create a new job listing. "
    "Guide them through these 16 steps in order, one or two at a time:\n\n"
    "1. Greeting — invite the recruiter to paste a job description or describe the role.\n"
    "2. Title extraction — normalise to a 1–2 word title + full display title; confirm both.\n"
    "3. Title variations — suggest 3–5 similar titles for the recruiter to approve/edit.\n"
    "4. Required Skills — extract from description; recruiter adds or removes.\n"
    "5. Experience — confirm years required.\n"
    "6. Salary Range — min/max (optional; skip gracefully if declined).\n"
    "7. Location + Work Type — confirm location; ask onsite/hybrid/remote/remote_global.\n"
    "8. Tech Stack — extract from description; recruiter can add more.\n"
    "9. Team Size — optional.\n"
    "10. Job Description — present clean summary for confirmation.\n"
    "11. Hiring Manager — name and email.\n"
    "12. Minimum Suitability Score — 1–10 scale; default 6.\n"
    "13. Candidate Count — how many candidates should the Scout target?\n"
    "14. Email Outreach Prompt — show default; allow customisation.\n"
    "15. Resume Evaluation Prompt — generate role-specific default; allow customisation. "
    "Ask for test question count (default 5) and any custom questions.\n"
    "16. Confirmation — show full job summary. Ask recruiter to confirm or edit.\n\n"
    "RULES: Never skip steps. Confirm data before advancing. "
    "After step 16 confirmation, set ready_for_payment=true.\n\n"
    "Return ONLY valid JSON:\n"
    '{"message": "<conversational text>", '
    '"job_fields": {"title": null, "title_variations": null, "job_type": null, '
    '"description": null, "required_skills": null, "experience_years": null, '
    '"salary_min": null, "salary_max": null, "location": null, '
    '"location_variations": null, "work_type": null, "tech_stack": null, '
    '"team_size": null, "hiring_manager_name": null, "hiring_manager_email": null, '
    '"minimum_score": null, "interview_questions_count": null, '
    '"custom_interview_questions": null, "outreach_email_prompt": null, '
    '"evaluation_prompt": null}, '
    '"current_step": 1, "ready_for_payment": false}'
)

_PAYMENT_SYSTEM = (
    "You are an AI Recruiter helping finalise a job listing for payment. "
    "The job spec has been confirmed. Guide the recruiter to:\n"
    "1. Explain the credit cost (1 credit per job search).\n"
    "2. Ask if they have a promo code.\n"
    "3. Once they confirm payment or a valid promo code, set payment_confirmed=true.\n\n"
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

_TOKEN_BUDGET = 3_000   # approximate tokens; trigger summarisation above this
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
            ChatSession.phase.in_(["job_collection", "payment", "recruitment"]),
        )
        .order_by(ChatSession.updated_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if not session:
        session = await _create_session(db, tenant.id, user_id)

    return ChatSessionResponse.model_validate(session)


@router.post("/new", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
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
    user_id: uuid.UUID = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=50),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[ChatSessionListItem]:
    """List chat sessions for the current user, most recent first."""
    conditions = [
        ChatSession.tenant_id == tenant.id,
        ChatSession.user_id == user_id,
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
        real_msg_count = len([m for m in msgs if m.get("role") in ("user", "assistant")])
        items.append(ChatSessionListItem(
            id=s.id,
            phase=s.phase,
            job_id=s.job_id,
            job_title=job_titles.get(s.job_id) if s.job_id else None,
            preview=preview,
            message_count=real_msg_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
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
    messages.append({
        "role": "user",
        "content": user_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    messages = await _summarise_if_needed(messages, tenant)

    ai_raw = await _call_ai(tenant, session.phase, messages, user_text)

    reply_text, job_fields, new_phase, extras = _parse_ai_response(
        ai_raw, session.phase
    )

    messages.append({
        "role": "assistant",
        "content": reply_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    resolved_phase = new_phase or session.phase

    session.messages = messages
    session.phase = resolved_phase
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()

    response: dict[str, Any] = {
        "session_id": str(session_id),
        "message": reply_text,
        "phase": resolved_phase,
    }
    if job_fields:
        response["job_fields"] = job_fields
    if extras:
        response.update(extras)
    return response


# ── AI orchestration ──────────────────────────────────────────────────────────


async def _call_ai(
    tenant: Tenant,
    phase: str,
    messages: list[dict[str, Any]],
    latest_user_message: str,
) -> str:
    """Build a prompt from conversation history and call the AI provider."""
    system = _get_system_prompt(phase)
    history = _format_history_for_ai(messages[:-1])  # exclude the turn just added
    prompt = f"{history}\nRecruiter: {latest_user_message}" if history else latest_user_message
    ai = AIProvider(tenant)
    return await ai.complete(prompt=prompt, system=system, max_tokens=1200)


def _get_system_prompt(phase: str) -> str:
    if phase == "payment":
        return _PAYMENT_SYSTEM
    if phase in ("recruitment", "post_recruitment"):
        return _RECRUITMENT_SYSTEM
    return _JOB_COLLECTION_SYSTEM


def _format_history_for_ai(messages: list[dict[str, Any]]) -> str:
    """Convert recent messages to a readable conversation string."""
    parts = []
    for msg in messages[-20:]:
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


def _parse_job_collection(
    raw: str,
) -> tuple[str, dict[str, Any] | None, str | None, dict[str, Any] | None]:
    try:
        data = json.loads(_extract_json(raw))
        message = str(data.get("message", raw))
        fields = {k: v for k, v in (data.get("job_fields") or {}).items() if v is not None}
        new_phase = "payment" if data.get("ready_for_payment") else None
        return message, fields or None, new_phase, None
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("job_collection: non-JSON response: %.120s", raw)
        return raw.strip(), None, None, None


def _parse_payment(
    raw: str,
) -> tuple[str, dict[str, Any] | None, str | None, dict[str, Any] | None]:
    try:
        data = json.loads(_extract_json(raw))
        message = str(data.get("message", raw))
        confirmed = bool(data.get("payment_confirmed", False))
        new_phase = "recruitment" if confirmed else None
        extras: dict[str, Any] = {"payment_confirmed": confirmed}
        if data.get("promo_code"):
            extras["promo_code"] = data["promo_code"]
        return message, None, new_phase, extras
    except (json.JSONDecodeError, TypeError, ValueError):
        return raw.strip(), None, None, None


def _extract_json(text: str) -> str:
    """Pull the first {...} block out of a potentially padded string."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


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

    The condensed list is saved back to the session by the caller so subsequent
    turns start from the smaller footprint.
    """
    if _count_tokens(messages) <= _TOKEN_BUDGET:
        return messages

    older = messages[:-_SUMMARY_KEEP_RECENT]
    recent = messages[-_SUMMARY_KEEP_RECENT:]

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
        logger.warning("_summarise_if_needed: AI call failed (%s) — falling back to truncation", exc)
        summary_text = f"[Earlier conversation — {len(older)} messages omitted]"

    summary_msg: dict[str, Any] = {
        "role": "system",
        "content": f"Previous conversation summary: {summary_text}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        "_summarise_if_needed: compressed %d messages → 1 summary + %d recent",
        len(older), len(recent),
    )
    return [summary_msg] + recent


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
