import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.tenant import Tenant

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / response schemas (auth-specific, not DB-backed) ─────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    firm_name: str
    slug: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str


# ── Supabase Auth helpers ─────────────────────────────────────────────────────

def _supabase_headers(*, use_service_key: bool = False) -> dict[str, str]:
    key = settings.supabase_service_key if use_service_key else settings.supabase_anon_key
    return {"apikey": key, "Content-Type": "application/json"}


async def _supabase_post(path: str, payload: dict, *, use_service_key: bool = False) -> dict:
    url = f"{settings.supabase_url}/auth/v1{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=_supabase_headers(use_service_key=use_service_key))
    return resp


async def _supabase_put(path: str, payload: dict) -> httpx.Response:
    url = f"{settings.supabase_url}/auth/v1{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            url, json=payload,
            headers=_supabase_headers(use_service_key=True),
        )
    return resp


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create a Supabase Auth user and a linked Tenant record."""
    # 1. Register user in Supabase Auth
    resp = await _supabase_post("/signup", {"email": body.email, "password": body.password})
    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=resp.json().get("msg", "Supabase signup failed"),
        )
    auth_data = resp.json()
    supabase_user_id: str = auth_data["user"]["id"]
    access_token: str = auth_data.get("access_token", "")

    # 2. Create Tenant record
    tenant = Tenant(
        id=uuid.uuid4(),
        name=body.firm_name,
        slug=body.slug,
        email_inbox=f"jobs-{body.slug}@airecruiterz.com",
    )
    async with db.begin():
        db.add(tenant)

    # 3. Tag the Supabase user with tenant_id in app_metadata (embedded in JWT)
    await _supabase_put(
        f"/admin/users/{supabase_user_id}",
        {"app_metadata": {"tenant_id": str(tenant.id), "role": "admin"}},
    )

    return TokenResponse(
        access_token=access_token,
        user_id=supabase_user_id,
        tenant_id=str(tenant.id),
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
    authorization: Annotated[str, Header()],
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Validate the Supabase JWT and return the associated Tenant.

    The tenant_id is read from app_metadata embedded in the JWT, validated
    against Supabase's /auth/v1/user endpoint to confirm the token is live.
    tenant_id is NEVER trusted from the request body.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")

    token = authorization[len("Bearer "):]

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_data = resp.json()
    tenant_id_str: str | None = (user_data.get("app_metadata") or {}).get("tenant_id")
    if not tenant_id_str:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant associated with this account")

    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Malformed tenant_id in token")

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant not found or inactive")

    return tenant
