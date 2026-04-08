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
    "10. Job Description — Write a clean 3–5 sentence job description from the collected "
    "details. Then output this EXACT block inside the message field, substituting real values "
    "(never leave placeholders like [X] or 'Not specified' for fields the recruiter provided):\n"
    "---\n\n"
    "📋 **Job Summary**\n\n"
    "**Title:** <full title>\n\n"
    "**Location:** <location> (<work_type>)\n\n"
    "**Experience:** <experience_years>+ years\n\n"
    "**Salary:** <salary_min> – <salary_max> (or 'Not specified')\n\n"
    "**Required Skills:** <comma-separated required_skills>\n\n"
    "**Tech Stack:** <comma-separated tech_stack>\n\n"
    "**Team Size:** <team_size or 'Not specified'>\n\n"
    "**Job Description:**\n\n"
    "<3–5 sentence description>\n\n"
    "---\n\n"
    "Does this look good, or would you like to make any edits?\n\n"
    "CRITICAL: The entire formatted block above MUST appear verbatim in the 'message' JSON "
    "field. Each field MUST be separated by a blank line so they render on separate lines. "
    "Do NOT collapse fields onto one line. Do NOT summarise or refer to it — output it in full.\n"
    "11. Hiring Manager — name and email.\n"
    "12. Minimum Suitability Score — 1–10 scale; default 6.\n"
    "13. Candidate Target — how many candidates should the Scout find? (default 20). "
    "Store the answer as candidate_target (integer).\n"
    "14. Email Outreach Prompt — show default; allow customisation.\n"
    "15. Resume Evaluation Prompt — generate role-specific default; allow customisation. "
    "Ask for test question count (default 5) and any custom questions.\n"
    "16. Confirmation — output the same full 📋 Job Summary block again (with all fields "
    "including hiring manager, minimum score, candidate target), then ask: "
    "'Does everything look correct? Type confirm to proceed or let me know what to change.'\n\n"
    "RULES: Never skip steps. Confirm data before advancing. "
    "When the recruiter confirms at step 16, set ready_for_payment=true in the JSON. "
    "IMPORTANT: There is NO external payment page and NO redirect. "
    "Do NOT say 'redirecting', 'taking you to payment', or anything similar. "
    "Payment happens entirely within this chat conversation — the system handles it automatically "
    "when ready_for_payment=true is set.\n\n"
    "Return ONLY valid JSON:\n"
    '{"message": "<conversational text>", '
    '"job_fields": {"title": null, "title_variations": null, "job_type": null, '
    '"description": null, "required_skills": null, "experience_years": null, '
    '"salary_min": null, "salary_max": null, "location": null, '
    '"location_variations": null, "work_type": null, "tech_stack": null, '
    '"team_size": null, "hiring_manager_name": null, "hiring_manager_email": null, '
    '"minimum_score": null, "candidate_target": null, "interview_questions_count": null, '
    '"custom_interview_questions": null, "outreach_email_prompt": null, '
    '"evaluation_prompt": null}, '
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

    # ── Server-side shortcuts (bypass AI for unambiguous user intent) ──────────

    # 1. Job summary confirmation — user confirmed the step-16 summary → move to payment
    if session.phase == "job_collection" and _detect_job_summary_confirmation(user_text, messages):
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
        job_fields, new_phase, extras = None, "post_recruitment", {"payment_confirmed": False}

    else:
        ai_raw = await _call_ai(tenant, session.phase, messages, user_text)
        reply_text, job_fields, new_phase, extras = _parse_ai_response(
            ai_raw, session.phase
        )

    # Persist any newly extracted job fields into the session's hidden metadata entry.
    if job_fields:
        messages = _accumulate_job_fields(messages, job_fields)

    messages.append({
        "role": "assistant",
        "content": reply_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    resolved_phase = new_phase or session.phase

    # ── Payment confirmed — create job, deduct credit, trigger Scout ─────────
    if extras and extras.get("payment_confirmed") and new_phase == "recruitment":
        if tenant.credits_remaining < 1:
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


# ── AI orchestration ──────────────────────────────────────────────────────────


async def _call_ai(
    tenant: Tenant,
    phase: str,
    messages: list[dict[str, Any]],
    latest_user_message: str,
) -> str:
    """Build a prompt from conversation history and call the AI provider."""
    system = _get_system_prompt(phase, credits_remaining=tenant.credits_remaining)
    history = _format_history_for_ai(messages[:-1])  # exclude the turn just added
    prompt = f"{history}\nRecruiter: {latest_user_message}" if history else latest_user_message
    ai = AIProvider(tenant)
    return await ai.complete(prompt=prompt, system=system, max_tokens=1200)


def _get_system_prompt(phase: str, credits_remaining: int = 0) -> str:
    if phase == "payment":
        return _build_payment_system(credits_remaining)
    if phase in ("recruitment", "post_recruitment"):
        return _RECRUITMENT_SYSTEM
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


def _parse_job_collection(
    raw: str,
) -> tuple[str, dict[str, Any] | None, str | None, dict[str, Any] | None]:
    try:
        data = json.loads(_extract_json(raw))
        message = str(data.get("message", ""))
        if not message:
            raise ValueError("empty message field")
        fields = {k: v for k, v in (data.get("job_fields") or {}).items() if v is not None}
        new_phase = "payment" if data.get("ready_for_payment") else None
        return message, fields or None, new_phase, None
    except (json.JSONDecodeError, TypeError, ValueError):
        # JSON may be malformed (e.g. unescaped quotes inside the description).
        # Try a regex-based extraction of just the "message" value before giving up.
        m = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
        if m:
            message = m.group(1).replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            logger.warning("job_collection: fell back to regex extraction (%.60s…)", message)
            ready = '"ready_for_payment": true' in raw or '"ready_for_payment":true' in raw
            return message, None, "payment" if ready else None, None
        # Total failure — log the raw output but never show it to the user.
        logger.error("job_collection: unparseable response: %.200s", raw)
        return "I've noted those details. Could you confirm everything looks correct so far?", None, None, None


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
            message = m.group(1).replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            confirmed = '"payment_confirmed": true' in raw or '"payment_confirmed":true' in raw
            return message, None, "recruitment" if confirmed else None, {"payment_confirmed": confirmed}
        logger.error("payment: unparseable response: %.200s", raw)
        return "Let me know when you're ready to proceed with payment.", None, None, {"payment_confirmed": False}


# Words/phrases that unambiguously mean "yes, charge the credit and proceed".
_CONFIRM_WORDS: frozenset[str] = frozenset({
    "confirm", "confirmed", "proceed", "yes", "go ahead", "go",
    "launch", "pay", "looks good", "no promo code", "no promo",
    "start", "proceed with credit", "do it", "yep", "yeah", "ok", "okay",
})


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
_JOB_CONFIRM_WORDS: frozenset[str] = frozenset({
    "confirm", "confirmed", "yes", "yep", "yeah", "yup", "ok", "okay",
    "looks good", "looks correct", "all good", "all looks good",
    "proceed", "go ahead", "go", "launch", "start", "great", "perfect",
    "correct", "that's correct", "that's right", "that looks good",
    "approve", "approved", "good", "done", "ready", "lets go", "let's go",
})


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
            messages[i] = {"role": _JOB_DATA_ROLE, "content": {**existing, **new_fields}}
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
    "onsite": "onsite", "on-site": "onsite", "on site": "onsite",
    "hybrid": "hybrid",
    "remote": "remote",
    "remote_global": "remote_global", "remote global": "remote_global", "global remote": "remote_global",
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
        return float(str(value).replace(",", "").replace("$", "").strip()) if value is not None else None
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
    logger.info("_create_job_on_payment: tenant=%s accumulated fields=%s", tenant.id, list(fields.keys()))

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
        logger.info("_create_job_on_payment: queued discover_candidates for job %s", job_id)
    except Exception as exc:
        logger.error("_create_job_on_payment: could not queue Celery task: %s", exc)

    logger.info(
        "_create_job_on_payment: job %s (%s) created, credits_remaining=%d",
        job.job_ref, job.title, tenant.credits_remaining,
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
        logger.warning("_summarise_if_needed: AI call failed (%s) — falling back to truncation", exc)
        summary_text = f"[Earlier conversation — {len(older)} messages omitted]"

    summary_msg: dict[str, Any] = {
        "role": "system",
        "content": f"Previous conversation summary: {summary_text}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        "_summarise_if_needed: compressed %d messages → 1 summary + %d recent (kept %d meta entries)",
        len(older), len(recent), len(meta),
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
