"""LinkedIn OAuth routes for the AI Marketing Module.

Handles the full OAuth 2.0 flow: authorization URL generation, callback
handling, multi-page company selection, and account disconnection.

Routes:
  POST /marketing/accounts/linkedin/connect       — start OAuth flow
  GET  /marketing/accounts/linkedin/callback      — OAuth callback
  GET  /marketing/accounts/linkedin/select-page/pages  — list pages for multi-page picker
  POST /marketing/accounts/linkedin/select-page   — complete multi-page selection
  GET  /marketing/accounts                        — list connected accounts
  DELETE /marketing/accounts/{account_id}         — disconnect account
"""
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_marketing_limits, settings
from app.database import get_db
from app.models.marketing import MarketingAccount
from app.routers.auth import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.marketing import MarketingAccountRead
from app.services.marketing.linkedin_client import LinkedInAuthError, LinkedInClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing-oauth"])

_STATE_TTL = 600       # 10 minutes — OAuth state validity
_TEMP_TOKEN_TTL = 900  # 15 minutes — multi-page selection window


# ── Redis helper ───────────────────────────────────────────────────────────────


def _redis() -> redis_lib.Redis:
    return redis_lib.from_url(
        settings.redis_url, socket_connect_timeout=2, decode_responses=True
    )


# ── Request / response schemas ─────────────────────────────────────────────────


class LinkedInConnectRequest(BaseModel):
    account_type: str  # 'personal' | 'company'
    locale: str = "en"


class SelectPageRequest(BaseModel):
    temp_token: str
    organization_id: str
    organization_name: str


class ConnectResponse(BaseModel):
    authorization_url: str


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.post("/accounts/linkedin/connect", response_model=ConnectResponse)
async def connect_linkedin(
    body: LinkedInConnectRequest,
    tenant: Tenant = Depends(get_current_tenant),
) -> ConnectResponse:
    """Generate a LinkedIn OAuth authorization URL and store state in Redis."""
    limits = get_marketing_limits(tenant.plan)
    if not limits["linkedin_connect"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"LinkedIn connect requires Agency Small plan or above (current: {tenant.plan})",
        )

    if body.account_type not in ("personal", "company"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="account_type must be 'personal' or 'company'",
        )

    # Generate a random nonce — used as both the OAuth state parameter and Redis key
    nonce = secrets.token_urlsafe(32)
    state_data = {
        "nonce": nonce,
        "tenant_id": str(tenant.id),
        "account_type": body.account_type,
        "locale": body.locale,
    }
    try:
        _redis().setex(f"marketing:oauth_state:{nonce}", _STATE_TTL, json.dumps(state_data))
    except Exception as exc:
        logger.error("Redis unavailable for OAuth state storage: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis unavailable — cannot initiate OAuth flow",
        )

    auth_url = LinkedInClient().get_authorization_url(
        state=nonce, account_type=body.account_type
    )
    return ConnectResponse(authorization_url=auth_url)


