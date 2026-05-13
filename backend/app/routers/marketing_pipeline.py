"""Marketing pipeline router — Client Pipeline Phase 4.

Routes (all under /api/v1/marketing):
  GET   /pipeline/summary          — all metric counts + funnel + signals + recent prospects + sequences
  PATCH /pipeline/signals/:id/action  — sets actioned=true, optionally enrolls in sequence
  PATCH /pipeline/signals/:id/dismiss — sets dismissed=true
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.marketing import (
    MarketingProspect,
    MarketingSequence,
    MarketingSignal,
)
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.marketing import (
    FunnelRow,
    MetricCard,
    PipelineSummaryResponse,
    ProspectRead,
    SequenceSummary,
    SignalActionRequest,
    SignalRead,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-pipeline"])


# ── Helpers ────────────────────────────────────────────────────────────────────


def _pct(num: int, denom: int) -> float:
    return round(num / denom * 100, 1) if denom > 0 else 0.0


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/pipeline/summary", response_model=PipelineSummaryResponse)
async def get_pipeline_summary(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> PipelineSummaryResponse:
    tid = str(tenant.id)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # ── 1. Prospect counts (current + 7-day baseline) ─────────────────────────
    counts_result = await db.execute(
        text(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE stage IN ('connected','messaged','replied','demo_booked','trial','paid')) AS connected,
                COUNT(*) FILTER (WHERE stage IN ('messaged','replied','demo_booked','trial','paid'))            AS messaged,
                COUNT(*) FILTER (WHERE stage IN ('replied','demo_booked','trial','paid'))                      AS replied,
                COUNT(*) FILTER (WHERE stage IN ('demo_booked','trial','paid'))                                AS demos_booked,
                COUNT(*) FILTER (WHERE stage IN ('trial','paid'))                                              AS trials_started,
                -- 7-day baselines (prospects that existed 7 days ago = created before week_ago)
                COUNT(*) FILTER (WHERE created_at < :week_ago)                                                                                          AS total_7d,
                COUNT(*) FILTER (WHERE stage IN ('connected','messaged','replied','demo_booked','trial','paid') AND created_at < :week_ago)              AS connected_7d,
                COUNT(*) FILTER (WHERE stage IN ('replied','demo_booked','trial','paid') AND created_at < :week_ago)                                    AS replied_7d,
                COUNT(*) FILTER (WHERE stage IN ('demo_booked','trial','paid') AND created_at < :week_ago)                                              AS demos_7d,
                COUNT(*) FILTER (WHERE stage IN ('trial','paid') AND created_at < :week_ago)                                                            AS trials_7d
            FROM marketing_prospects
            WHERE tenant_id = :tid
            """
        ),
        {"tid": tid, "week_ago": week_ago},
    )
    row = counts_result.fetchone()

    total: int = row.total or 0
    connected: int = row.connected or 0
    messaged: int = row.messaged or 0
    replied: int = row.replied or 0
    demos: int = row.demos_booked or 0
    trials: int = row.trials_started or 0

    prospects_card = MetricCard(
        value=total,
        delta=total - (row.total_7d or 0),
    )
    connected_card = MetricCard(
        value=connected,
        delta=connected - (row.connected_7d or 0),
        pct_label=f"{_pct(connected, total)}% accept rate" if total > 0 else None,
    )
    replied_card = MetricCard(
        value=replied,
        delta=replied - (row.replied_7d or 0),
        pct_label=f"{_pct(replied, connected)}% reply rate" if connected > 0 else None,
    )
    demos_card = MetricCard(
        value=demos,
        delta=demos - (row.demos_7d or 0),
        pct_label=f"{_pct(demos, replied)}% conversion" if replied > 0 else None,
    )
    trials_card = MetricCard(
        value=trials,
        delta=trials - (row.trials_7d or 0),
        pct_label=f"{_pct(trials, demos)}% trial rate" if demos > 0 else None,
    )

    # ── 2. Conversion funnel ──────────────────────────────────────────────────
    funnel = [
        FunnelRow(stage="identified",  label="Identified",    count=total,    percentage=100.0),
        FunnelRow(stage="connected",   label="Connected",     count=connected, percentage=_pct(connected, total)),
        FunnelRow(stage="messaged",    label="Messaged",      count=messaged,  percentage=_pct(messaged, total)),
        FunnelRow(stage="replied",     label="Replied",       count=replied,   percentage=_pct(replied, total)),
        FunnelRow(stage="demo_booked", label="Demo booked",   count=demos,     percentage=_pct(demos, total)),
        FunnelRow(stage="trial",       label="Trial started", count=trials,    percentage=_pct(trials, total)),
    ]

    # ── 3. Live signals (3 most recent unactioned + undismissed) ─────────────
    signals_result = await db.execute(
        select(MarketingSignal)
        .where(
            and_(
                MarketingSignal.tenant_id == tenant.id,
                MarketingSignal.actioned.is_(False),
                MarketingSignal.dismissed.is_(False),
            )
        )
        .order_by(MarketingSignal.detected_at.desc())
        .limit(3)
    )
    signals_rows = signals_result.scalars().all()
    signals = [SignalRead.model_validate(s) for s in signals_rows]

    # ── 4. Recent prospect activity (5 most recently active) ─────────────────
    recent_result = await db.execute(
        select(MarketingProspect)
        .where(MarketingProspect.tenant_id == tenant.id)
        .options(selectinload(MarketingProspect.outreach_log))
        .order_by(
            MarketingProspect.last_activity_at.desc().nullslast(),
            MarketingProspect.created_at.desc(),
        )
        .limit(5)
    )
    recent_prospects_rows = recent_result.scalars().all()
    recent_prospects = [ProspectRead.model_validate(p) for p in recent_prospects_rows]

    # ── 5. Active sequences with reply rates ─────────────────────────────────
    seq_result = await db.execute(
        text(
            """
            SELECT
                s.id,
                s.name,
                s.status,
                s.enrolled_count,
                COUNT(ol.id) FILTER (WHERE ol.replied_at IS NOT NULL) AS replied_count,
                COUNT(ol.id) AS total_sent
            FROM marketing_sequences s
            LEFT JOIN marketing_sequence_steps ss ON ss.sequence_id = s.id
            LEFT JOIN marketing_outreach_log ol ON ol.step_id = ss.id
            WHERE s.tenant_id = :tid
              AND s.status IN ('live', 'paused')
            GROUP BY s.id, s.name, s.status, s.enrolled_count
            ORDER BY s.enrolled_count DESC
            """
        ),
        {"tid": tid},
    )
    sequences: list[SequenceSummary] = []
    for seq_row in seq_result.fetchall():
        total_sent = seq_row.total_sent or 0
        replied_count = seq_row.replied_count or 0
        sequences.append(
            SequenceSummary(
                id=seq_row.id,
                name=seq_row.name,
                status=seq_row.status,
                enrolled_count=seq_row.enrolled_count or 0,
                reply_rate=round(replied_count / total_sent, 3) if total_sent > 0 else 0.0,
            )
        )

    return PipelineSummaryResponse(
        prospects_found=prospects_card,
        connected=connected_card,
        replied=replied_card,
        demos_booked=demos_card,
        trials_started=trials_card,
        funnel=funnel,
        signals=signals,
        recent_prospects=recent_prospects,
        sequences=sequences,
    )


