from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# Populate SQLAlchemy mapper registry before any route handlers execute.
import app.models  # noqa: F401

from app.routers import (
    applications,
    audit,
    auth,
    candidates,
    chat_sessions,
    jobs,
    promo_codes,
    rag,
    super_admin,
    tenants,
    webhooks,
    widget,
)

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    application = FastAPI(
        title="AI Recruiter API",
        version="3.0.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router_module in (
        auth,
        tenants,
        jobs,
        candidates,
        chat_sessions,
        rag,
        promo_codes,
        webhooks,
        super_admin,
        audit,
        widget,
    ):
        application.include_router(router_module.router, prefix=API_PREFIX)

    # Applications router has mixed prefixes (/applications, /test, /actions)
    application.include_router(applications.router, prefix=API_PREFIX)

    return application


app = create_app()
