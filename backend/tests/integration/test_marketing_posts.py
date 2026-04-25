"""Integration tests for /api/v1/marketing/posts routes."""

import uuid
from datetime import datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

API = "/api/v1/marketing"


# ── Helpers ───────────────────────────────────────────────────────────────────


def fake_refresh(obj) -> None:
    """Simulate DB refresh: populate server-side / column defaults on new ORM objects.

    SQLAlchemy 2.x does not eagerly apply column defaults (default=0, default=uuid.uuid4,
    server_default=func.now()) to the Python instance before flush.  This helper mimics
    what a real flush+refresh cycle would do so pydantic validation succeeds.
    """
    if not getattr(obj, "id", None):
        obj.id = uuid.uuid4()
    if not getattr(obj, "created_at", None):
        obj.created_at = datetime.now(timezone.utc)
    # Integer stats default to 0
    for _int_field in ("likes", "comments", "impressions", "clicks", "retry_count"):
        if hasattr(obj, _int_field) and getattr(obj, _int_field, None) is None:
            setattr(obj, _int_field, 0)


# ── Factories ──────────────────────────────────────────────────────────────────


def make_account(tenant_id: uuid.UUID, **kwargs) -> MagicMock:
    a = MagicMock()
    a.id = kwargs.get("id", uuid.uuid4())
    a.tenant_id = tenant_id
    a.platform = kwargs.get("platform", "linkedin")
    a.account_type = kwargs.get("account_type", "company")
    a.account_name = kwargs.get("account_name", "Test Agency")
    a.linkedin_urn = "urn:li:organization:12345"
    a.is_active = kwargs.get("is_active", True)
    a.token_expires_at = None
    a.created_at = datetime.now(timezone.utc)
    a.is_token_expiring_soon = MagicMock(return_value=False)
    a.author_urn = "urn:li:organization:12345"
    return a


def make_settings(tenant_id: uuid.UUID, **kwargs) -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.tenant_id = tenant_id
    s.post_frequency = "twice_weekly"
    s.post_time_utc = time(9, 0)
    s.post_types_enabled = ["thought_leadership", "tip"]
    s.platforms_enabled = ["linkedin"]
    s.target_audience = "recruiters"
    s.tone = "professional"
    s.topics = ["AI recruiting"]
    s.auto_engage = False
    s.engagement_per_day = 5
    s.requires_approval = kwargs.get("requires_approval", True)
    s.include_images = False
    s.is_active = kwargs.get("is_active", True)
    s.created_at = datetime.now(timezone.utc)
    return s


def make_post(tenant_id: uuid.UUID, account_id: uuid.UUID, **kwargs) -> MagicMock:
    p = MagicMock()
    p.id = kwargs.get("id", uuid.uuid4())
    p.tenant_id = tenant_id
    p.account_id = account_id
    p.platform = "linkedin"
    p.post_type = kwargs.get("post_type", "thought_leadership")
    p.content = kwargs.get("content", "Recruiting is changing fast. Here are 3 trends.")
    p.hashtags = ["#Recruiting", "#HR"]
    p.topic = kwargs.get("topic", "AI recruiting")
    p.include_image = False
    p.image_search_query = None
    p.image_url = None
    p.image_attribution = None
    p.scheduled_at = datetime.now(timezone.utc)
    p.posted_at = kwargs.get("posted_at", None)
    p.status = kwargs.get("status", "draft")
    p.retry_count = 0
    p.platform_post_id = None
    p.likes = 0
    p.comments = 0
    p.impressions = 0
    p.clicks = 0
    p.created_at = datetime.now(timezone.utc)
    return p


