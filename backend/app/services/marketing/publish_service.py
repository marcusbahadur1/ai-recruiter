"""LinkedIn multi-page publish service.

Provides two async functions used by both the Celery task and the
retry-failed API route:

  publish_single_page(post, page_urn, access_token, client, db)
    — Posts to one page URN; updates post.publish_results in-place.
      Commits the DB row but does NOT update the overall post status.

  publish_post_to_all_pages(post, db)
    — Iterates over post.target_pages, calls publish_single_page for
      each pending/failed URN, then sets post.status to posted/partial/failed.

Token refresh uses the 7-day threshold (168 h) per the spec.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketing import LinkedInPage, MarketingAccount, MarketingPost
from app.services.marketing.linkedin_client import (
    LinkedInAuthError,
    LinkedInClient,
    LinkedInRateLimitError,
)

logger = logging.getLogger(__name__)

_TOKEN_REFRESH_HOURS = 168  # 7 days


async def _get_token_for_page(
    page_urn: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[MarketingAccount | None, str | None]:
    """Look up the MarketingAccount for a given page URN and return the decrypted token.

    Refreshes the access token if expiring within 7 days.
    Returns (account, access_token) or (None, None) if unavailable.
    """
    # Find the LinkedInPage record for this tenant + URN
    page_result = await db.execute(
        select(LinkedInPage).where(
            LinkedInPage.tenant_id == tenant_id,
            LinkedInPage.page_urn == page_urn,
        )
    )
    li_page = page_result.scalar_one_or_none()
    if not li_page:
        # Page not in our DB — look up account directly by URN for backward compat
        account_result = await db.execute(
            select(MarketingAccount).where(
                MarketingAccount.tenant_id == tenant_id,
                MarketingAccount.is_active.is_(True),
            )
        )
        account = account_result.scalars().first()
    else:
        account_result = await db.execute(
            select(MarketingAccount).where(
                MarketingAccount.id == li_page.linkedin_account_id,
            )
        )
        account = account_result.scalar_one_or_none()

    if not account or not account.is_active:
        return None, None

    if account.needs_reconnect:
        logger.warning("account=%s needs_reconnect — skipping page=%s", account.id, page_urn)
        return account, None

    # Refresh if expiring soon
    if account.is_token_expiring_soon(hours=_TOKEN_REFRESH_HOURS):
        refreshed = await _refresh_token(account, db)
        if not refreshed:
            return account, None

    access_token, _ = account.get_decrypted_tokens()
    return account, access_token


async def _refresh_token(account: MarketingAccount, db: AsyncSession) -> bool:
    """Refresh the access token. Returns True on success, False on failure."""
    client = LinkedInClient()
    try:
        _, refresh_token_enc = account.access_token, account.refresh_token
        _, plain_refresh = account.get_decrypted_tokens()
        tokens = await client.refresh_access_token(plain_refresh)
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 5184000))
        account.set_encrypted_tokens(tokens["access_token"], tokens["refresh_token"])
        account.token_expires_at = expires_at
        account.needs_reconnect = False
        await db.commit()
        logger.info("Token refreshed for account=%s", account.id)
        return True
    except Exception as exc:
        logger.error("Token refresh failed for account=%s: %s", account.id, exc)
        account.needs_reconnect = True
        await db.commit()
        return False


async def publish_single_page(
    post: MarketingPost,
    page_urn: str,
    access_token: str,
    client: LinkedInClient,
    db: AsyncSession,
) -> dict[str, Any]:
    """Post to one LinkedIn page URN. Updates post.publish_results for this URN.

    Returns the result dict: {status, post_id, posted_at} or {status, error}.
    Does not change post.status — caller handles overall status.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    results: dict[str, Any] = dict(post.publish_results or {})

    try:
        post_urn = await client.create_post_v2(
            access_token=access_token,
            author_urn=page_urn,
            text=post.content,
            hashtags=list(post.hashtags or []),
            image_url=post.image_url if post.include_image else None,
        )
        result: dict[str, Any] = {
            "status": "posted",
            "post_id": post_urn,
            "posted_at": now_iso,
        }
        logger.info(
            "publish_single_page: posted page_urn=%s post=%s post_urn=%s",
            page_urn, post.id, post_urn,
        )
    except LinkedInAuthError as exc:
        result = {"status": "failed", "error": f"Auth error: {str(exc)[:200]}"}
        logger.error("publish_single_page: auth error page=%s post=%s: %s", page_urn, post.id, exc)
    except LinkedInRateLimitError:
        result = {"status": "failed", "error": "Rate limit exceeded"}
        logger.warning("publish_single_page: rate limit page=%s post=%s", page_urn, post.id)
    except Exception as exc:
        result = {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        logger.error("publish_single_page: error page=%s post=%s: %s", page_urn, post.id, exc)

    results[page_urn] = result
    post.publish_results = results
    await db.commit()
    return result


async def publish_post_to_all_pages(
    post: MarketingPost,
    db: AsyncSession,
    retry_failed_only: bool = False,
) -> None:
    """Publish a content post to all target_pages.

    If retry_failed_only=True, only retries pages where publish_results[urn].status == 'failed'.
    Sets post.status to 'posted', 'partial', or 'failed' after all attempts.
    Sets post.posted_at on first successful page.
    """
    target_urns: list[str] = list(post.target_pages or [])

    if not target_urns:
        # Backward compat: no target_pages set — post to account default URN
        account_result = await db.execute(
            select(MarketingAccount).where(
                MarketingAccount.id == post.account_id,
                MarketingAccount.is_active.is_(True),
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            post.status = "failed"
            await db.commit()
            return
        target_urns = [account.author_urn]

    client = LinkedInClient()
    existing_results: dict[str, Any] = dict(post.publish_results or {})
    now = datetime.now(timezone.utc)

    for page_urn in target_urns:
        if retry_failed_only:
            existing = existing_results.get(page_urn, {})
            if existing.get("status") != "failed":
                continue  # skip already-posted and pending pages

        account, access_token = await _get_token_for_page(
            page_urn, post.tenant_id, db
        )
        if access_token is None:
            existing_results[page_urn] = {
                "status": "failed",
                "error": "No valid access token — reconnect LinkedIn",
            }
            post.publish_results = existing_results
            await db.commit()
            continue

        await publish_single_page(post, page_urn, access_token, client, db)

    # Refresh results after all publishes
    final_results: dict[str, Any] = dict(post.publish_results or {})
    statuses = [r.get("status") for r in final_results.values()]

    succeeded = statuses.count("posted")
    failed = statuses.count("failed")
    total = len(statuses)

    if succeeded == total:
        post.status = "posted"
        if not post.posted_at:
            post.posted_at = now
        # Set platform_post_id from first successful page for backward compat
        for urn, res in final_results.items():
            if res.get("status") == "posted" and res.get("post_id"):
                post.platform_post_id = res["post_id"]
                break
    elif succeeded > 0:
        post.status = "partial"
        if not post.posted_at:
            post.posted_at = now
    else:
        post.status = "failed"

    await db.commit()
    logger.info(
        "publish_post_to_all_pages: post=%s succeeded=%d failed=%d total=%d status=%s",
        post.id, succeeded, failed, total, post.status,
    )


async def sync_linkedin_pages(
    tenant_id: uuid.UUID,
    account_id: uuid.UUID,
    access_token: str,
    db: AsyncSession,
) -> list:
    """Discover and upsert all LinkedIn pages for a tenant's connected account.

    Step 1 — Personal profile (via /v2/userinfo)
    Step 2 — Admin pages (company + showcase) via /rest/organizationAcls

    On 403 for step 2 (missing w_organization_social scope):
      — Logs warning, marks account.needs_reconnect = False (personal still works)
      — Still saves the personal profile page.

    Returns list of LinkedInPage ORM objects upserted.
    """
    from datetime import datetime, timezone
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.marketing import LinkedInPage

    client = LinkedInClient()
    now = datetime.now(timezone.utc)
    upserted: list[LinkedInPage] = []

    # ── Step 1: Personal profile ───────────────────────────────────────────────
    try:
        profile = await client.get_personal_profile(access_token)
        member_id = profile.get("id", "")
        if member_id:
            personal_urn = f"urn:li:person:{member_id}"
            page = await _upsert_page(
                db=db,
                tenant_id=tenant_id,
                account_id=account_id,
                page_type="personal",
                page_name=profile.get("name") or "Personal Profile",
                page_urn=personal_urn,
                page_id=member_id,
                vanity_name=None,
                logo_url=profile.get("picture"),
                follower_count=None,
                now=now,
            )
            upserted.append(page)
    except Exception as exc:
        logger.warning("sync_linkedin_pages: personal profile fetch failed: %s", exc)

    # ── Step 2: Admin pages (company + showcase) ───────────────────────────────
    try:
        admin_pages = await client.get_admin_pages(access_token)
    except Exception as exc:
        logger.warning("sync_linkedin_pages: get_admin_pages failed: %s", exc)
        admin_pages = []

    # Update needs_reconnect flag on account based on whether we got scoped access
    # (403 already logged inside get_admin_pages — don't change needs_reconnect here)

    for item in admin_pages:
        org_urn: str = item.get("organizationalTarget", "")
        if not org_urn or ":" not in org_urn:
            continue
        org_id = org_urn.split(":")[-1]

        try:
            org_data = await client.get_organization(access_token, org_id)
            if org_data is None:
                continue

            page_name = org_data.get("localizedName", org_id)
            vanity = org_data.get("vanityName")
            # Showcase pages have a parentOrganization field
            has_parent = bool(org_data.get("parentOrganization"))
            page_type = "showcase" if has_parent else "company"

            page = await _upsert_page(
                db=db,
                tenant_id=tenant_id,
                account_id=account_id,
                page_type=page_type,
                page_name=page_name,
                page_urn=org_urn,
                page_id=org_id,
                vanity_name=vanity,
                logo_url=None,  # logo requires extra API call; skip for now
                follower_count=None,
                now=now,
            )
            upserted.append(page)
        except Exception as exc:
            logger.warning(
                "sync_linkedin_pages: org_id=%s lookup failed, skipping: %s", org_id, exc
            )
            continue

    logger.info(
        "sync_linkedin_pages: tenant=%s pages upserted=%d", tenant_id, len(upserted)
    )
    return upserted


async def _upsert_page(
    *,
    db: AsyncSession,
    tenant_id: uuid.UUID,
    account_id: uuid.UUID,
    page_type: str,
    page_name: str,
    page_urn: str,
    page_id: str,
    vanity_name: str | None,
    logo_url: str | None,
    follower_count: int | None,
    now: datetime,
):
    """Insert or update a LinkedInPage row (upsert on tenant_id + page_urn)."""
    from app.models.marketing import LinkedInPage

    result = await db.execute(
        select(LinkedInPage).where(
            LinkedInPage.tenant_id == tenant_id,
            LinkedInPage.page_urn == page_urn,
        )
    )
    page = result.scalar_one_or_none()

    if page is None:
        page = LinkedInPage(
            tenant_id=tenant_id,
            linkedin_account_id=account_id,
            page_urn=page_urn,
            page_id=page_id,
        )
        db.add(page)

    page.linkedin_account_id = account_id
    page.page_type = page_type
    page.page_name = page_name
    page.page_id = page_id
    if vanity_name is not None:
        page.vanity_name = vanity_name
    if logo_url is not None:
        page.logo_url = logo_url
    if follower_count is not None:
        page.follower_count = follower_count
    page.last_synced_at = now

    await db.commit()
    await db.refresh(page)
    return page