@router.get("/accounts/linkedin/callback")
async def linkedin_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle LinkedIn OAuth callback.

    Exchanges the authorization code for tokens, fetches profile/pages,
    and upserts a MarketingAccount record. Redirects to the frontend
    marketing page on success or failure.
    """
    # Retrieve and validate state from Redis
    state_data, locale, tenant_id_str, account_type, error_redirect = _consume_state(
        state, error
    )
    if error_redirect:
        return error_redirect

    try:
        client = LinkedInClient()
        tokens = await client.exchange_code_for_tokens(code)
    except LinkedInAuthError as exc:
        logger.warning("LinkedIn token exchange failed: %s", exc)
        return _redirect_error(locale, "auth_failed")
    except Exception as exc:
        logger.error("LinkedIn token exchange error: %s", exc)
        return _redirect_error(locale, "auth_failed")

    access_token: str = tokens["access_token"]
    refresh_token: str = tokens["refresh_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 5184000))
    tenant_id = uuid.UUID(tenant_id_str)

    if account_type == "personal":
        return await _handle_personal(
            db, client, access_token, refresh_token, expires_at, tenant_id, locale
        )
    else:
        return await _handle_company(
            db, client, access_token, refresh_token, expires_at, tenant_id, locale
        )


@router.get("/accounts/linkedin/select-page/pages")
async def get_select_page_options(
    token: str = Query(...),
) -> dict:
    """Return the list of available company pages stored under a temp token.

    Called by the frontend select-page UI to populate the radio list.
    """
    try:
        raw = _redis().get(f"marketing:oauth_temp:{token}")
    except Exception as exc:
        logger.error("Redis unavailable for temp token lookup: %s", exc)
        raise HTTPException(status_code=503, detail="Redis unavailable")

    if not raw:
        raise HTTPException(status_code=404, detail="Token expired or not found")

    data = json.loads(raw)
    return {"pages": data.get("pages", [])}


@router.post("/accounts/linkedin/select-page")
async def select_linkedin_page(
    body: SelectPageRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Complete company page selection when multiple pages were found during OAuth."""
    try:
        raw = _redis().get(f"marketing:oauth_temp:{body.temp_token}")
    except Exception as exc:
        logger.error("Redis unavailable for temp token lookup: %s", exc)
        raise HTTPException(status_code=503, detail="Redis unavailable")

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selection token expired or not found — please reconnect",
        )

    data = json.loads(raw)
    access_token: str = data["access_token"]
    refresh_token: str = data["refresh_token"]
    expires_at = datetime.fromisoformat(data["expires_at"])

    await _upsert_account(
        db=db,
        tenant_id=tenant.id,
        platform="linkedin",
        account_type="company",
        account_name=body.organization_name,
        linkedin_urn=body.organization_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )

    # Clean up temp token
    try:
        _redis().delete(f"marketing:oauth_temp:{body.temp_token}")
    except Exception:
        pass

    return {"success": True}


