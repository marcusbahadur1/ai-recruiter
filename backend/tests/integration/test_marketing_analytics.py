"""Integration tests for /api/v1/marketing/analytics and /engagement routes."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

API = "/api/v1/marketing"


# ── Factories ──────────────────────────────────────────────────────────────────


def make_post(tenant_id: uuid.UUID, account_id: uuid.UUID, **kwargs) -> MagicMock:
    p = MagicMock()
    p.id = kwargs.get("id", uuid.uuid4())
    p.tenant_id = tenant_id
    p.account_id = account_id
    p.platform = "linkedin"
    p.post_type = kwargs.get("post_type", "thought_leadership")
    p.content = kwargs.get("content", "Recruiting is changing. Here are 3 trends to watch.")
    p.hashtags = ["#Recruiting", "#HR"]
    p.topic = kwargs.get("topic", "AI recruiting")
    p.include_image = False
    p.image_search_query = None
    p.image_url = None
    p.image_attribution = None
    p.scheduled_at = datetime.now(timezone.utc)
    p.posted_at = kwargs.get("posted_at", datetime.now(timezone.utc))
    p.status = kwargs.get("status", "posted")
    p.retry_count = 0
    p.platform_post_id = kwargs.get("platform_post_id", "urn:li:share:123")
    p.likes = kwargs.get("likes", 10)
    p.comments = kwargs.get("comments", 3)
    p.impressions = kwargs.get("impressions", 500)
    p.clicks = kwargs.get("clicks", 15)
    p.created_at = datetime.now(timezone.utc)
    return p


def make_engagement(account_id: uuid.UUID, **kwargs) -> MagicMock:
    e = MagicMock()
    e.id = uuid.uuid4()
    e.account_id = account_id
    e.action_type = kwargs.get("action_type", "like")
    e.target_post_id = kwargs.get("target_post_id", "urn:li:share:456")
    e.target_author = kwargs.get("target_author", "urn:li:person:abc123")
    e.content = kwargs.get("content", None)
    e.performed_at = datetime.now(timezone.utc)
    e.created_at = datetime.now(timezone.utc)
    return e


# ── Plan gate ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_analytics_returns_403_for_trial_plan(client, mock_db, mock_tenant):
    resp = await client.get(f"{API}/analytics", headers={"Authorization": "Bearer test"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analytics_summary_returns_403_for_trial_plan(client, mock_db, mock_tenant):
    resp = await client.get(f"{API}/analytics/summary", headers={"Authorization": "Bearer test"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_engagement_returns_403_for_trial_plan(client, mock_db, mock_tenant):
    resp = await client.get(f"{API}/engagement", headers={"Authorization": "Bearer test"})
    assert resp.status_code == 403


# ── GET /analytics ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_analytics_returns_empty_list(client, mock_db, mock_tenant):
    mock_tenant.plan = "agency_small"

    rows_result = MagicMock()
    rows_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=rows_result)

    resp = await client.get(f"{API}/analytics", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_daily_analytics_returns_aggregated_rows(client, mock_db, mock_tenant):
    mock_tenant.plan = "agency_small"

    row = MagicMock()
    row.day = "2026-04-20"
    row.impressions = 500
    row.likes = 10
    row.comments = 3
    row.posts_count = 2

    rows_result = MagicMock()
    rows_result.all.return_value = [row]
    mock_db.execute = AsyncMock(return_value=rows_result)

    resp = await client.get(f"{API}/analytics", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["impressions"] == 500
    assert data[0]["posts_count"] == 2
    assert data[0]["date"] == "2026-04-20"


@pytest.mark.asyncio
async def test_daily_analytics_accepts_date_range_params(client, mock_db, mock_tenant):
    mock_tenant.plan = "agency_small"

    rows_result = MagicMock()
    rows_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=rows_result)

    resp = await client.get(
        f"{API}/analytics?date_from=2026-04-01T00:00:00Z&date_to=2026-04-24T23:59:59Z",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200


# ── GET /analytics/summary ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analytics_summary_returns_zeros_with_no_posts(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"

    agg_row = MagicMock()
    agg_row.total_posts = 0
    agg_row.total_impressions = 0
    agg_row.total_likes = 0
    agg_row.total_comments = 0

    agg_result = MagicMock()
    agg_result.one.return_value = agg_row

    top_post_result = MagicMock()
    top_post_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[agg_result, top_post_result])

    resp = await client.get(f"{API}/analytics/summary", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_posts"] == 0
    assert data["total_impressions"] == 0
    assert data["avg_engagement_rate"] == 0.0
    assert data["top_post"] is None


@pytest.mark.asyncio
async def test_analytics_summary_returns_stats_with_posts(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    top_post = make_post(tenant_id, account_id, impressions=800, likes=40, comments=10)

    agg_row = MagicMock()
    agg_row.total_posts = 5
    agg_row.total_impressions = 1000
    agg_row.total_likes = 40
    agg_row.total_comments = 10

    agg_result = MagicMock()
    agg_result.one.return_value = agg_row

    top_post_result = MagicMock()
    top_post_result.scalar_one_or_none.return_value = top_post

    mock_db.execute = AsyncMock(side_effect=[agg_result, top_post_result])

    resp = await client.get(f"{API}/analytics/summary", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_posts"] == 5
    assert data["total_impressions"] == 1000
    # (40 + 10) / 1000 * 100 = 5.0
    assert data["avg_engagement_rate"] == 5.0
    assert data["top_post"] is not None
    assert data["top_post"]["impressions"] == 800


# ── GET /engagement ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_engagement_returns_empty(client, mock_db, mock_tenant):
    mock_tenant.plan = "agency_small"

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[count_result, list_result])

    resp = await client.get(f"{API}/engagement", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_engagement_returns_actions(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    engagement = make_engagement(account_id, action="like")

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [engagement]

    mock_db.execute = AsyncMock(side_effect=[count_result, list_result])

    resp = await client.get(f"{API}/engagement", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["action_type"] == "like"


@pytest.mark.asyncio
async def test_list_engagement_respects_pagination(client, mock_db, mock_tenant):
    mock_tenant.plan = "agency_small"

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[count_result, list_result])

    resp = await client.get(
        f"{API}/engagement?page=2&page_size=10",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["offset"] == 10
    assert data["limit"] == 10
