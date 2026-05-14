"""Marketing sequences router — Client Pipeline Phase 6.

Routes (all under /api/v1/marketing):
  GET    /sequences                         — list sequences for tenant
  POST   /sequences                         — create new sequence
  PATCH  /sequences/:id                     — update name/status/persona/angle
  DELETE /sequences/:id                     — soft-delete (status=draft, enrolled_count cleared)
  POST   /sequences/generate                — AI-generate step templates
  GET    /sequences/:id/steps               — list steps (ordered)
  POST   /sequences/:id/steps               — add step
  PATCH  /sequences/:id/steps/:step_id      — update step
  DELETE /sequences/:id/steps/:step_id      — delete step
  POST   /sequences/:id/enroll              — bulk enroll prospects
  GET    /sequences/:id/stats               — performance metrics
"""
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.marketing import (
    MarketingEnrollment,
    MarketingOutreachLog,
    MarketingProspect,
    MarketingSequence,
    MarketingSequenceStep,
)
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.marketing import (
    EnrollProspectsRequest,
    EnrollProspectsResponse,
    GenerateSequenceRequest,
    GenerateSequenceResponse,
    GeneratedStepTemplate,
    SequenceCreate,
    SequenceRead,
    SequenceStats,
    SequenceStepCreate,
    SequenceStepRead,
    SequenceStepUpdate,
    SequenceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-sequences"])

_STEP_CHAR_LIMITS: dict[str, int] = {
    "linkedin_connect": 240,
    "linkedin_dm": 600,
    "email": 5000,
}


# ── Helpers ────────────────────────────────────────────────────────────────────


def _check_plan(tenant: Tenant) -> None:
    is_super = getattr(tenant, "_is_super_admin", False) or tenant.slug == "super-admin"
    if is_super:
        return
    from app.config import get_marketing_limits
    limits = get_marketing_limits(tenant.plan)
    if not limits.get("marketing_visible"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Marketing module requires Agency Small plan or above (current: {tenant.plan})",
        )


async def _get_sequence_or_404(
    seq_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession
) -> MarketingSequence:
    result = await db.execute(
        select(MarketingSequence)
        .where(
            and_(
                MarketingSequence.id == seq_id,
                MarketingSequence.tenant_id == tenant_id,
            )
        )
        .options(selectinload(MarketingSequence.steps))
    )
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    return seq


async def _get_step_or_404(
    seq_id: uuid.UUID, step_id: uuid.UUID, db: AsyncSession
) -> MarketingSequenceStep:
    result = await db.execute(
        select(MarketingSequenceStep).where(
            and_(
                MarketingSequenceStep.id == step_id,
                MarketingSequenceStep.sequence_id == seq_id,
            )
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    return step


async def _build_step_stats(step_ids: list[uuid.UUID], db: AsyncSession) -> dict[uuid.UUID, dict[str, Any]]:
    """Return per-step stats dict keyed by step_id."""
    if not step_ids:
        return {}
    rows = await db.execute(
        select(
            MarketingOutreachLog.step_id,
            func.count().filter(MarketingOutreachLog.sent_at.isnot(None)).label("sent"),
            func.count().filter(
                or_(MarketingOutreachLog.opened_at.isnot(None), MarketingOutreachLog.replied_at.isnot(None))
            ).label("accepted_or_opened"),
            func.count().filter(MarketingOutreachLog.replied_at.isnot(None)).label("replied"),
        )
        .where(MarketingOutreachLog.step_id.in_(step_ids))
        .group_by(MarketingOutreachLog.step_id)
    )
    stats: dict[uuid.UUID, dict[str, Any]] = {}
    for row in rows.fetchall():
        sid = uuid.UUID(str(row.step_id))
        sent = row.sent or 0
        stats[sid] = {
            "sent_count": sent,
            "accept_open_rate": round((row.accepted_or_opened or 0) / sent, 3) if sent else 0.0,
            "reply_rate": round((row.replied or 0) / sent, 3) if sent else 0.0,
            "has_been_sent": sent > 0,
        }
    return stats


def _enrich_step(step: MarketingSequenceStep, stats: dict[uuid.UUID, dict[str, Any]]) -> SequenceStepRead:
    s = stats.get(step.id, {})
    return SequenceStepRead(
        id=step.id,
        sequence_id=step.sequence_id,
        step_type=step.step_type,
        step_name=step.step_name,
        day_offset=step.day_offset,
        message_template=step.message_template,
        condition=step.condition,
        sort_order=step.sort_order,
        sent_count=s.get("sent_count", 0),
        accept_open_rate=s.get("accept_open_rate", 0.0),
        reply_rate=s.get("reply_rate", 0.0),
        has_been_sent=s.get("has_been_sent", False),
    )


def _build_channel_tags(steps: list[MarketingSequenceStep]) -> list[str]:
    seen: list[str] = []
    for s in steps:
        label = {
            "linkedin_connect": "LI",
            "linkedin_dm": "LI",
            "email": "Email",
            "wait": "Wait",
        }.get(s.step_type, s.step_type)
        if label not in seen:
            seen.append(label)
    return seen


async def _build_sequence_read(seq: MarketingSequence, db: AsyncSession) -> SequenceRead:
    step_ids = [s.id for s in seq.steps]
    stats = await _build_step_stats(step_ids, db)
    enriched_steps = [_enrich_step(s, stats) for s in seq.steps]
    return SequenceRead(
        id=seq.id,
        tenant_id=seq.tenant_id,
        name=seq.name,
        status=seq.status,
        persona_target=seq.persona_target,
        angle=seq.angle,
        enrolled_count=seq.enrolled_count,
        steps=enriched_steps,
        channel_tags=_build_channel_tags(seq.steps),
    )


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/sequences", response_model=list[SequenceRead])
async def list_sequences(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[SequenceRead]:
    _check_plan(tenant)
    result = await db.execute(
        select(MarketingSequence)
        .where(MarketingSequence.tenant_id == tenant.id)
        .options(selectinload(MarketingSequence.steps))
        .order_by(MarketingSequence.enrolled_count.desc())
    )
    seqs = result.scalars().all()
    return [await _build_sequence_read(s, db) for s in seqs]


@router.post("/sequences", response_model=SequenceRead, status_code=status.HTTP_201_CREATED)
async def create_sequence(
    body: SequenceCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SequenceRead:
    _check_plan(tenant)

    # Usage enforcement for tenants (not super admin)
    is_super = getattr(tenant, "_is_super_admin", False) or tenant.slug == "super-admin"
    if not is_super:
        from app.models.marketing import MarketingSettings
        platform_result = await db.execute(
            select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
        )
        platform_settings = platform_result.scalar_one_or_none()
        if platform_settings and platform_settings.tenant_mode_config:
            limit = platform_settings.tenant_mode_config.get("max_sequences")
            if limit is not None:
                count_result = await db.execute(
                    select(func.count()).where(MarketingSequence.tenant_id == tenant.id)
                )
                current_count = count_result.scalar_one() or 0
                if current_count >= limit:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Sequence limit reached for your plan ({limit} sequences). Upgrade to create more.",
                    )

    seq = MarketingSequence(
        tenant_id=tenant.id,
        name=body.name,
        status="draft",
        persona_target=body.persona_target,
        angle=body.angle,
        enrolled_count=0,
    )
    db.add(seq)
    await db.commit()
    await db.refresh(seq)
    logger.info("Sequence created id=%s tenant=%s", seq.id, tenant.id)
    # Reload with steps relationship
    seq = await _get_sequence_or_404(seq.id, tenant.id, db)
    return await _build_sequence_read(seq, db)


@router.patch("/sequences/{seq_id}", response_model=SequenceRead)
async def update_sequence(
    seq_id: uuid.UUID,
    body: SequenceUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SequenceRead:
    _check_plan(tenant)
    seq = await _get_sequence_or_404(seq_id, tenant.id, db)
    if body.name is not None:
        seq.name = body.name
    if body.status is not None:
        seq.status = body.status
    if body.persona_target is not None:
        seq.persona_target = body.persona_target
    if body.angle is not None:
        seq.angle = body.angle
    await db.commit()
    seq = await _get_sequence_or_404(seq_id, tenant.id, db)
    return await _build_sequence_read(seq, db)


@router.delete("/sequences/{seq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sequence(
    seq_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    _check_plan(tenant)
    seq = await _get_sequence_or_404(seq_id, tenant.id, db)
    await db.delete(seq)
    await db.commit()
    logger.info("Sequence deleted id=%s tenant=%s", seq_id, tenant.id)


@router.post("/sequences/generate", response_model=GenerateSequenceResponse)
async def generate_sequence_steps(
    body: GenerateSequenceRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> GenerateSequenceResponse:
    """Use Claude to generate 4-step outreach sequence templates."""
    _check_plan(tenant)

    system_prompt = (
        "You are an outreach copywriter for AIRecruiterz, an AI recruitment "
        "platform for recruitment agencies and HR teams."
    )
    user_prompt = (
        f"Write a {body.angle} outreach sequence for {body.persona}. "
        "Generate exactly 4 steps:\n"
        "Step 1: LinkedIn connection request (max 240 chars, no placeholder tokens).\n"
        "Step 2: Wait 2 days if accepted.\n"
        f"Step 3: LinkedIn DM (max 600 chars) — {body.angle} angle, reference their "
        "company type and pain. Use {{first_name}} and {{company}} tokens.\n"
        "Step 4: Email follow-up (if no reply to DM after 3 days) — different angle, "
        "reference AIRecruiterz ROI numbers. Use {{first_name}} and {{company}} tokens.\n"
        "Return ONLY valid JSON with this shape: "
        '{"steps": [{"step_type": "linkedin_connect|linkedin_dm|email|wait", '
        '"day_offset": 0, "message_template": "...", "condition": "..."}]}. '
        "For wait steps, set message_template to null. "
        "For the connection request, set condition to null."
    )

    from app.services.ai_provider import AIProvider
    raw: dict = await AIProvider(tenant).complete_json(
        prompt=user_prompt,
        system=system_prompt,
        max_tokens=1500,
    )

    steps_raw = raw.get("steps", [])
    steps = []
    for i, s in enumerate(steps_raw):
        steps.append(
            GeneratedStepTemplate(
                step_type=s.get("step_type", "linkedin_dm"),
                day_offset=s.get("day_offset", i),
                message_template=s.get("message_template"),
                condition=s.get("condition"),
            )
        )

    return GenerateSequenceResponse(steps=steps)


# ── Steps ──────────────────────────────────────────────────────────────────────


@router.get("/sequences/{seq_id}/steps", response_model=list[SequenceStepRead])
async def list_steps(
    seq_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[SequenceStepRead]:
    _check_plan(tenant)
    seq = await _get_sequence_or_404(seq_id, tenant.id, db)
    step_ids = [s.id for s in seq.steps]
    stats = await _build_step_stats(step_ids, db)
    return [_enrich_step(s, stats) for s in seq.steps]


@router.post(
    "/sequences/{seq_id}/steps",
    response_model=SequenceStepRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_step(
    seq_id: uuid.UUID,
    body: SequenceStepCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SequenceStepRead:
    _check_plan(tenant)
    seq = await _get_sequence_or_404(seq_id, tenant.id, db)

    # Auto-assign sort_order
    max_order = max((s.sort_order for s in seq.steps), default=-1)
    step = MarketingSequenceStep(
        sequence_id=seq.id,
        step_type=body.step_type,
        step_name=body.step_name,
        day_offset=body.day_offset,
        message_template=body.message_template,
        condition=body.condition,
        sort_order=body.sort_order if body.sort_order else max_order + 1,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    logger.info("Sequence step added id=%s seq=%s", step.id, seq_id)
    return _enrich_step(step, {})


@router.patch("/sequences/{seq_id}/steps/{step_id}", response_model=SequenceStepRead)
async def update_step(
    seq_id: uuid.UUID,
    step_id: uuid.UUID,
    body: SequenceStepUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SequenceStepRead:
    _check_plan(tenant)
    # Verify sequence belongs to tenant
    await _get_sequence_or_404(seq_id, tenant.id, db)
    step = await _get_step_or_404(seq_id, step_id, db)

    if body.step_type is not None:
        step.step_type = body.step_type
    if body.step_name is not None:
        step.step_name = body.step_name
    if body.day_offset is not None:
        step.day_offset = body.day_offset
    if body.message_template is not None:
        step.message_template = body.message_template
    if body.condition is not None:
        step.condition = body.condition
    if body.sort_order is not None:
        step.sort_order = body.sort_order

    await db.commit()
    await db.refresh(step)
    stats = await _build_step_stats([step.id], db)
    return _enrich_step(step, stats)


@router.delete(
    "/sequences/{seq_id}/steps/{step_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_step(
    seq_id: uuid.UUID,
    step_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    _check_plan(tenant)
    await _get_sequence_or_404(seq_id, tenant.id, db)
    step = await _get_step_or_404(seq_id, step_id, db)
    await db.delete(step)
    await db.commit()
    logger.info("Sequence step deleted id=%s seq=%s", step_id, seq_id)


# ── Enrollment ─────────────────────────────────────────────────────────────────


@router.post("/sequences/{seq_id}/enroll", response_model=EnrollProspectsResponse)
async def enroll_prospects(
    seq_id: uuid.UUID,
    body: EnrollProspectsRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> EnrollProspectsResponse:
    _check_plan(tenant)
    seq = await _get_sequence_or_404(seq_id, tenant.id, db)

    enrolled = 0
    already_enrolled = 0

    for pid in body.prospect_ids:
        # Verify prospect belongs to this tenant
        p_result = await db.execute(
            select(MarketingProspect).where(
                and_(
                    MarketingProspect.id == pid,
                    MarketingProspect.tenant_id == tenant.id,
                )
            )
        )
        prospect = p_result.scalar_one_or_none()
        if not prospect:
            continue

        # Check not already enrolled in this sequence
        existing = await db.execute(
            select(MarketingEnrollment).where(
                and_(
                    MarketingEnrollment.prospect_id == pid,
                    MarketingEnrollment.sequence_id == seq_id,
                    MarketingEnrollment.status == "active",
                )
            )
        )
        if existing.scalar_one_or_none():
            already_enrolled += 1
            continue

        enrollment = MarketingEnrollment(
            prospect_id=pid,
            sequence_id=seq_id,
            current_step=0,
            status="active",
        )
        db.add(enrollment)
        enrolled += 1

    if enrolled > 0:
        seq.enrolled_count = (seq.enrolled_count or 0) + enrolled
        await db.commit()
        logger.info(
            "Enrolled %d prospects in sequence=%s tenant=%s",
            enrolled,
            seq_id,
            tenant.id,
        )
    else:
        await db.commit()

    return EnrollProspectsResponse(enrolled=enrolled, already_enrolled=already_enrolled)


# ── Stats ──────────────────────────────────────────────────────────────────────


@router.get("/sequences/{seq_id}/stats", response_model=SequenceStats)
async def get_sequence_stats(
    seq_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SequenceStats:
    _check_plan(tenant)
    seq = await _get_sequence_or_404(seq_id, tenant.id, db)

    tid = str(tenant.id)
    sid = str(seq_id)

    row = await db.execute(
        text(
            """
            SELECT
                COUNT(ol.id) FILTER (WHERE ol.sent_at IS NOT NULL)               AS sent,
                COUNT(ol.id) FILTER (
                    WHERE ol.opened_at IS NOT NULL OR ol.replied_at IS NOT NULL
                )                                                                 AS accepted_opened,
                COUNT(ol.id) FILTER (WHERE ol.replied_at IS NOT NULL)            AS replied,
                COUNT(DISTINCT p.id) FILTER (
                    WHERE p.stage = 'demo_booked'
                )                                                                 AS demos
            FROM marketing_outreach_log ol
            JOIN marketing_sequence_steps ss ON ss.id = ol.step_id
            JOIN marketing_prospects p ON p.id = ol.prospect_id
            WHERE ss.sequence_id = :sid
              AND p.tenant_id = :tid
            """
        ),
        {"sid": sid, "tid": tid},
    )
    r = row.fetchone()
    sent = r.sent or 0
    accepted_opened = r.accepted_opened or 0
    replied = r.replied or 0
    demos = r.demos or 0

    return SequenceStats(
        sent=sent,
        accept_open_rate=round(accepted_opened / sent, 3) if sent else 0.0,
        reply_rate=round(replied / sent, 3) if sent else 0.0,
        demos_booked=demos,
    )