@router.get("/accounts", response_model=list[MarketingAccountRead])
async def list_accounts(
    tenant_id_override: uuid.UUID | None = Query(None, alias="tenant_id"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[MarketingAccountRead]:
    """List connected LinkedIn accounts.

    Super admin can pass ?tenant_id= to view any tenant's accounts.
    Omit tenant_id to list the current tenant's accounts.
    """
    is_super = getattr(tenant, "_is_super_admin", False)

    if tenant_id_override is not None and not is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required to view another tenant's accounts",
        )

    target_id = tenant_id_override if (is_super and tenant_id_override is not None) else tenant.id

    result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.tenant_id == target_id,
            MarketingAccount.is_active.is_(True),
        )
    )
    accounts = result.scalars().all()
    return [MarketingAccountRead.from_orm(a) for a in accounts]


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    account_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect a LinkedIn account.

    Sets is_active=False and returns all scheduled posts for this account
    to 'draft' status (so they are not published without a valid connection).
    """
    result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.id == account_id,
            MarketingAccount.tenant_id == tenant.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    account.is_active = False

    # Return all scheduled posts for this account to draft
    from app.models.marketing import MarketingPost
    await db.execute(
        update(MarketingPost)
        .where(
            MarketingPost.account_id == account_id,
            MarketingPost.status == "scheduled",
        )
        .values(status="draft")
    )
    await db.commit()
    logger.info("Marketing account %s disconnected for tenant %s", account_id, tenant.id)


# ── Internal helpers ───────────────────────────────────────────────────────────


def _consume_state(
    state: str | None,
    error: str | None,
) -> tuple[dict | None, str, str, str, RedirectResponse | None]:
    """Validate and consume the OAuth state from Redis.

    Returns (state_data, locale, tenant_id_str, account_type, error_redirect).
    error_redirect is non-None when validation fails.
    """
    default_locale = "en"

    if error:
        logger.warning("LinkedIn OAuth returned error=%s", error)
        return None, default_locale, "", "", _redirect_error(default_locale, "auth_failed")

    if not state:
        return None, default_locale, "", "", _redirect_error(default_locale, "auth_failed")

    try:
        raw = _redis().get(f"marketing:oauth_state:{state}")
    except Exception as exc:
        logger.error("Redis unavailable during OAuth callback: %s", exc)
        return None, default_locale, "", "", _redirect_error(default_locale, "auth_failed")

    if not raw:
        logger.warning("OAuth state not found or expired: %s", state[:16])
        return None, default_locale, "", "", _redirect_error(default_locale, "state_expired")

    state_data = json.loads(raw)
    locale = state_data.get("locale", default_locale)
    tenant_id_str = state_data.get("tenant_id", "")
    account_type = state_data.get("account_type", "personal")

    # Consume the state (one-time use)
    try:
        _redis().delete(f"marketing:oauth_state:{state}")
    except Exception:
        pass

    return state_data, locale, tenant_id_str, account_type, None


async def _handle_personal(
    db: AsyncSession,
    client: LinkedInClient,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    tenant_id: uuid.UUID,
    locale: str,
) -> RedirectResponse:
    try:
        profile = await client.get_personal_profile(access_token)
    except Exception as exc:
        logger.error("LinkedIn get_personal_profile failed: %s", exc)
        return _redirect_error(locale, "auth_failed")

    first = profile.get("localizedFirstName", "")
    last = profile.get("localizedLastName", "")
    account_name = f"{first} {last}".strip() or "LinkedIn User"
    linkedin_urn = profile.get("id", "")

    await _upsert_account(
        db=db,
        tenant_id=tenant_id,
        platform="linkedin",
        account_type="personal",
        account_name=account_name,
        linkedin_urn=linkedin_urn,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    return _redirect_success(locale)


async def _handle_company(
    db: AsyncSession,
    client: LinkedInClient,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    tenant_id: uuid.UUID,
    locale: str,
) -> RedirectResponse:
    try:
        pages = await client.get_company_pages(access_token)
    except Exception as exc:
        logger.error("LinkedIn get_company_pages failed: %s", exc)
        return _redirect_error(locale, "auth_failed")

    if len(pages) == 1:
        page = pages[0]
        await _upsert_account(
            db=db,
            tenant_id=tenant_id,
            platform="linkedin",
            account_type="company",
            account_name=page.get("organizationName", "Company Page"),
            linkedin_urn=page.get("organizationId", ""),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        return _redirect_success(locale)

    if len(pages) == 0:
        logger.warning("LinkedIn OAuth: no company pages found for tenant %s", tenant_id)
        return _redirect_error(locale, "no_pages")

    # Multiple pages — store tokens in Redis and redirect to page selector
    temp_token = secrets.token_urlsafe(32)
    temp_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at.isoformat(),
        "tenant_id": str(tenant_id),
        "pages": pages,
    }
    try:
        _redis().setex(
            f"marketing:oauth_temp:{temp_token}", _TEMP_TOKEN_TTL, json.dumps(temp_data)
        )
    except Exception as exc:
        logger.error("Redis unavailable for temp token storage: %s", exc)
        return _redirect_error(locale, "auth_failed")

    frontend = settings.frontend_url.rstrip("/")
    return RedirectResponse(
        url=f"{frontend}/{locale}/marketing/linkedin/select-page?token={temp_token}",
        status_code=302,
    )


async def _upsert_account(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    platform: str,
    account_type: str,
    account_name: str,
    linkedin_urn: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> MarketingAccount:
    """Insert or update a MarketingAccount row (upsert on tenant+platform+account_type)."""
    result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.tenant_id == tenant_id,
            MarketingAccount.platform == platform,
            MarketingAccount.account_type == account_type,
        )
    )
    account = result.scalar_one_or_none()

    if account is None:
        account = MarketingAccount(
            tenant_id=tenant_id,
            platform=platform,
            account_type=account_type,
        )
        db.add(account)

    account.account_name = account_name
    account.linkedin_urn = linkedin_urn
    account.token_expires_at = expires_at
    account.is_active = True
    account.set_encrypted_tokens(access_token, refresh_token)

    await db.commit()
    await db.refresh(account)
    logger.info(
        "Marketing account upserted tenant=%s platform=%s type=%s",
        tenant_id,
        platform,
        account_type,
    )
    return account


def _redirect_success(locale: str) -> RedirectResponse:
    frontend = settings.frontend_url.rstrip("/")
    return RedirectResponse(
        url=f"{frontend}/{locale}/marketing?connected=true", status_code=302
    )


def _redirect_error(locale: str, reason: str) -> RedirectResponse:
    frontend = settings.frontend_url.rstrip("/")
    return RedirectResponse(
        url=f"{frontend}/{locale}/marketing?error={reason}", status_code=302
    )
