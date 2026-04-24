"""Celery tasks for the AI Marketing Module.

Beat schedule is defined at the bottom of this file and merged into
celery_app.beat_schedule in celery_app.py.

All tasks follow the same async pattern as scheduled_tasks.py:
  - Synchronous @celery_app.task wrapper calls asyncio.run()
  - Actual logic lives in an async _*_async() helper
  - Each row/account is wrapped in try/except so one failure can't block others
  - DB access uses AsyncTaskSessionLocal (NullPool, safe for Celery workers)
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, update

from app.database import AsyncTaskSessionLocal as AsyncSessionLocal
from app.models.marketing import (
    MarketingAccount,
    MarketingEngagement,
    MarketingPost,
    MarketingSettings,
)
from app.models.tenant import Tenant
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# ── Task 6.1 — generate_and_schedule_posts ────────────────────────────────────


@celery_app.task(name="app.tasks.marketing_tasks.generate_and_schedule_posts")
def generate_and_schedule_posts() -> None:
    """Generate AI posts for all active marketing settings rows.

    Runs daily. Creates draft posts (requires_approval=True by default)
    scheduled for each account's configured post_time_utc.
    """
    asyncio.run(_generate_and_schedule_posts_async())


async def _generate_and_schedule_posts_async() -> None:
    from app.config import get_marketing_limits
    from app.services.marketing.content_generator import (
        ContentGenerationError,
        MarketingContentGenerator,
    )

    today = datetime.now(timezone.utc).date()
    generated = skipped = failed = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MarketingSettings).where(MarketingSettings.is_active.is_(True))
        )
        all_settings = result.scalars().all()

    for ms in all_settings:
        try:
            async with AsyncSessionLocal() as db:
                outcome = await _generate_for_settings(db, ms, today)
            if outcome == "generated":
                generated += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            logger.error(
                "generate_and_schedule_posts: failed for settings=%s: %s", ms.id, exc
            )

    logger.info(
        "generate_and_schedule_posts: %d generated, %d skipped, %d failed",
        generated,
        skipped,
        failed,
    )


async def _generate_for_settings(db, ms: MarketingSettings, today) -> str:
    from app.config import get_marketing_limits
    from app.services.marketing.content_generator import (
        ContentGenerationError,
        MarketingContentGenerator,
    )

    # Check frequency — is a post due today?
    weekday = today.weekday()  # Monday=0, Sunday=6
    if ms.post_frequency == "twice_weekly" and weekday not in (0, 3):
        return "skipped"
    if ms.post_frequency == "weekly" and weekday != 0:
        return "skipped"

    # Load the linked account
    account_result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.tenant_id == ms.tenant_id,
            MarketingAccount.platform == "linkedin",
            MarketingAccount.is_active.is_(True),
        )
    )
    account = account_result.scalars().first()
    if not account or account.is_token_expired:
        return "skipped"

    # Already posted or scheduled today?
    existing = await db.scalar(
        select(func.count())
        .select_from(MarketingPost)
        .where(
            MarketingPost.account_id == account.id,
            func.date(MarketingPost.scheduled_at) == today,
            MarketingPost.status.in_(["scheduled", "posted"]),
        )
    )
    if existing:
        return "skipped"

    # Check plan post-per-week limit
    if ms.tenant_id is not None:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == ms.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant:
            limits = get_marketing_limits(tenant.plan)
            posts_per_week = limits["posts_per_week"]
            if posts_per_week == 0:
                return "skipped"
            if posts_per_week is not None:
                week_start = today - timedelta(days=today.weekday())
                week_posts = await db.scalar(
                    select(func.count())
                    .select_from(MarketingPost)
                    .where(
                        MarketingPost.account_id == account.id,
                        func.date(MarketingPost.scheduled_at) >= week_start,
                        MarketingPost.status.in_(["scheduled", "posted", "draft"]),
                    )
                )
                if (week_posts or 0) >= posts_per_week:
                    return "skipped"
            # Build a minimal tenant-like object for AIProvider
            ai_tenant = tenant
        else:
            return "skipped"
    else:
        # Platform-level account — use a synthetic tenant with platform keys
        ai_tenant = _platform_tenant()

    # Load last 30 posts for rotation
    recent_result = await db.execute(
        select(MarketingPost)
        .where(MarketingPost.account_id == account.id)
        .order_by(MarketingPost.created_at.desc())
        .limit(30)
    )
    recent_posts = recent_result.scalars().all()

    generator = MarketingContentGenerator(ai_tenant)
    topic = generator.get_next_topic(ms, recent_posts)
    post_type = generator.get_next_post_type(ms, recent_posts)

    try:
        result_data = await generator.generate_post(ms, account, post_type, topic)
    except ContentGenerationError as exc:
        logger.warning(
            "generate_and_schedule_posts: content validation failed settings=%s: %s",
            ms.id,
            exc.detail,
        )
        return "skipped"

    scheduled_at = datetime.combine(today, ms.post_time_utc).replace(tzinfo=timezone.utc)

    post = MarketingPost(
        tenant_id=ms.tenant_id,
        account_id=account.id,
        platform="linkedin",
        post_type=post_type,
        content=result_data["content"],
        hashtags=result_data["hashtags"],
        topic=result_data["topic"],
        include_image=ms.include_images,
        image_search_query=result_data["image_search_query"],
        image_url=result_data["image_url"],
        image_attribution=result_data["image_attribution"],
        scheduled_at=scheduled_at,
        # All posts start as draft — requires approval before publishing
        status="draft" if ms.requires_approval else "scheduled",
    )
    db.add(post)
    await db.commit()
    logger.info(
        "generate_and_schedule_posts: post created type=%s topic=%r account=%s",
        post_type,
        topic,
        account.id,
    )
    return "generated"


# ── Task 6.2 — publish_scheduled_posts ───────────────────────────────────────


@celery_app.task(name="app.tasks.marketing_tasks.publish_scheduled_posts")
def publish_scheduled_posts() -> None:
    """Publish all posts whose scheduled_at <= now() and status='scheduled'.

    Runs every 15 minutes. Uses SELECT FOR UPDATE SKIP LOCKED to prevent
    concurrent workers from double-publishing the same post.
    """
    asyncio.run(_publish_scheduled_posts_async())


async def _publish_scheduled_posts_async() -> None:
    from app.services.marketing.linkedin_client import (
        LinkedInAuthError,
        LinkedInClient,
        LinkedInRateLimitError,
    )
    from app.services.sendgrid_email import send_email

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MarketingPost)
            .where(
                MarketingPost.status == "scheduled",
                MarketingPost.scheduled_at <= now,
            )
            .with_for_update(skip_locked=True)
            .limit(20)
        )
        posts = result.scalars().all()

        for post in posts:
            try:
                account_result = await db.execute(
                    select(MarketingAccount).where(
                        MarketingAccount.id == post.account_id
                    )
                )
                account = account_result.scalar_one_or_none()
                if not account or not account.is_active:
                    post.status = "failed"
                    await db.commit()
                    continue

                # Refresh token if expiring within 24h
                if account.is_token_expiring_soon(hours=24):
                    await _refresh_account_token(db, account)

                access_token, _ = account.get_decrypted_tokens()
                client = LinkedInClient()

                post_urn = await client.create_post(
                    access_token=access_token,
                    author_urn=account.author_urn,
                    text=post.content,
                    hashtags=post.hashtags or [],
                    image_url=post.image_url if post.include_image else None,
                )
                post.status = "posted"
                post.posted_at = datetime.now(timezone.utc)
                post.platform_post_id = post_urn
                await db.commit()
                logger.info("publish_scheduled_posts: posted urn=%s", post_urn)

            except LinkedInRateLimitError:
                # Back off 2 hours — do not increment retry_count
                post.scheduled_at = post.scheduled_at + timedelta(hours=2)
                await db.commit()
                logger.warning(
                    "publish_scheduled_posts: rate limit hit — rescheduled post=%s +2h",
                    post.id,
                )

            except LinkedInAuthError as exc:
                post.status = "failed"
                await db.commit()
                logger.error(
                    "publish_scheduled_posts: auth error post=%s: %s", post.id, exc
                )
                await _send_auth_alert(db, post, account if account else None, send_email)

            except Exception as exc:
                post.retry_count += 1
                if post.retry_count >= 3:
                    post.status = "failed"
                    logger.error(
                        "publish_scheduled_posts: post=%s permanently failed after 3 retries: %s",
                        post.id,
                        exc,
                    )
                else:
                    logger.warning(
                        "publish_scheduled_posts: post=%s retry %d/3: %s",
                        post.id,
                        post.retry_count,
                        exc,
                    )
                await db.commit()


# ── Task 6.3 — collect_post_stats ────────────────────────────────────────────


@celery_app.task(name="app.tasks.marketing_tasks.collect_post_stats")
def collect_post_stats() -> None:
    """Update likes, comments, impressions for all posts from the last 30 days."""
    asyncio.run(_collect_post_stats_async())


async def _collect_post_stats_async() -> None:
    from app.services.marketing.linkedin_client import LinkedInClient

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    updated = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MarketingPost)
            .where(
                MarketingPost.status == "posted",
                MarketingPost.platform_post_id.isnot(None),
                MarketingPost.posted_at >= cutoff,
            )
            .limit(200)
        )
        posts = result.scalars().all()

        # Process in batches of 50
        for i in range(0, len(posts), 50):
            batch = posts[i : i + 50]
            for post in batch:
                try:
                    account_result = await db.execute(
                        select(MarketingAccount).where(
                            MarketingAccount.id == post.account_id,
                            MarketingAccount.is_active.is_(True),
                        )
                    )
                    account = account_result.scalar_one_or_none()
                    if not account:
                        continue

                    access_token, _ = account.get_decrypted_tokens()
                    stats = await LinkedInClient().get_post_stats(
                        access_token, post.platform_post_id
                    )
                    post.likes = stats.get("num_likes", post.likes)
                    post.comments = stats.get("num_comments", post.comments)
                    post.impressions = stats.get("impressions", post.impressions)
                    updated += 1
                except Exception as exc:
                    logger.warning(
                        "collect_post_stats: failed for post=%s: %s", post.id, exc
                    )

            await db.commit()

    logger.info("collect_post_stats: updated %d post(s)", updated)


# ── Task 6.4 — auto_engage ────────────────────────────────────────────────────


@celery_app.task(
    name="app.tasks.marketing_tasks.auto_engage",
    queue="marketing",
    # Do not set a short soft_time_limit — this task sleeps 2-5min between
    # actions by design to stay within LinkedIn's rate limits.
)
def auto_engage() -> None:
    """Like and comment on relevant LinkedIn posts for all auto-engage accounts.

    Runs daily. Concurrency MUST be 1 on the marketing queue (see Phase 11).
    The mandatory 2-5 minute sleep between actions prevents rate-limit violations.
    """
    asyncio.run(_auto_engage_async())


async def _auto_engage_async() -> None:
    from app.config import get_marketing_limits
    from app.services.ai_provider import AIProvider
    from app.services.marketing.linkedin_client import LinkedInClient

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MarketingSettings).where(
                MarketingSettings.auto_engage.is_(True),
                MarketingSettings.is_active.is_(True),
            )
        )
        settings_rows = result.scalars().all()

    for ms in settings_rows:
        try:
            async with AsyncSessionLocal() as db:
                await _engage_for_settings(db, ms, today_start)
        except Exception as exc:
            logger.error(
                "auto_engage: failed for settings=%s: %s", ms.id, exc
            )


async def _engage_for_settings(db, ms: MarketingSettings, today_start: datetime) -> None:
    from app.config import get_marketing_limits
    from app.services.marketing.linkedin_client import LinkedInClient

    if ms.tenant_id is not None:
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == ms.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            return
        limits = get_marketing_limits(tenant.plan)
        if not limits["auto_engage"]:
            return
        ai_tenant = tenant
    else:
        ai_tenant = _platform_tenant()

    account_result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.tenant_id == ms.tenant_id,
            MarketingAccount.platform == "linkedin",
            MarketingAccount.is_active.is_(True),
        )
    )
    account = account_result.scalars().first()
    if not account or account.is_token_expired:
        return

    # Count today's engagements already performed
    today_count = await db.scalar(
        select(func.count())
        .select_from(MarketingEngagement)
        .where(
            MarketingEngagement.account_id == account.id,
            MarketingEngagement.performed_at >= today_start,
        )
    )
    remaining = ms.engagement_per_day - (today_count or 0)
    if remaining <= 0:
        return

    access_token, _ = account.get_decrypted_tokens()
    client = LinkedInClient()

    # Derive keywords from the first 3 topics (split to individual words)
    keywords: list[str] = []
    for topic in (ms.topics or [])[:3]:
        keywords.extend(topic.lower().split())
    keywords = list(dict.fromkeys(keywords))[:5]  # deduplicate, max 5

    # NOTE: LinkedIn does not provide a public feed search API for third-party apps.
    # The /v2/feed endpoint requires special Marketing Developer Platform access.
    # For now we skip feed search and log a warning. When MDP access is granted,
    # replace this section with a real feed query using the keywords above.
    logger.debug(
        "auto_engage: LinkedIn feed search not available via standard API "
        "(requires MDP access). Skipping engagement for account=%s",
        account.id,
    )
    # Placeholder: in a production MDP-approved integration, call something like:
    #   candidate_posts = await client.search_feed(access_token, keywords, limit=remaining)
    candidate_posts: list[dict] = []

    action_count = 0
    for cp in candidate_posts:
        if action_count >= remaining:
            break

        post_urn: str = cp.get("urn", "")
        author: str = cp.get("author", "")
        if not post_urn:
            continue

        # Skip if already engaged with this post + like action
        already = await db.scalar(
            select(func.count())
            .select_from(MarketingEngagement)
            .where(
                MarketingEngagement.account_id == account.id,
                MarketingEngagement.target_post_id == post_urn,
                MarketingEngagement.action_type == "like",
            )
        )
        if already:
            continue

        try:
            await client.like_post(access_token, account.author_urn, post_urn)
            db.add(
                MarketingEngagement(
                    account_id=account.id,
                    action_type="like",
                    target_post_id=post_urn,
                    target_author=author,
                )
            )
            await db.commit()
            action_count += 1

            # Every 5th action: add a short AI-generated comment
            if action_count % 5 == 0:
                from app.services.ai_provider import AIProvider
                comment_text = await AIProvider(ai_tenant).complete(
                    prompt=(
                        f"Write a single genuine 1-sentence professional comment "
                        f"for a LinkedIn post about {', '.join(keywords[:2])}. "
                        f"Do not start with 'I'. Under 25 words."
                    ),
                    max_tokens=60,
                )
                comment_text = comment_text.strip()
                if comment_text:
                    await client.comment_on_post(
                        access_token, account.author_urn, post_urn, comment_text
                    )
                    db.add(
                        MarketingEngagement(
                            account_id=account.id,
                            action_type="comment",
                            target_post_id=post_urn,
                            target_author=author,
                            content=comment_text,
                        )
                    )
                    await db.commit()
                    action_count += 1

        except Exception as exc:
            logger.warning("auto_engage: action failed post=%s: %s", post_urn, exc)

        # Mandatory 2-5 minute delay between actions (LinkedIn rate limit compliance)
        await asyncio.sleep(random.uniform(120, 300))

    logger.info(
        "auto_engage: %d action(s) performed for account=%s", action_count, account.id
    )


# ── Task 6.5 — refresh_linkedin_tokens ───────────────────────────────────────


@celery_app.task(name="app.tasks.marketing_tasks.refresh_linkedin_tokens")
def refresh_linkedin_tokens() -> None:
    """Proactively refresh LinkedIn tokens expiring within 48 hours."""
    asyncio.run(_refresh_linkedin_tokens_async())


async def _refresh_linkedin_tokens_async() -> None:
    from app.services.marketing.linkedin_client import LinkedInClient
    from app.services.sendgrid_email import send_email

    cutoff = datetime.now(timezone.utc) + timedelta(hours=48)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MarketingAccount).where(
                MarketingAccount.is_active.is_(True),
                MarketingAccount.token_expires_at <= cutoff,
                MarketingAccount.token_expires_at.isnot(None),
            )
        )
        accounts = result.scalars().all()

    logger.info("refresh_linkedin_tokens: %d account(s) expiring soon", len(accounts))

    for account in accounts:
        try:
            async with AsyncSessionLocal() as db:
                await _refresh_account_token(db, account)
                logger.info(
                    "refresh_linkedin_tokens: refreshed account=%s", account.id
                )
        except Exception as exc:
            logger.error(
                "refresh_linkedin_tokens: failed for account=%s: %s", account.id, exc
            )
            await _send_token_expiry_alert(account, exc, send_email)


async def _refresh_account_token(db, account: MarketingAccount) -> None:
    """Refresh and re-save tokens for a single account (shared helper)."""
    from app.services.marketing.linkedin_client import LinkedInClient

    _, refresh_token = account.get_decrypted_tokens()
    new_tokens = await LinkedInClient().refresh_access_token(refresh_token)
    account.set_encrypted_tokens(
        new_tokens["access_token"], new_tokens["refresh_token"]
    )
    account.token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=new_tokens.get("expires_in", 5184000)
    )
    await db.commit()


# ── Task 6.6 — post_to_linkedin_groups ───────────────────────────────────────


@celery_app.task(
    name="app.tasks.marketing_tasks.post_to_linkedin_groups",
    queue="marketing",
)
def post_to_linkedin_groups() -> None:
    """Post to LinkedIn groups — runs Tuesday 09:00 UTC."""
    asyncio.run(_post_to_linkedin_groups_async())


async def _post_to_linkedin_groups_async() -> None:
    from app.config import get_marketing_limits
    from app.services.marketing.content_generator import MarketingContentGenerator
    from app.services.marketing.linkedin_client import LinkedInClient
    import json
    import redis as redis_lib
    from app.config import settings as _settings

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MarketingSettings).where(MarketingSettings.is_active.is_(True))
        )
        all_settings = result.scalars().all()

    for ms in all_settings:
        try:
            async with AsyncSessionLocal() as db:
                await _post_groups_for_settings(db, ms)
        except Exception as exc:
            logger.error(
                "post_to_linkedin_groups: failed for settings=%s: %s", ms.id, exc
            )


async def _post_groups_for_settings(db, ms: MarketingSettings) -> None:
    from app.config import get_marketing_limits
    from app.services.marketing.content_generator import (
        ContentGenerationError,
        MarketingContentGenerator,
    )
    from app.services.marketing.linkedin_client import LinkedInClient
    import json, redis as redis_lib
    from app.config import settings as _settings

    if ms.tenant_id is not None:
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == ms.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            return
        limits = get_marketing_limits(tenant.plan)
        if not limits["group_posting"]:
            return
        ai_tenant = tenant
    else:
        ai_tenant = _platform_tenant()

    account_result = await db.execute(
        select(MarketingAccount).where(
            MarketingAccount.tenant_id == ms.tenant_id,
            MarketingAccount.platform == "linkedin",
            MarketingAccount.is_active.is_(True),
        )
    )
    account = account_result.scalars().first()
    if not account or account.is_token_expired:
        return

    # Find best post from last 7 days (highest impressions)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    best_result = await db.execute(
        select(MarketingPost)
        .where(
            MarketingPost.account_id == account.id,
            MarketingPost.status == "posted",
            MarketingPost.posted_at >= week_ago,
        )
        .order_by(MarketingPost.impressions.desc())
        .limit(1)
    )
    best_post = best_result.scalar_one_or_none()

    if best_post:
        content = best_post.content
    else:
        # Generate fresh content
        recent_result = await db.execute(
            select(MarketingPost)
            .where(MarketingPost.account_id == account.id)
            .order_by(MarketingPost.created_at.desc())
            .limit(30)
        )
        recent_posts = recent_result.scalars().all()
        generator = MarketingContentGenerator(ai_tenant)
        topic = generator.get_next_topic(ms, recent_posts)
        post_type = generator.get_next_post_type(ms, recent_posts)
        try:
            result_data = await generator.generate_post(ms, account, post_type, topic)
            content = result_data["content"]
        except ContentGenerationError as exc:
            logger.warning("post_to_linkedin_groups: content generation failed: %s", exc.detail)
            return

    access_token, _ = account.get_decrypted_tokens()
    client = LinkedInClient()

    try:
        groups = await client.get_groups(access_token)
    except Exception as exc:
        logger.warning("post_to_linkedin_groups: get_groups failed: %s", exc)
        return

    if not groups:
        return

    # Rotate through groups using Redis key to avoid repeating same groups
    redis_key = f"marketing:group_rotation:{account.id}"
    try:
        r = redis_lib.from_url(
            _settings.redis_url, socket_connect_timeout=2, decode_responses=True
        )
        last_raw = r.get(redis_key)
        last_posted_ids: list[str] = json.loads(last_raw) if last_raw else []
    except Exception:
        last_posted_ids = []

    # Filter out recently used groups; take up to 3
    available = [g for g in groups if str(g.get("id", "")) not in last_posted_ids]
    if not available:
        available = groups  # All used — restart rotation
    targets = available[:3]

    posted_ids: list[str] = []
    for group in targets:
        group_id = str(group.get("id", ""))
        if not group_id:
            continue
        try:
            post_urn = await client.post_to_group(access_token, group_id, content)
            db.add(
                MarketingPost(
                    tenant_id=ms.tenant_id,
                    account_id=account.id,
                    platform="linkedin",
                    post_type="thought_leadership",
                    content=content,
                    hashtags=[],
                    scheduled_at=datetime.now(timezone.utc),
                    posted_at=datetime.now(timezone.utc),
                    status="posted",
                    platform_post_id=post_urn,
                )
            )
            await db.commit()
            posted_ids.append(group_id)
            logger.info(
                "post_to_linkedin_groups: posted to group=%s urn=%s", group_id, post_urn
            )
        except Exception as exc:
            logger.warning("post_to_linkedin_groups: failed for group=%s: %s", group_id, exc)

    # Save rotation state
    try:
        r.setex(redis_key, 7 * 24 * 3600, json.dumps(posted_ids))
    except Exception:
        pass


# ── Private helpers ────────────────────────────────────────────────────────────


def _platform_tenant():
    """Return a minimal Tenant-like object for the platform-level account.

    Uses platform API keys directly. Only used when tenant_id IS NULL.
    """
    from app.config import settings as _s
    from app.models.tenant import Tenant as _T

    t = _T.__new__(_T)
    t.id = None
    t.ai_provider = "anthropic"
    t.ai_api_key = None
    t.plan = "enterprise"
    return t


async def _send_auth_alert(db, post: MarketingPost, account, send_email) -> None:
    """Alert tenant/super_admin when a LinkedIn auth error occurs on posting."""
    from app.config import settings as _s

    if not account:
        return
    try:
        recipient = _s.super_admin_email
        if account.tenant_id:
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == account.tenant_id)
            )
            t = tenant_result.scalar_one_or_none()
            if t and t.main_contact_email:
                recipient = t.main_contact_email
        if recipient:
            await send_email(
                to=recipient,
                subject="Action required: LinkedIn account disconnected",
                html_body=(
                    f"<p>The LinkedIn account <strong>{account.account_name}</strong> "
                    f"has been disconnected due to an authentication error. "
                    f"Please reconnect it from the Marketing settings page.</p>"
                ),
                tenant=None,
            )
    except Exception as exc:
        logger.warning("_send_auth_alert: failed to send email: %s", exc)


async def _send_token_expiry_alert(account: MarketingAccount, exc: Exception, send_email) -> None:
    """Alert tenant/super_admin when a token refresh fails."""
    from app.config import settings as _s

    try:
        recipient = _s.super_admin_email
        if account.tenant_id:
            async with AsyncSessionLocal() as db:
                tenant_result = await db.execute(
                    select(Tenant).where(Tenant.id == account.tenant_id)
                )
                t = tenant_result.scalar_one_or_none()
                if t and t.main_contact_email:
                    recipient = t.main_contact_email
        if recipient:
            reconnect_url = f"{_s.frontend_url}/en/marketing?tab=linkedin-account"
            await send_email(
                to=recipient,
                subject=f"LinkedIn token refresh failed: {account.account_name}",
                html_body=(
                    f"<p>Failed to refresh the LinkedIn token for "
                    f"<strong>{account.account_name}</strong>.</p>"
                    f"<p>Error: {exc}</p>"
                    f"<p>The token expires at {account.token_expires_at}. "
                    f"Please <a href='{reconnect_url}'>reconnect your account</a> "
                    f"before it expires to avoid publishing interruptions.</p>"
                ),
                tenant=None,
            )
    except Exception as alert_exc:
        logger.warning("_send_token_expiry_alert: failed to send email: %s", alert_exc)
