"""Audit trail routes.

Routes:
  GET /jobs/{job_id}/audit-stream   — real-time SSE via asyncpg LISTEN
  GET /jobs/{job_id}/audit-events   — paginated history with category/severity filters
  GET /super-admin/audit            — platform-wide system+payment events (super_admin only)
"""

import asyncio
import json
import logging
import uuid
from typing import Annotated, AsyncGenerator

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.job import Job
from app.models.job_audit_event import JobAuditEvent
from app.routers.auth import get_current_tenant
from app.schemas.common import PaginatedResponse
from app.schemas.job_audit_event import JobAuditEventResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _asyncpg_dsn() -> str:
    """Convert SQLAlchemy asyncpg URL to a plain asyncpg DSN."""
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def _channel_name(job_id: uuid.UUID) -> str:
    return f"audit_{str(job_id).replace('-', '_')}"


async def _sse_generator(
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    last_event_id: str | None,
    category_filter: str | None,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings for each new audit event on this job.

    1. If last_event_id is provided, replay missed events first.
    2. Subscribe to Postgres NOTIFY channel via asyncpg LISTEN.
    3. Forward each notification as an SSE data frame.
    4. On disconnect (GeneratorExit) the connection is released cleanly.
    """
    # Replay missed events if client sends Last-Event-ID
    if last_event_id:
        async for frame in _replay_events(db, job_id, tenant_id, last_event_id, category_filter):
            yield frame

    conn: asyncpg.Connection | None = None
    queue: asyncio.Queue[str] = asyncio.Queue()

    def _on_notify(_conn: asyncpg.Connection, pid: int, channel: str, payload: str) -> None:
        queue.put_nowait(payload)

    try:
        conn = await asyncpg.connect(_asyncpg_dsn())
        channel = _channel_name(job_id)
        await conn.add_listener(channel, _on_notify)

        # Keep-alive: yield a comment every 15 s so the TCP socket stays open
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    data = {"raw": payload}

                if not _matches_category(data, category_filter):
                    continue

                event_id = data.get("id", "")
                yield f"id: {event_id}\ndata: {json.dumps(data)}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"

    except GeneratorExit:
        pass
    except Exception as exc:
        logger.error("SSE generator error for job %s: %s", job_id, exc)
        yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
    finally:
        if conn:
            try:
                await conn.remove_listener(_channel_name(job_id), _on_notify)
                await conn.close()
            except Exception as close_exc:
                logger.warning("Error closing asyncpg connection: %s", close_exc)


async def _replay_events(
    db: AsyncSession,
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
    since_event_id: str,
    category_filter: str | None,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames for events created after `since_event_id` (UUID)."""
    try:
        since_id = uuid.UUID(since_event_id)
    except ValueError:
        return

    # Fetch the timestamp of the last-seen event
    ts_result = await db.execute(
        select(JobAuditEvent.created_at).where(
            JobAuditEvent.id == since_id,
            JobAuditEvent.tenant_id == tenant_id,
        )
    )
    since_ts = ts_result.scalar_one_or_none()
    if not since_ts:
        return

    conditions = [
        JobAuditEvent.job_id == job_id,
        JobAuditEvent.tenant_id == tenant_id,
        JobAuditEvent.created_at > since_ts,
    ]
    if category_filter:
        conditions.append(JobAuditEvent.event_category == category_filter)

    result = await db.execute(
        select(JobAuditEvent)
        .where(and_(*conditions))
        .order_by(JobAuditEvent.created_at)
    )
    for event in result.scalars().all():
        resp = JobAuditEventResponse.model_validate(event)
        yield f"id: {event.id}\ndata: {resp.model_dump_json()}\n\n"


def _matches_category(data: dict, category_filter: str | None) -> bool:
    if not category_filter:
        return True
    return data.get("event_category") == category_filter


async def _verify_job_access(
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Job:
    """Raise 404 if the job doesn't exist or belongs to another tenant."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}/audit-stream")
async def audit_stream(
    job_id: uuid.UUID,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    last_event_id: str | None = Query(None, alias="lastEventId"),
) -> StreamingResponse:
    """Real-time SSE stream for all audit events on a job.

    Subscribe via EventSource.  Send ``lastEventId`` to replay events missed
    during a reconnect.  The connection is kept alive with periodic comments.
    """
    await _verify_job_access(job_id, tenant.id, db)
    gen = _sse_generator(job_id, tenant.id, db, last_event_id, category_filter=None)
    return StreamingResponse(gen, media_type="text/event-stream")


@router.get("/jobs/{job_id}/evaluation-report")
async def evaluation_report_stream(
    job_id: uuid.UUID,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    last_event_id: str | None = Query(None, alias="lastEventId"),
) -> StreamingResponse:
    """SSE stream filtered to talent_scout candidate-status events only.

    Powers the Evaluation Report table in the chat UI.  Uses the same
    underlying LISTEN channel as audit-stream but discards non-candidate events.
    """
    await _verify_job_access(job_id, tenant.id, db)
    gen = _sse_generator(
        job_id, tenant.id, db, last_event_id, category_filter="talent_scout"
    )
    return StreamingResponse(gen, media_type="text/event-stream")


@router.get("/jobs/{job_id}/audit-events", response_model=PaginatedResponse[JobAuditEventResponse])
async def list_audit_events(
    job_id: uuid.UUID,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    category: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[JobAuditEventResponse]:
    """Paginated audit event history with optional category/severity filters."""
    await _verify_job_access(job_id, tenant.id, db)

    conditions = [
        JobAuditEvent.job_id == job_id,
        JobAuditEvent.tenant_id == tenant.id,
    ]
    if category:
        conditions.append(JobAuditEvent.event_category == category)
    if severity:
        conditions.append(JobAuditEvent.severity == severity)

    count_result = await db.execute(
        select(JobAuditEvent).where(and_(*conditions))
    )
    total = len(count_result.scalars().all())

    result = await db.execute(
        select(JobAuditEvent)
        .where(and_(*conditions))
        .order_by(JobAuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    events = result.scalars().all()
    items = [JobAuditEventResponse.model_validate(e) for e in events]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


# ── Super-admin audit view ─────────────────────────────────────────────────────

async def _require_super_admin(
    authorization: Annotated[str, Header()],
) -> dict:
    """Validate JWT and assert super_admin role.

    Returns the decoded user metadata dict on success.
    """
    import httpx as _httpx

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    token = authorization[len("Bearer "):]

    async with _httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_data = resp.json()
    role = (user_data.get("app_metadata") or {}).get("role")
    if role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="super_admin role required")
    return user_data


@router.get(
    "/super-admin/audit",
    response_model=PaginatedResponse[JobAuditEventResponse],
)
async def super_admin_audit(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(_require_super_admin),
    category: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[JobAuditEventResponse]:
    """Platform-wide audit view: system and payment events across all tenants.

    Returns only ``system`` and ``payment`` categories — never candidate PII
    from talent_scout or resume_screener events.
    """
    # Always restrict to system + payment categories
    allowed_categories = ["system", "payment"]
    effective_category = category if category in allowed_categories else None

    conditions = [
        JobAuditEvent.event_category.in_(allowed_categories)
    ]
    if effective_category:
        conditions.append(JobAuditEvent.event_category == effective_category)
    if severity:
        conditions.append(JobAuditEvent.severity == severity)

    count_result = await db.execute(
        select(JobAuditEvent).where(and_(*conditions))
    )
    total = len(count_result.scalars().all())

    result = await db.execute(
        select(JobAuditEvent)
        .where(and_(*conditions))
        .order_by(JobAuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    events = result.scalars().all()
    items = [JobAuditEventResponse.model_validate(e) for e in events]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
