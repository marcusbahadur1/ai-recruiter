"""Marketing prospects router — Client Pipeline Phase 3.

Routes (all under /api/v1/marketing):
  GET   /prospects                — list prospects (filters, sort, pagination)
  POST  /prospects/scrape         — trigger BrightData scrape + ICP score + insert
  GET   /prospects/{id}           — single prospect with outreach log
  PATCH /prospects/{id}           — update stage, email, notes, etc.
  POST  /prospects/{id}/enrich-email — call Hunter.io, store result
  POST  /prospects/{id}/enroll    — enroll in a sequence
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.marketing import MarketingOutreachLog, MarketingProspect, MarketingSettings
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.marketing import (
    ProspectCreate,
    ProspectListResponse,
    ProspectRead,
    ProspectUpdate,
    ScrapeRequest,
    ScrapeResponse,
)
from app.services import hunter as hunter_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-prospects"])

# ── Stage ordering for sort ────────────────────────────────────────────────────
_STAGE_ORDER = {
    "identified": 0,
    "connected": 1,
    "messaged": 2,
    "replied": 3,
    "demo_booked": 4,
    "trial": 5,
    "paid": 6,
}


# ── ICP scoring ────────────────────────────────────────────────────────────────


def compute_icp_score(
    prospect_data: dict[str, Any],
    icp_config: dict[str, Any],
    has_hiring_spike: bool = False,
) -> tuple[int, dict[str, int]]:
    """Score a prospect against the tenant's ICP config.

    Returns (score 1-10, breakdown dict).
    """
    score = 0
    breakdown: dict[str, int] = {}

    title = (prospect_data.get("title") or "").lower()
    target_titles = [t.lower() for t in (icp_config.get("target_titles") or [])]
    if target_titles and any(t in title for t in target_titles):
        score += 3
        breakdown["title_match"] = 3

    company_type = (prospect_data.get("company_type") or "").lower()
    config_types = [ct.lower() for ct in (icp_config.get("company_types") or [])]
    if config_types and any(ct in company_type or company_type in ct for ct in config_types):
        score += 2
        breakdown["company_type_match"] = 2

    size = prospect_data.get("company_size")
    size_min = icp_config.get("size_min", 0)
    size_max = icp_config.get("size_max", 999_999)
    if size is not None and size_min <= size <= size_max:
        score += 1
        breakdown["company_size_in_range"] = 1

    location = (prospect_data.get("location") or "").lower()
    config_locations = [loc.lower() for loc in (icp_config.get("locations") or [])]
    if config_locations and any(loc in location or location in loc for loc in config_locations):
        score += 1
        breakdown["location_match"] = 1

    last_post = prospect_data.get("last_linkedin_post_at")
    if last_post:
        if isinstance(last_post, str):
            try:
                last_post = datetime.fromisoformat(last_post)
            except ValueError:
                last_post = None
        if last_post:
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            if last_post.replace(tzinfo=timezone.utc) > cutoff:
                score += 2
                breakdown["recent_linkedin_activity"] = 2

    if has_hiring_spike:
        score += 1
        breakdown["hiring_spike_signal"] = 1

    return min(score, 10), breakdown


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _get_prospect_or_404(
    prospect_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    with_log: bool = False,
) -> MarketingProspect:
    q = select(MarketingProspect).where(
        and_(
            MarketingProspect.id == prospect_id,
            MarketingProspect.tenant_id == tenant_id,
        )
    )
    if with_log:
        q = q.options(selectinload(MarketingProspect.outreach_log))
    result = await db.execute(q)
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prospect not found")
    return p


async def _get_icp_config(tenant_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant_id)
    )
    s = result.scalar_one_or_none()
    if s and s.icp_config:
        return s.icp_config
    # Fall back to platform defaults
    result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
    )
    defaults = result.scalar_one_or_none()
    return defaults.icp_config if defaults and defaults.icp_config else {}


async def _get_hunter_api_key(tenant_id: uuid.UUID, db: AsyncSession) -> Optional[str]:
    result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant_id)
    )
    s = result.scalar_one_or_none()
    if s and s.channel_config:
        from app.services.crypto import decrypt
        raw = s.channel_config.get("hunter_api_key")
        if raw:
            try:
                return decrypt(raw)
            except Exception:
                return raw  # stored unencrypted during dev
    return None


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/prospects", response_model=ProspectListResponse)
async def list_prospects(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: str = Query("icp_desc"),  # icp_desc | icp_asc | date_desc | stage
    stage: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    company_size_min: Optional[int] = Query(None),
    company_size_max: Optional[int] = Query(None),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ProspectListResponse:
    q = select(MarketingProspect).where(MarketingProspect.tenant_id == tenant.id)

    if stage:
        # stage can be comma-separated
        stages = [s.strip() for s in stage.split(",")]
        q = q.where(MarketingProspect.stage.in_(stages))
    if source:
        q = q.where(MarketingProspect.source == source)
    if location:
        q = q.where(MarketingProspect.location.ilike(f"%{location}%"))
    if company_size_min is not None:
        q = q.where(MarketingProspect.company_size >= company_size_min)
    if company_size_max is not None:
        q = q.where(MarketingProspect.company_size <= company_size_max)

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Sort
    if sort == "icp_asc":
        q = q.order_by(MarketingProspect.icp_score.asc().nullslast())
    elif sort == "date_desc":
        q = q.order_by(MarketingProspect.created_at.desc())
    elif sort == "stage":
        # Python-side ordering after fetch — use date desc as DB sort, re-sort in memory
        q = q.order_by(MarketingProspect.created_at.desc())
    else:  # icp_desc (default)
        q = q.order_by(MarketingProspect.icp_score.desc().nullslast())

    q = q.options(selectinload(MarketingProspect.outreach_log))
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    items = [ProspectRead.model_validate(r) for r in rows]

    if sort == "stage":
        items.sort(key=lambda p: _STAGE_ORDER.get(p.stage, 99))

    return ProspectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/prospects/scrape", response_model=ScrapeResponse)
async def scrape_prospects(
    body: ScrapeRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ScrapeResponse:
    """Trigger a BrightData prospects search, score results, and insert into DB."""
    icp_config = await _get_icp_config(tenant.id, db)

    # Get BrightData API key from channel config
    bd_key: Optional[str] = None
    settings_result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant.id)
    )
    s = settings_result.scalar_one_or_none()
    if s and s.channel_config:
        from app.services.crypto import decrypt
        raw = s.channel_config.get("brightdata_api_key")
        if raw:
            try:
                bd_key = decrypt(raw)
            except Exception:
                bd_key = raw

    raw_prospects: list[dict[str, Any]] = []

    if bd_key:
        raw_prospects = await _brightdata_search_prospects(body, bd_key)
    else:
        logger.warning(
            "No BrightData API key for tenant %s — scrape returned 0 results", tenant.id
        )

    min_score = icp_config.get("min_score", 0)
    inserted = 0

    for raw in raw_prospects:
        score, breakdown = compute_icp_score(raw, icp_config)
        if score < min_score:
            continue

        p = MarketingProspect(
            tenant_id=tenant.id,
            name=raw.get("name"),
            company=raw.get("company"),
            title=raw.get("title"),
            location=raw.get("location"),
            company_size=raw.get("company_size"),
            company_type=raw.get("company_type"),
            linkedin_url=raw.get("linkedin_url"),
            email=raw.get("email"),
            icp_score=score,
            score_breakdown=breakdown,
            source="brightdata",
            stage="identified",
            last_linkedin_post_at=raw.get("last_linkedin_post_at"),
        )
        db.add(p)
        inserted += 1

    if inserted:
        await db.commit()

    logger.info("Scrape inserted %d prospects for tenant %s", inserted, tenant.id)
    return ScrapeResponse(
        inserted=inserted,
        message=(
            f"Scraped and inserted {inserted} prospects"
            if inserted
            else "Scrape complete — no prospects met the minimum ICP score"
        ),
    )


async def _brightdata_search_prospects(
    req: ScrapeRequest,
    api_key: str,
) -> list[dict[str, Any]]:
    """Call BrightData 'LinkedIn People Search' dataset and return normalized rows."""
    # BrightData LinkedIn People Search dataset
    DATASET_ID = "gd_lxe7084k6l8iobbif"
    trigger_url = (
        f"https://api.brightdata.com/datasets/v3/trigger"
        f"?dataset_id={DATASET_ID}&include_errors=true"
    )

    # Build search parameters — one entry per title×location combo (capped at max_prospects)
    inputs = []
    titles = req.titles or ["Recruiter", "HR Director", "Talent Acquisition"]
    locations = req.locations or []

    for title in titles:
        if locations:
            for loc in locations:
                inputs.append({"keyword": title, "location": loc})
                if len(inputs) >= req.max_prospects:
                    break
        else:
            inputs.append({"keyword": title})
        if len(inputs) >= req.max_prospects:
            break

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            trigger_resp = await client.post(trigger_url, json=inputs, headers=headers)
            trigger_resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("BrightData trigger failed: %s", exc)
            return []

        snapshot_id = trigger_resp.json().get("snapshot_id")
        if not snapshot_id:
            return []

        # Poll for results (max 2 minutes)
        import asyncio
        snapshot_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"
        for _ in range(24):
            await asyncio.sleep(5)
            try:
                snap_resp = await client.get(snapshot_url, headers=headers)
                if snap_resp.status_code == 200:
                    rows = snap_resp.json()
                    return _normalize_brightdata_rows(rows)
                elif snap_resp.status_code == 202:
                    continue  # still processing
            except httpx.HTTPError:
                continue

    return []


def _normalize_brightdata_rows(rows: list[dict]) -> list[dict[str, Any]]:
    """Map BrightData row format to our prospect dict format."""
    out = []
    for row in rows:
        if not isinstance(row, dict) or row.get("error"):
            continue
        out.append({
            "name": row.get("name") or row.get("full_name"),
            "title": row.get("headline") or row.get("job_title"),
            "company": row.get("current_company") or row.get("company"),
            "location": row.get("location") or row.get("city"),
            "linkedin_url": row.get("url") or row.get("linkedin_url"),
            "company_size": None,  # not typically in People Search results
            "company_type": None,
            "email": None,
            "last_linkedin_post_at": None,
        })
    return out


@router.get("/prospects/{prospect_id}", response_model=ProspectRead)
async def get_prospect(
    prospect_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ProspectRead:
    p = await _get_prospect_or_404(prospect_id, tenant.id, db, with_log=True)
    return ProspectRead.model_validate(p)


@router.patch("/prospects/{prospect_id}", response_model=ProspectRead)
async def update_prospect(
    prospect_id: uuid.UUID,
    body: ProspectUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ProspectRead:
    p = await _get_prospect_or_404(prospect_id, tenant.id, db, with_log=True)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    p.last_activity_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(p)
    return ProspectRead.model_validate(p)


@router.post("/prospects/{prospect_id}/enrich-email", response_model=ProspectRead)
async def enrich_email(
    prospect_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ProspectRead:
    """Find the prospect's work email via Hunter.io and store it."""
    p = await _get_prospect_or_404(prospect_id, tenant.id, db, with_log=True)
    if p.email:
        return ProspectRead.model_validate(p)

    api_key = await _get_hunter_api_key(tenant.id, db)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hunter.io API key not configured — add it in Settings → Channels",
        )

    if not p.name or not p.company:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Prospect must have a name and company to look up email",
        )

    # Derive domain from company name (simple heuristic)
    parts = p.name.strip().split()
    first = parts[0] if parts else p.name
    last = parts[-1] if len(parts) > 1 else ""
    # Attempt to derive domain: replace spaces with nothing, lowercase
    domain = p.company.lower().replace(" ", "").replace(",", "").replace(".", "") + ".com"

    found_email = await hunter_service.find_email(first, last, domain, api_key)
    if not found_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hunter.io could not find a verified email for this prospect",
        )

    p.email = found_email
    p.last_activity_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(p)
    return ProspectRead.model_validate(p)


