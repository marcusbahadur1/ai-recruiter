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
    MarketingEnrollment,
    MarketingEngagement,
    MarketingOutreachLog,
    MarketingPost,
    MarketingProspect,
    MarketingSequence,
    MarketingSequenceStep,
    MarketingSettings,
    MarketingSignal,
    MarketingSignalRun,
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
    """Publish all scheduled content posts using the multi-page publish service.

    Uses SELECT FOR UPDATE SKIP LOCKED to prevent concurrent workers from
    double-publishing the same post.
    """
    from app.services.marketing.publish_service import publish_post_to_all_pages

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
                await publish_post_to_all_pages(post, db)
                logger.info(
                    "publish_scheduled_posts: post=%s status=%s", post.id, post.status
                )
            except Exception as exc:
                post.retry_count += 1
                if post.retry_count >= 3:
                    post.status = "failed"
                    logger.error(
                        "publish_scheduled_posts: post=%s permanently failed: %s",
                        post.id, exc,
                    )
                else:
                    logger.warning(
                        "publish_scheduled_posts: post=%s retry %d/3: %s",
                        post.id, post.retry_count, exc,
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


# ── Task: scrape_signals_for_tenant ──────────────────────────────────────────


@celery_app.task(
    name="app.tasks.marketing_tasks.scrape_signals_for_tenant",
    bind=True,
    max_retries=3,
    queue="marketing",
)
def scrape_signals_for_tenant(self, tenant_id: str, run_id: str) -> None:
    """BrightData signal scrape for a single tenant.

    Triggered by POST /api/marketing/signals/run or by the Beat schedule.
    Idempotent: signals are deduplicated by (tenant_id, type, company, week).
    """
    try:
        asyncio.run(_scrape_signals_async(tenant_id, run_id))
    except Exception as exc:
        logger.error("scrape_signals_for_tenant: tenant=%s run=%s error=%s", tenant_id, run_id, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


async def _scrape_signals_async(tenant_id: str, run_id: str) -> None:
    import uuid as _uuid
    import httpx

    from sqlalchemy import text as _text

    tid = _uuid.UUID(tenant_id)
    rid = _uuid.UUID(run_id)

    async with AsyncSessionLocal() as db:
        # Load tenant + settings
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            logger.warning("scrape_signals: tenant %s not found", tenant_id)
            return

        settings_result = await db.execute(
            select(MarketingSettings).where(MarketingSettings.tenant_id == tid)
        )
        ms = settings_result.scalar_one_or_none()

        # Fall back to platform settings
        if not ms:
            settings_result = await db.execute(
                select(MarketingSettings).where(MarketingSettings.tenant_id.is_(None))
            )
            ms = settings_result.scalar_one_or_none()

        bd_key: str | None = None
        spike_threshold: int = 3
        monitor_pain: bool = True
        monitor_growth: bool = True

        if ms and ms.channel_config:
            raw_key = ms.channel_config.get("brightdata_api_key")
            if raw_key and not raw_key.startswith("*"):
                bd_key = raw_key
        if ms and ms.signal_config:
            spike_threshold = ms.signal_config.get("hiring_spike_threshold", 3)
            monitor_pain = ms.signal_config.get("monitor_pain_posts", True)
            monitor_growth = ms.signal_config.get("monitor_growth_signals", True)

        # ICP location hints for scoping searches
        icp_locations: list[str] = []
        if ms and ms.icp_config:
            icp_locations = ms.icp_config.get("locations", [])

    # ── Run scrapes ───────────────────────────────────────────────────────────
    signals_created = 0

    if bd_key:
        try:
            hiring_signals = await _scrape_hiring_spikes(bd_key, icp_locations, spike_threshold)
            signals_created += await _insert_signals(tid, hiring_signals)
        except Exception as exc:
            logger.warning("scrape_signals: hiring_spike scrape failed: %s", exc)

        if monitor_pain:
            try:
                pain_signals = await _scrape_pain_posts(bd_key, icp_locations)
                signals_created += await _insert_signals(tid, pain_signals)
            except Exception as exc:
                logger.warning("scrape_signals: pain_post scrape failed: %s", exc)

        if monitor_growth:
            try:
                growth_signals = await _scrape_growth_signals(bd_key, icp_locations)
                signals_created += await _insert_signals(tid, growth_signals)
            except Exception as exc:
                logger.warning("scrape_signals: growth_signal scrape failed: %s", exc)
    else:
        logger.info(
            "scrape_signals: no BrightData key for tenant %s — inserting demo signals", tenant_id
        )
        demo = _demo_signals()
        signals_created += await _insert_signals(tid, demo)

    # ── Mark run complete ─────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        await db.execute(
            _text(
                "UPDATE marketing_signal_runs SET completed_at = now(), signals_found = :sf WHERE id = :rid"
            ),
            {"sf": signals_created, "rid": str(rid)},
        )
        await db.commit()

    logger.info(
        "scrape_signals: tenant=%s run=%s created=%d signals", tenant_id, run_id, signals_created
    )


async def _brightdata_trigger_and_poll(api_key: str, dataset_id: str, inputs: list[dict]) -> list[dict]:
    """Shared helper: trigger a BrightData dataset job and poll for results."""
    import httpx

    trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&include_errors=true"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            r = await client.post(trigger_url, json=inputs, headers=headers)
            r.raise_for_status()
        except Exception as exc:
            logger.warning("BrightData trigger failed dataset=%s: %s", dataset_id, exc)
            return []

        snapshot_id = r.json().get("snapshot_id")
        if not snapshot_id:
            return []

        snap_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"
        for _ in range(24):
            await asyncio.sleep(5)
            try:
                snap = await client.get(snap_url, headers=headers)
                if snap.status_code == 200:
                    rows = snap.json()
                    return [r for r in rows if isinstance(r, dict) and not r.get("error")]
                elif snap.status_code == 202:
                    continue
            except Exception:
                continue

    return []


async def _scrape_hiring_spikes(api_key: str, locations: list[str], threshold: int) -> list[dict]:
    """Query BrightData LinkedIn Jobs dataset for companies with hiring spikes."""
    # BrightData LinkedIn Job Listings dataset
    # Dataset ID: gd_lpfll7823cnl2x7jg — verify in BrightData dashboard
    DATASET_ID = "gd_lpfll7823cnl2x7jg"

    inputs = []
    queries = ["recruiter", "HR Director", "talent acquisition", "hiring manager"]
    for q in queries:
        if locations:
            for loc in locations[:3]:
                inputs.append({"keyword": q, "location": loc, "time_range": "past week"})
        else:
            inputs.append({"keyword": q, "time_range": "past week"})

    rows = await _brightdata_trigger_and_poll(api_key, DATASET_ID, inputs)

    # Group by company, count job postings
    company_jobs: dict[str, list[dict]] = {}
    for row in rows:
        company = row.get("company_name") or row.get("company")
        if company:
            company_jobs.setdefault(company, []).append(row)

    signals: list[dict] = []
    for company, jobs in company_jobs.items():
        if len(jobs) < threshold:
            continue
        sample = jobs[0]
        job_count = len(jobs)
        company_size = sample.get("company_employees_count") or sample.get("company_size")
        location = sample.get("location") or sample.get("city") or ""

        # Compute urgency: high if 5+ new jobs
        urgency = "high" if job_count >= 5 else "medium"

        size_str = f"{company_size:,}" if isinstance(company_size, int) else "unknown"
        summary = (
            f"{company} posted {job_count} new role{'s' if job_count > 1 else ''} in the past 7 days. "
            f"{size_str} employee company — likely stretched on sourcing."
        )

        signals.append({
            "type": "hiring_spike",
            "company": company,
            "person_name": None,
            "linkedin_url": sample.get("company_url") or sample.get("url"),
            "summary": summary,
            "urgency": urgency,
            "location": location,
            "company_type": sample.get("company_industry") or sample.get("industry"),
            "job_count": job_count,
            "dedup_key": company,
        })

    return signals


async def _scrape_pain_posts(api_key: str, locations: list[str]) -> list[dict]:
    """Query BrightData LinkedIn Posts dataset for pain-point keywords."""
    # BrightData LinkedIn Posts Search dataset
    # Dataset ID: gd_lyy3tpxn4dn948o8t — verify in BrightData dashboard
    DATASET_ID = "gd_lyy3tpxn4dn948o8t"

    PAIN_KEYWORDS = [
        "time-to-hire", "candidate pipeline", "CV screening", "agency fee",
        "recruitment automation", "finding candidates", "sourcing candidates",
        "slow hiring", "can't find candidates",
    ]

    ICP_TITLES = [
        "Managing Director", "Director", "Owner", "Founder", "CEO",
        "Head of HR", "HR Director", "Hiring Manager",
    ]

    inputs = [{"keyword": kw} for kw in PAIN_KEYWORDS[:5]]  # cap API calls

    rows = await _brightdata_trigger_and_poll(api_key, DATASET_ID, inputs)

    signals: list[dict] = []
    for row in rows:
        author_title = row.get("author_title") or row.get("title") or ""
        # Filter to ICP target titles
        if not any(t.lower() in author_title.lower() for t in ICP_TITLES):
            continue

        author_name = row.get("author_name") or row.get("name") or "Someone"
        author_company = row.get("author_company") or row.get("company") or ""
        keyword = row.get("keyword") or row.get("matched_keyword") or "hiring"
        followers = row.get("author_followers") or row.get("followers") or 0
        location = row.get("author_location") or ""
        linkedin_url = row.get("author_url") or row.get("url")

        summary = (
            f"{author_name} posted about {keyword}. "
            f"{author_title} at {author_company}, {followers:,} followers."
        )

        signals.append({
            "type": "pain_post",
            "company": author_company,
            "person_name": author_name,
            "linkedin_url": linkedin_url,
            "summary": summary,
            "urgency": "medium",
            "location": location,
            "company_type": None,
            "job_count": None,
            "dedup_key": linkedin_url or f"{author_name}:{author_company}",
        })

    return signals


async def _scrape_growth_signals(api_key: str, locations: list[str]) -> list[dict]:
    """Query BrightData for companies actively hiring recruitment consultants."""
    DATASET_ID = "gd_lpfll7823cnl2x7jg"

    GROWTH_QUERIES = ["recruitment consultant", "talent acquisition specialist", "recruiter"]
    inputs = []
    for q in GROWTH_QUERIES:
        if locations:
            for loc in locations[:2]:
                inputs.append({"keyword": q, "location": loc, "time_range": "past month"})
        else:
            inputs.append({"keyword": q, "time_range": "past month"})

    rows = await _brightdata_trigger_and_poll(api_key, DATASET_ID, inputs)

    # Group by company
    company_jobs: dict[str, list[dict]] = {}
    for row in rows:
        company = row.get("company_name") or row.get("company")
        if company:
            company_jobs.setdefault(company, []).append(row)

    signals: list[dict] = []
    for company, jobs in company_jobs.items():
        count = len(jobs)
        sample = jobs[0]
        location = sample.get("location") or ""

        summary = (
            f"{company} is hiring {count} recruitment consultant"
            f"{'s' if count > 1 else ''} — scaling team, likely has more client mandates than capacity."
        )

        signals.append({
            "type": "growth_signal",
            "company": company,
            "person_name": None,
            "linkedin_url": sample.get("company_url") or sample.get("url"),
            "summary": summary,
            "urgency": "medium",
            "location": location,
            "company_type": sample.get("company_industry") or sample.get("industry"),
            "job_count": count,
            "dedup_key": company,
        })

    return signals


async def _insert_signals(tenant_id, signals: list[dict]) -> int:
    """Deduplicate and insert signals. Returns number inserted."""
    from datetime import timedelta

    created = 0
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    async with AsyncSessionLocal() as db:
        for sig in signals:
            dedup_key = sig.pop("dedup_key", None) or sig.get("company") or sig.get("person_name")

            # Dedup: skip if same tenant + type + dedup_key already exists within 7 days
            if dedup_key:
                existing = await db.execute(
                    select(MarketingSignal.id).where(
                        MarketingSignal.tenant_id == tenant_id,
                        MarketingSignal.type == sig["type"],
                        MarketingSignal.company == sig.get("company"),
                        MarketingSignal.detected_at >= week_ago,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

            db.add(MarketingSignal(
                tenant_id=tenant_id,
                type=sig["type"],
                company=sig.get("company"),
                person_name=sig.get("person_name"),
                linkedin_url=sig.get("linkedin_url"),
                summary=sig.get("summary"),
                urgency=sig.get("urgency", "medium"),
                location=sig.get("location"),
                company_type=sig.get("company_type"),
                job_count=sig.get("job_count"),
            ))
            created += 1

        await db.commit()

    return created


def _demo_signals() -> list[dict]:
    """Return seeded demo signals when no BrightData key is configured."""
    return [
        {
            "type": "hiring_spike",
            "company": "Acme Corp",
            "person_name": None,
            "linkedin_url": None,
            "summary": "Acme Corp posted 6 new roles in the past 7 days. 85 employee company — likely stretched on sourcing.",
            "urgency": "high",
            "location": "Sydney, AU",
            "company_type": "Technology",
            "job_count": 6,
            "dedup_key": "Acme Corp",
        },
        {
            "type": "pain_post",
            "company": "BuildCo",
            "person_name": "Sarah Chen",
            "linkedin_url": None,
            "summary": "Sarah Chen posted about slow hiring. Managing Director at BuildCo, 2,400 followers.",
            "urgency": "medium",
            "location": "Melbourne, AU",
            "company_type": None,
            "job_count": None,
            "dedup_key": "Sarah Chen:BuildCo",
        },
        {
            "type": "growth_signal",
            "company": "Nexus Partners",
            "person_name": None,
            "linkedin_url": None,
            "summary": "Nexus Partners is hiring 3 recruitment consultants — scaling team, likely has more client mandates than capacity.",
            "urgency": "medium",
            "location": "Brisbane, AU",
            "company_type": "Professional Services",
            "job_count": 3,
            "dedup_key": "Nexus Partners",
        },
    ]


# ── Task: process_enrollments ─────────────────────────────────────────────────


@celery_app.task(name="app.tasks.marketing_tasks.process_enrollments")
def process_enrollments() -> None:
    """Advance active enrollment sequences every 15 minutes.

    For each active enrollment:
      1. Find current step (by sort_order index = enrollment.current_step).
      2. Check if day_offset has been reached (enrolled_at + day_offset days <= now).
      3. Check step condition (previous step acceptance/reply from outreach_log).
      4. If all conditions met and within outreach_limits window:
         - linkedin_connect: send via LinkedIn API (requires MDP — logs if unavailable).
         - linkedin_dm: send via LinkedIn API (requires MDP — logs if unavailable).
         - email: personalise and send via SendGrid (uses Hunter.io to find email if missing).
         - wait: advance immediately if condition is met or no condition set.
      5. Log to marketing_outreach_log and increment enrollment.current_step.
      6. If no more steps: mark enrollment status = 'completed'.
    """
    asyncio.run(_process_enrollments_async())


async def _process_enrollments_async() -> None:
    from app.models.marketing import (
        MarketingEnrollment,
        MarketingOutreachLog,
        MarketingSequence,
        MarketingSequenceStep,
        MarketingSettings,
    )
    from sqlalchemy import text as _text

    now = datetime.now(timezone.utc)
    processed = advanced = skipped = 0

    async with AsyncSessionLocal() as db:
        # Load all active enrollments
        result = await db.execute(
            select(MarketingEnrollment).where(
                MarketingEnrollment.status == "active"
            ).limit(500)
        )
        enrollments = result.scalars().all()

    for enrollment in enrollments:
        try:
            async with AsyncSessionLocal() as db:
                outcome = await _process_single_enrollment(db, enrollment, now)
            if outcome == "advanced":
                advanced += 1
            else:
                skipped += 1
            processed += 1
        except Exception as exc:
            logger.error(
                "process_enrollments: enrollment=%s error=%s", enrollment.id, exc
            )

    logger.info(
        "process_enrollments: processed=%d advanced=%d skipped=%d",
        processed,
        advanced,
        skipped,
    )


async def _process_single_enrollment(db, enrollment: "MarketingEnrollment", now: datetime) -> str:
    from app.models.marketing import (
        MarketingEnrollment,
        MarketingOutreachLog,
        MarketingProspect,
        MarketingSequence,
        MarketingSequenceStep,
        MarketingSettings,
    )

    # Load enrollment with FK objects
    result = await db.execute(
        select(MarketingEnrollment)
        .where(MarketingEnrollment.id == enrollment.id)
    )
    enr = result.scalar_one_or_none()
    if not enr or enr.status != "active":
        return "skipped"

    # Load sequence steps ordered by sort_order
    steps_result = await db.execute(
        select(MarketingSequenceStep)
        .where(MarketingSequenceStep.sequence_id == enr.sequence_id)
        .order_by(MarketingSequenceStep.sort_order)
    )
    steps = steps_result.scalars().all()

    if not steps or enr.current_step >= len(steps):
        enr.status = "completed"
        await db.commit()
        return "advanced"

    step = steps[enr.current_step]

    # Check day_offset: enrolled_at + day_offset <= now
    from datetime import timedelta
    eligible_at = enr.enrolled_at + timedelta(days=step.day_offset)
    if now < eligible_at:
        return "skipped"

    # Load prospect
    prospect_result = await db.execute(
        select(MarketingProspect).where(MarketingProspect.id == enr.prospect_id)
    )
    prospect = prospect_result.scalar_one_or_none()
    if not prospect:
        enr.status = "skipped"
        await db.commit()
        return "skipped"

    # Load tenant settings for outreach limits
    tenant_id = prospect.tenant_id
    settings_result = await db.execute(
        select(MarketingSettings).where(MarketingSettings.tenant_id == tenant_id)
    )
    ms = settings_result.scalar_one_or_none()
    outreach_limits = (ms.outreach_limits or {}) if ms else {}
    window_start = outreach_limits.get("window_start_utc", "08:00")
    window_end = outreach_limits.get("window_end_utc", "17:00")
    skip_weekends = outreach_limits.get("skip_weekends", True)

    # Check outreach window
    now_hour = now.hour
    now_minute = now.minute
    start_h, start_m = (int(x) for x in window_start.split(":"))
    end_h, end_m = (int(x) for x in window_end.split(":"))
    start_mins = start_h * 60 + start_m
    end_mins = end_h * 60 + end_m
    now_mins = now_hour * 60 + now_minute
    if now_mins < start_mins or now_mins > end_mins:
        return "skipped"
    if skip_weekends and now.weekday() >= 5:
        return "skipped"

    # Check condition: look at previous step's outreach_log
    if step.condition and enr.current_step > 0:
        prev_step = steps[enr.current_step - 1]
        prev_log_result = await db.execute(
            select(MarketingOutreachLog).where(
                MarketingOutreachLog.step_id == prev_step.id,
                MarketingOutreachLog.prospect_id == enr.prospect_id,
            )
        )
        prev_log = prev_log_result.scalar_one_or_none()

        cond_lower = step.condition.lower()
        if "accept" in cond_lower and (not prev_log or not prev_log.opened_at):
            return "skipped"
        if "no reply" in cond_lower and prev_log and prev_log.replied_at:
            return "skipped"

    # ── Execute step ──────────────────────────────────────────────────────────
    if step.step_type == "wait":
        # Wait steps just advance
        enr.current_step += 1
        if enr.current_step >= len(steps):
            enr.status = "completed"
        await db.commit()
        return "advanced"

    # Personalise message
    first_name = (prospect.name or "").split()[0] if prospect.name else "there"
    message = (step.message_template or "").replace("{first_name}", first_name)
    message = message.replace("{company}", prospect.company or "your company")
    message = message.replace("{company_niche}", prospect.company_type or "your industry")

    sent_at = now
    channel = "email" if step.step_type == "email" else "linkedin"

    if step.step_type in ("linkedin_connect", "linkedin_dm"):
        # LinkedIn outreach requires MDP access — log intent, mark sent
        # When MDP access is approved, replace this section with real API calls
        logger.info(
            "process_enrollments: LinkedIn step seq=%s step=%s prospect=%s (MDP pending — logged only)",
            enr.sequence_id,
            step.id,
            enr.prospect_id,
        )

    elif step.step_type == "email":
        # Email outreach via SendGrid
        try:
            email = prospect.email
            if not email and prospect.linkedin_url:
                # Try Hunter.io enrichment
                from app.services.hunter import HunterClient
                hunter = HunterClient()
                parts = (prospect.name or "").split()
                first = parts[0] if parts else ""
                last = parts[-1] if len(parts) > 1 else ""
                found = await hunter.find_email(
                    first_name=first,
                    last_name=last,
                    company=prospect.company or "",
                )
                if found:
                    email = found
                    prospect.email = email
                    await db.flush()

            if email:
                from app.services.sendgrid_email import send_email as sg_send
                from app.models.tenant import Tenant as _Tenant
                tenant_result = await db.execute(
                    select(_Tenant).where(_Tenant.id == tenant_id)
                )
                tenant = tenant_result.scalar_one_or_none()
                if tenant:
                    subject = f"Quick question, {first_name}"
                    await sg_send(
                        to=email,
                        subject=subject,
                        html_body=message.replace("\n", "<br>"),
                        tenant=tenant,
                    )
        except Exception as exc:
            logger.warning(
                "process_enrollments: email send failed prospect=%s: %s",
                enr.prospect_id,
                exc,
            )

    # Log to outreach_log
    log_entry = MarketingOutreachLog(
        prospect_id=enr.prospect_id,
        step_id=step.id,
        channel=channel,
        sent_at=sent_at,
    )
    db.add(log_entry)

    # Advance enrollment
    enr.current_step += 1
    if enr.current_step >= len(steps):
        enr.status = "completed"

    # Update prospect stage
    if step.step_type == "linkedin_connect" and prospect.stage == "identified":
        prospect.stage = "connected"
    elif step.step_type in ("linkedin_dm", "email") and prospect.stage in ("identified", "connected"):
        prospect.stage = "messaged"
    prospect.last_activity_at = now

    await db.commit()
    return "advanced"


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