@router.patch("/pipeline/signals/{signal_id}/action", response_model=SignalRead)
async def action_signal(
    signal_id: uuid.UUID,
    body: SignalActionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SignalRead:
    """Mark a signal as actioned. For 'outreach_now', also creates a prospect and enrolls."""
    result = await db.execute(
        select(MarketingSignal).where(
            and_(
                MarketingSignal.id == signal_id,
                MarketingSignal.tenant_id == tenant.id,
            )
        )
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")

    if body.action_type == "outreach_now":
        # Find best-match live sequence (highest enrolled_count first)
        seq_result = await db.execute(
            select(MarketingSequence)
            .where(
                and_(
                    MarketingSequence.tenant_id == tenant.id,
                    MarketingSequence.status == "live",
                )
            )
            .order_by(MarketingSequence.enrolled_count.desc())
            .limit(1)
        )
        seq = seq_result.scalar_one_or_none()

        # Create prospect from signal data
        prospect = MarketingProspect(
            tenant_id=tenant.id,
            name=signal.person_name,
            company=signal.company,
            linkedin_url=signal.linkedin_url,
            source="manual",
            stage="identified",
        )
        db.add(prospect)
        await db.flush()  # get prospect.id

        # Enroll in sequence if one exists
        if seq:
            await db.execute(
                text(
                    """
                    INSERT INTO marketing_enrollments (id, prospect_id, sequence_id, current_step, status)
                    VALUES (gen_random_uuid(), :pid, :sid, 0, 'active')
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"pid": str(prospect.id), "sid": str(seq.id)},
            )

    elif body.action_type == "add_to_prospects":
        # Create prospect from signal data
        prospect = MarketingProspect(
            tenant_id=tenant.id,
            name=signal.person_name,
            company=signal.company,
            linkedin_url=signal.linkedin_url,
            source="manual",
            stage="identified",
        )
        db.add(prospect)

    # For 'comment_connect' the frontend opens the LinkedIn URL; nothing to do server-side.

    signal.actioned = True
    await db.commit()
    await db.refresh(signal)
    return SignalRead.model_validate(signal)


@router.patch("/pipeline/signals/{signal_id}/dismiss", response_model=SignalRead)
async def dismiss_signal(
    signal_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SignalRead:
    result = await db.execute(
        select(MarketingSignal).where(
            and_(
                MarketingSignal.id == signal_id,
                MarketingSignal.tenant_id == tenant.id,
            )
        )
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")

    signal.dismissed = True
    await db.commit()
    await db.refresh(signal)
    return SignalRead.model_validate(signal)