class EnrollRequest:
    pass


@router.post("/prospects/{prospect_id}/enroll", response_model=dict)
async def enroll_prospect(
    prospect_id: uuid.UUID,
    body: dict,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enroll a prospect in a sequence.

    Body: { "sequence_id": "<uuid>" }
    """
    p = await _get_prospect_or_404(prospect_id, tenant.id, db)
    sequence_id = body.get("sequence_id")
    if not sequence_id:
        raise HTTPException(status_code=400, detail="sequence_id is required")

    # Import here to avoid circular imports
    from app.models.marketing import MarketingSettings  # already imported above, just confirm

    # Verify sequence belongs to tenant (simple check via raw select)
    from sqlalchemy import text
    check = await db.execute(
        text(
            "SELECT id FROM marketing_sequences WHERE id = :sid AND tenant_id = :tid"
        ),
        {"sid": sequence_id, "tid": str(tenant.id)},
    )
    if not check.fetchone():
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Insert enrollment
    await db.execute(
        text(
            """
            INSERT INTO marketing_enrollments (id, prospect_id, sequence_id, current_step, status)
            VALUES (gen_random_uuid(), :pid, :sid, 0, 'active')
            ON CONFLICT DO NOTHING
            """
        ),
        {"pid": str(p.id), "sid": sequence_id},
    )
    p.last_activity_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("Prospect %s enrolled in sequence %s by tenant %s", p.id, sequence_id, tenant.id)
    return {"enrolled": True, "prospect_id": str(p.id), "sequence_id": sequence_id}
