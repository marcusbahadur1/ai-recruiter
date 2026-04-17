import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / response schemas (auth-specific, not DB-backed) ─────────────────


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    firm_name: str
    slug: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    message: str = ""  # non-empty when email confirmation is required


# ── Helpers ───────────────────────────────────────────────────────────────────


def _generate_slug(name: str) -> str:
    """Derive a URL-safe slug from a firm name, with a short random suffix."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50]
    suffix = uuid.uuid4().hex[:6]
    return f"{base}-{suffix}"


# ── Supabase Auth helpers ─────────────────────────────────────────────────────


def _supabase_headers(*, use_service_key: bool = False) -> dict[str, str]:
    key = (
        settings.supabase_service_key if use_service_key else settings.supabase_anon_key
    )
    headers: dict[str, str] = {"apikey": key, "Content-Type": "application/json"}
    if use_service_key:
        # Admin endpoints require Authorization: Bearer in addition to apikey
        headers["Authorization"] = f"Bearer {key}"
    return headers


async def _supabase_post(
    path: str, payload: dict, *, use_service_key: bool = False
) -> dict:
    url = f"{settings.supabase_url}/auth/v1{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=payload,
            headers=_supabase_headers(use_service_key=use_service_key),
        )
    return resp


async def _supabase_put(path: str, payload: dict) -> httpx.Response:
    url = f"{settings.supabase_url}/auth/v1{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            url,
            json=payload,
            headers=_supabase_headers(use_service_key=True),
        )
    return resp


async def _supabase_admin_get_user_by_email(email: str) -> dict | None:
    """Look up a Supabase Auth user by email using the admin API."""
    url = f"{settings.supabase_url}/auth/v1/admin/users"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params={"email": email},
            headers=_supabase_headers(use_service_key=True),
        )
    if resp.status_code != 200:
        logger.warning(
            "Admin user lookup failed: status=%d body=%s", resp.status_code, resp.text
        )
        return None
    data = resp.json()
    users = data.get("users", [])
    return next((u for u in users if u.get("email") == email), None)


async def _create_tenant_and_tag(
    firm_name: str, slug: str, supabase_user_id: str, db: AsyncSession
) -> Tenant:
    """Insert a Tenant row and write tenant_id into the Supabase user's app_metadata.

    If a tenant already exists for this supabase_user_id, return it instead of
    creating a duplicate.
    """
    existing = await db.scalar(
        select(Tenant).where(Tenant.user_id == uuid.UUID(supabase_user_id))
    )
    if existing:
        logger.info(
            "_create_tenant_and_tag: tenant already exists for user %s — reusing",
            supabase_user_id,
        )
        return existing

    now = datetime.now(timezone.utc)
    tenant = Tenant(
        id=uuid.uuid4(),
        name=firm_name,
        slug=slug,
        user_id=uuid.UUID(supabase_user_id),
        email_inbox=f"jobs-{slug}@airecruiterz.com",
        credits_remaining=10,
        plan="trial",
        trial_started_at=now,
        trial_ends_at=now + timedelta(days=14),
    )
    db.add(tenant)
    await db.commit()

    meta_resp = await _supabase_put(
        f"/admin/users/{supabase_user_id}",
        {"app_metadata": {"tenant_id": str(tenant.id), "role": "admin"}},
    )
    if meta_resp.status_code not in (200, 201):
        logger.error(
            "Metadata tag failed for user %s: status=%d body=%s",
            supabase_user_id,
            meta_resp.status_code,
            meta_resp.text,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tenant created but failed to tag user metadata: {meta_resp.text}",
        )
    return tenant


# ── Routes ────────────────────────────────────────────────────────────────────


async def _handle_existing_user(
    email: str, firm_name: str, slug: str, db: AsyncSession
) -> TokenResponse:
    """Handle retry when Supabase says the user already exists.

    Two sub-cases:
    1. User exists AND has tenant_id in app_metadata → just return success.
    2. User exists but has NO tenant_id (orphaned from a previous partial signup)
       → create the tenant now and tag the metadata.
    """
    user = await _supabase_admin_get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    supabase_user_id: str = user["id"]
    existing_tenant_id: str | None = (user.get("app_metadata") or {}).get("tenant_id")

    if existing_tenant_id:
        # Already fully set up — tell the frontend to redirect to login
        return TokenResponse(
            access_token="",
            refresh_token="",
            user_id=supabase_user_id,
            tenant_id=existing_tenant_id,
            message="Account already exists. Please sign in.",
        )

    # Orphaned user — create tenant and tag now
    tenant = await _create_tenant_and_tag(firm_name, slug, supabase_user_id, db)
    return TokenResponse(
        access_token="",
        refresh_token="",
        user_id=supabase_user_id,
        tenant_id=str(tenant.id),
        message="Please check your email and click the confirmation link before signing in.",
    )


@router.post(
    "/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create a Supabase Auth user and a linked Tenant record."""
    slug = body.slug or _generate_slug(body.firm_name)

    # 1. Register user in Supabase Auth
    resp = await _supabase_post(
        "/signup", {"email": body.email, "password": body.password}
    )
    auth_data = resp.json()
    logger.info(
        "Supabase /signup status=%d keys=%s", resp.status_code, list(auth_data.keys())
    )

    # Handle "user already registered" — retry-safe path
    if resp.status_code == 422 or (
        resp.status_code == 400
        and "already registered"
        in (auth_data.get("msg") or auth_data.get("message") or "").lower()
    ):
        return await _handle_existing_user(body.email, body.firm_name, slug, db)

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=auth_data.get("msg")
            or auth_data.get("message")
            or "Supabase signup failed",
        )

    # Supabase returns two different shapes depending on email-confirmation setting:
    #
    #   Auto-confirm ON  → {"access_token": "…", "refresh_token": "…", "user": {"id": "…", …}}
    #   Auto-confirm OFF → {"id": "…", "email": "…", …}  ← user object IS the root; no tokens
    #
    if "user" in auth_data:
        user_obj = auth_data["user"]
        access_token: str = auth_data.get("access_token", "")
        refresh_token: str = auth_data.get("refresh_token", "")
        needs_confirmation = False
    elif "id" in auth_data:
        user_obj = auth_data
        access_token = ""
        refresh_token = ""
        needs_confirmation = True
    else:
        logger.error("Unrecognised Supabase signup payload: %s", auth_data)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected response from Supabase — check server logs",
        )

    supabase_user_id: str = user_obj["id"]

    # 2. Create Tenant record and tag Supabase user metadata
    tenant = await _create_tenant_and_tag(body.firm_name, slug, supabase_user_id, db)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=supabase_user_id,
        tenant_id=str(tenant.id),
        message="Please check your email and click the confirmation link before signing in."
        if needs_confirmation
        else "",
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Authenticate with Supabase and return a JWT."""
    resp = await _supabase_post(
        "/token?grant_type=password",
        {"email": body.email, "password": body.password},
    )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    data = resp.json()
    user_id: str = data["user"]["id"]
    tenant_id: str = (data["user"].get("app_metadata") or {}).get("tenant_id", "")

    return TokenResponse(
        access_token=data["access_token"],
        user_id=user_id,
        tenant_id=tenant_id,
    )


# ── Dependency ────────────────────────────────────────────────────────────────


async def get_current_tenant(
    authorization: Annotated[str | None, Header()] = None,
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Validate the Supabase JWT and return the associated Tenant.

    Accepts the JWT via the Authorization header (normal API calls) or via the
    ``?token=`` query parameter (SSE / EventSource connections, which cannot
    send custom headers from the browser).

    The tenant_id is read from app_metadata embedded in the JWT, validated
    against Supabase's /auth/v1/user endpoint to confirm the token is live.
    tenant_id is NEVER trusted from the request body.
    """
    raw_token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization[len("Bearer ") :]
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization required"
        )

    token = raw_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    user_data = resp.json()
    tenant_id_str: str | None = (user_data.get("app_metadata") or {}).get("tenant_id")
    if not tenant_id_str:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant associated with this account",
        )

    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Malformed tenant_id in token"
        )

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tenant not found or inactive"
        )

    return tenant