# ── Plan gate ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_posts_returns_403_for_trial_plan(client, mock_db, mock_tenant):
    resp = await client.get(f"{API}/posts", headers={"Authorization": "Bearer test"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_generate_post_returns_403_for_trial_plan(client, mock_db, mock_tenant):
    resp = await client.post(f"{API}/posts/generate", json={}, headers={"Authorization": "Bearer test"})
    assert resp.status_code == 403


# ── GET /posts ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_posts_returns_empty(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 0
    list_mock = MagicMock()
    list_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[count_mock, list_mock])

    resp = await client.get(f"{API}/posts", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_posts_returns_posts(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post = make_post(tenant_id, account_id)

    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 1
    list_mock = MagicMock()
    list_mock.scalars.return_value.all.return_value = [post]
    mock_db.execute = AsyncMock(side_effect=[count_mock, list_mock])

    resp = await client.get(f"{API}/posts", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "draft"


@pytest.mark.asyncio
async def test_list_posts_filters_by_status(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 0
    list_mock = MagicMock()
    list_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[count_mock, list_mock])

    resp = await client.get(f"{API}/posts?status=scheduled", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200


# ── POST /posts/generate ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_post_creates_draft(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    account = make_account(tenant_id, id=account_id)
    settings = make_settings(tenant_id)
    post = make_post(tenant_id, account_id, status="draft")

    account_result = MagicMock()
    account_result.scalars.return_value.first.return_value = account

    recent_result = MagicMock()
    recent_result.scalars.return_value.all.return_value = []

    settings_result = MagicMock()
    settings_result.scalar_one_or_none.return_value = settings

    mock_db.execute = AsyncMock(side_effect=[settings_result, account_result, recent_result])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    mock_ai_output = {
        "content": "Recruitment technology is reshaping talent acquisition in 2026.",
        "hashtags": ["#Recruiting", "#AI", "#HR"],
    }

    with patch("app.services.marketing.content_generator.MarketingContentGenerator") as mock_gen_cls:
        mock_gen = MagicMock()
        mock_gen.get_next_post_type.return_value = "thought_leadership"
        mock_gen.get_next_topic.return_value = "AI recruiting"
        mock_gen.generate_post = AsyncMock(return_value={
            "content": mock_ai_output["content"],
            "hashtags": mock_ai_output["hashtags"],
            "topic": "AI recruiting",
            "image_search_query": None,
            "image_url": None,
            "image_attribution": None,
        })
        mock_gen_cls.return_value = mock_gen

        resp = await client.post(
            f"{API}/posts/generate",
            json={},
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["content"] == mock_ai_output["content"]


@pytest.mark.asyncio
async def test_generate_post_returns_422_when_no_account(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    settings = make_settings(tenant_id)

    settings_result = MagicMock()
    settings_result.scalar_one_or_none.return_value = settings

    no_account_result = MagicMock()
    no_account_result.scalars.return_value.first.return_value = None

    mock_db.execute = AsyncMock(side_effect=[settings_result, no_account_result])

    resp = await client.post(
        f"{API}/posts/generate",
        json={},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 422


# ── POST /posts/{id}/approve ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_post_changes_status_to_scheduled(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = make_post(tenant_id, account_id, id=post_id, status="draft")

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    resp = await client.post(
        f"{API}/posts/{post_id}/approve",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert post.status == "scheduled"


@pytest.mark.asyncio
async def test_approve_post_returns_422_when_already_scheduled(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = make_post(tenant_id, account_id, id=post_id, status="scheduled")

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.post(
        f"{API}/posts/{post_id}/approve",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_approve_post_returns_404_when_not_found(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    post_id = uuid.uuid4()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.post(
        f"{API}/posts/{post_id}/approve",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 404


# ── POST /posts/{id}/reject ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_post_reverts_to_draft(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = make_post(tenant_id, account_id, id=post_id, status="scheduled")

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    resp = await client.post(
        f"{API}/posts/{post_id}/reject",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert post.status == "draft"


@pytest.mark.asyncio
async def test_reject_posted_post_returns_422(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = make_post(
        tenant_id, account_id, id=post_id, status="posted",
        posted_at=datetime.now(timezone.utc),
    )

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.post(
        f"{API}/posts/{post_id}/reject",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 422


# ── DELETE /posts/{id} ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_draft_post_returns_204(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = make_post(tenant_id, account_id, id=post_id, status="draft")

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    resp = await client.delete(
        f"{API}/posts/{post_id}",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 204
    mock_db.delete.assert_called_once_with(post)


@pytest.mark.asyncio
async def test_delete_posted_post_returns_422(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = make_post(
        tenant_id, account_id, id=post_id, status="posted",
        posted_at=datetime.now(timezone.utc),
    )

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.delete(
        f"{API}/posts/{post_id}",
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 422


# ── PATCH /posts/{id} ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_draft_post_returns_200(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = make_post(tenant_id, account_id, id=post_id, status="draft")

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    resp = await client.patch(
        f"{API}/posts/{post_id}",
        json={"content": "Updated content about talent acquisition."},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert post.content == "Updated content about talent acquisition."


@pytest.mark.asyncio
async def test_update_posted_post_returns_422(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    account_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = make_post(
        tenant_id, account_id, id=post_id, status="posted",
        posted_at=datetime.now(timezone.utc),
    )

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.patch(
        f"{API}/posts/{post_id}",
        json={"content": "Try to update a posted post."},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 422
