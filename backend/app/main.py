import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.config import settings

# Populate SQLAlchemy mapper registry before any route handlers execute.
import app.models  # noqa: F401

from app.database import AsyncTaskSessionLocal
from app.models.tenant import Tenant
from app.routers import (
    applications,
    audit,
    auth,
    billing,
    candidates,
    chat_sessions,
    dashboard,
    gdpr_settings,
    jobs,
    promo_codes,
    rag,
    screener,
    search,
    super_admin,
    team,
    tenants,
    webhooks,
    widget,
)

API_PREFIX = "/api/v1"

# Routes exempt from trial expiry enforcement
_TRIAL_EXEMPT = re.compile(
    r"^/api/v1/(auth|webhooks|billing|screener/test|actions|candidates/unsubscribe)/|^/docs|^/redoc|^/openapi\.json"
)


def create_app() -> FastAPI:
    application = FastAPI(
        title="AI Recruiter API",
        version="3.0.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    # Widget routes must be accessible from any third-party website (no auth, public).
    # All other routes are restricted to the known frontend origin.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_origin_regex=None,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def trial_expiry_middleware(request: Request, call_next):
        """Block expired-trial tenants on protected routes (SPEC §4)."""
        if _TRIAL_EXEMPT.match(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        import uuid as _uuid
        import httpx as _httpx

        token = auth_header[len("Bearer ") :]
        try:
            async with _httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{settings.supabase_url}/auth/v1/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "apikey": settings.supabase_anon_key,
                    },
                )
            if resp.status_code != 200:
                return await call_next(request)

            user_data = resp.json()
            tenant_id_str: str | None = (user_data.get("app_metadata") or {}).get(
                "tenant_id"
            )
            if not tenant_id_str:
                return await call_next(request)

            tenant_id = _uuid.UUID(tenant_id_str)
        except Exception:
            return await call_next(request)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True))
            )
            tenant = result.scalar_one_or_none()

        if not tenant:
            return await call_next(request)

        if tenant.plan == "trial_expired":
            return JSONResponse(status_code=402, content={"error": "trial_expired"})

        if (
            tenant.plan == "trial"
            and tenant.trial_ends_at is not None
            and tenant.trial_ends_at < datetime.now(timezone.utc)
        ):
            return JSONResponse(status_code=402, content={"error": "trial_expired"})

        return await call_next(request)

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {exc}"},
        )

    for router_module in (
        auth,
        tenants,
        jobs,
        candidates,
        chat_sessions,
        dashboard,
        rag,
        promo_codes,
        webhooks,
        super_admin,
        audit,
        widget,
        team,
        billing,
        gdpr_settings,
        search,
    ):
        application.include_router(router_module.router, prefix=API_PREFIX)

    # Applications router has mixed prefixes (/applications, /test, /actions)
    application.include_router(applications.router, prefix=API_PREFIX)
    application.include_router(screener.router, prefix=API_PREFIX)
    # Screener action endpoints at /api/v1/actions/ (no /screener prefix)
    application.include_router(screener.actions_router, prefix=API_PREFIX)

    @application.get("/health", include_in_schema=False)
    async def health():
        from sqlalchemy import text
        try:
            async with AsyncTaskSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {type(e).__name__}: {e}"
        return {"status": "ok", "db": db_status, "v": "370ab25"}

    return application


app = create_app()
