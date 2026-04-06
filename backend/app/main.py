from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# Import models so SQLAlchemy mapper registry is populated before any route
# handlers execute (required for relationship resolution).
import app.models  # noqa: F401


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

    # Routers registered here as they are implemented (see Section 13 / SPEC.md)
    # from app.routers import auth, jobs, candidates, ...
    # application.include_router(auth.router, prefix="/api/v1")

    return application


app = create_app()
