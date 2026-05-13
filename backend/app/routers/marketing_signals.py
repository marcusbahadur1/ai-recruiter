"""Marketing signals router — Client Pipeline Phase 5.

Routes (all under /api/v1/marketing):
  GET   /signals               — list with optional type filter, hide dismissed
  POST  /signals/run           — trigger immediate BrightData scrape for tenant
  GET   /signals/runs/:run_id  — poll a specific run's status
  PATCH /signals/:id/action    — action a signal (outreach_now | add_to_prospects | comment_connect | comment_dm)
  PATCH /signals/:id/dismiss   — dismiss a signal
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.marketing import (
    MarketingProspect,
    MarketingSequence,
    MarketingSignal,
    MarketingSignalRun,
    MarketingSettings,
)
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.marketing import (
    SignalActionRequest,
    SignalListResponse,
    SignalRead,
    SignalRunRead,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-signals"])


# ── GET /signals ───────────────────────────────────────────────────────────────

@router.get("/signals", response_model=SignalListResponse)
async def list_signals(
    type_filter: Optional[str] = Query(None, alias="type"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SignalListResponse:
    """Return unactioned + undismissed signals, sorted: high urgency first, then detected_at desc."""
    q = (
        select(MarketingSignal)
        .where(
            and_(
                MarketingSignal.tenant_id == tenant.id,
                MarketingSignal.actioned.is_(False),
                MarketingSignal.dismissed.is_(False),
            )
        )
        .order_by(
            # high urgency sorts first (0), medium sorts second (1)
            case((MarketingSignal.urgency == "high", 0), else_=1),
            MarketingSignal.detected_at.desc(),
        )
    )

    if type_filter:
        q = q.where(MarketingSignal.type == type_filter)

    result = await db.execute(q)
    rows = result.scalars().all()
    items = [SignalRead.model_validate(s) for s in rows]

    # Last run
    last_run_result = await db.execute(
        select(MarketingSignalRun)
        .where(MarketingSignalRun.tenant_id == tenant.id)
        .order_by(MarketingSignalRun.started_at.desc())
        .limit(1)
    )
    last_run_row = last_run_result.scalar_one_or_none()
    last_run = SignalRunRead.model_validate(last_run_row) if last_run_row else None

    # scrape_frequency_hours from signal_config
    freq_hours = 6
    settings_result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant.id)
    )
    settings = settings_result.scalar_one_or_none()
    if settings and settings.signal_config:
        freq_hours = settings.signal_config.get("scrape_frequency_hours", 6)

    return SignalListResponse(
        items=items,
        total=len(items),
        last_run=last_run,
        scrape_frequency_hours=freq_hours,
    )


# ── POST /signals/run ──────────────────────────────────────────────────────────

@router.post("/signals/run", response_model=SignalRunRead, status_code=status.HTTP_202_ACCEPTED)
async def trigger_signal_scrape(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SignalRunRead:
    """Trigger an immediate BrightData signal scrape for this tenant."""
    from app.tasks.marketing_tasks import scrape_signals_for_tenant

    # Create a run record so frontend can poll status
    run = MarketingSignalRun(tenant_id=tenant.id, signals_found=0)
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Fire Celery task (non-blocking)
    scrape_signals_for_tenant.delay(str(tenant.id), str(run.id))

    return SignalRunRead.model_validate(run)


# ── GET /signals/runs/:run_id ──────────────────────────────────────────────────

@router.get("/signals/runs/{run_id}", response_model=SignalRunRead)
async def get_signal_run(
    run_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SignalRunRead:
    result = await db.execute(
        select(MarketingSignalRun).where(
            and_(
                MarketingSignalRun.id == run_id,
                MarketingSignalRun.tenant_id == tenant.id,
            )
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return SignalRunRead.model_validate(run)


# ── PATCH /signals/:id/action ──────────────────────────────────────────────────

@router.patch("/signals/{signal_id}/action", response_model=SignalRead)
async def action_signal(
    signal_id: uuid.UUID,
    body: SignalActionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SignalRead:
    """Mark a signal as actioned. For outreach_now/add_to_prospects, creates a prospect record."""
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

    if body.action_type in ("outreach_now", "add_to_prospects"):
        prospect = MarketingProspect(
            tenant_id=tenant.id,
            name=signal.person_name,
            company=signal.company,
            linkedin_url=signal.linkedin_url,
            location=signal.location,
            company_type=signal.company_type,
            source="manual",
            stage="identified",
        )
        db.add(prospect)

        if body.action_type == "outreach_now":
            await db.flush()  # get prospect.id
            # Find best live sequence (highest enrolled_count first)
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

    # comment_connect and comment_dm: frontend opens LinkedIn URL; nothing to do server-side.

    signal.actioned = True
    await db.commit()
    await db.refresh(signal)
    return SignalRead.model_validate(signal)


# ── PATCH /signals/:id/dismiss ─────────────────────────────────────────────────

@router.patch("/signals/{signal_id}/dismiss", response_model=SignalRead)
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
