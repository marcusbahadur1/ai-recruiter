"""Integration tests for /api/v1/marketing/settings and /api/v1/marketing/toggle routes."""

import uuid
from datetime import datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

API = "/api/v1/marketing"


# ── Helpers ───────────────────────────────────────────────────────────────────


def fake_refresh(obj) -> None:
    """Simulate DB refresh: populate server-side defaults on newly created ORM objects."""
    if not getattr(obj, "id", None):
        obj.id = uuid.uuid4()
    if not getattr(obj, "created_at", None):
        obj.created_at = datetime.now(timezone.utc)
    # post_time_utc is a required schema field; default to 09:00 when not supplied
    if hasattr(obj, "post_time_utc") and getattr(obj, "post_time_utc", None) is None:
        obj.post_time_utc = time(9, 0)


# ── Factories ──────────────────────────────────────────────────────────────────


def make_settings(tenant_id: uuid.UUID | None, **kwargs) -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.tenant_id = tenant_id
    s.post_frequency = kwargs.get("post_frequency", "twice_weekly")
    s.post_time_utc = time(9, 0)
    s.post_types_enabled = kwargs.get("post_types_enabled", ["thought_leadership", "tip"])
    s.platforms_enabled = kwargs.get("platforms_enabled", ["linkedin"])
    s.target_audience = kwargs.get("target_audience", "recruiters")
    s.tone = kwargs.get("tone", "professional")
    s.topics = kwargs.get("topics", ["AI recruiting", "talent acquisition"])
    s.auto_engage = kwargs.get("auto_engage", False)
    s.engagement_per_day = kwargs.get("engagement_per_day", 10)
    s.requires_approval = kwargs.get("requires_approval", True)
    s.include_images = kwargs.get("include_images", False)
    s.is_active = kwargs.get("is_active", False)
    s.created_at = datetime.now(timezone.utc)
    return s


# ── Plan gate ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_settings_returns_403_for_trial_plan(client, mock_db, mock_tenant):
    resp = await client.get(f"{API}/settings", headers={"Authorization": "Bearer test"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_settings_returns_403_for_trial_plan(client, mock_db, mock_tenant):
    resp = await client.patch(
        f"{API}/settings",
        json={"tone": "bold"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_toggle_returns_403_for_trial_plan(client, mock_db, mock_tenant):
    mock_tenant._is_super_admin = False
    resp = await client.post(
        f"{API}/toggle",
        json={"is_active": True},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 403


# ── GET /settings ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_settings_returns_existing_row(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    settings = make_settings(tenant_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = settings
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.get(f"{API}/settings", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["tone"] == "professional"
    assert data["post_frequency"] == "twice_weekly"
    assert data["requires_approval"] is True


@pytest.mark.asyncio
async def test_get_settings_auto_creates_from_defaults(client, mock_db, mock_tenant, tenant_id):
    """When no tenant row exists, settings are created from the platform defaults row."""
    mock_tenant.plan = "agency_small"

    defaults = make_settings(None, post_frequency="weekly", tone="conversational")

    no_row = MagicMock()
    no_row.scalar_one_or_none.return_value = None

    defaults_result = MagicMock()
    defaults_result.scalar_one_or_none.return_value = defaults

    mock_db.execute = AsyncMock(side_effect=[no_row, defaults_result])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    resp = await client.get(f"{API}/settings", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_settings_auto_creates_without_defaults_row(client, mock_db, mock_tenant, tenant_id):
    """Auto-create still works when the platform defaults row is also absent."""
    mock_tenant.plan = "agency_small"

    no_row = MagicMock()
    no_row.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(return_value=no_row)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    resp = await client.get(f"{API}/settings", headers={"Authorization": "Bearer test"})

    assert resp.status_code == 200
    mock_db.add.assert_called_once()


# ── PATCH /settings ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_settings_updates_tone(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    settings = make_settings(tenant_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = settings
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    resp = await client.patch(
        f"{API}/settings",
        json={"tone": "bold"},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert settings.tone == "bold"


@pytest.mark.asyncio
async def test_patch_settings_updates_topics(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    settings = make_settings(tenant_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = settings
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    new_topics = ["employer branding", "diversity hiring", "candidate experience"]
    resp = await client.patch(
        f"{API}/settings",
        json={"topics": new_topics},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert settings.topics == new_topics


@pytest.mark.asyncio
async def test_patch_settings_auto_engage_blocked_on_small_plan(client, mock_db, mock_tenant, tenant_id):
    """auto_engage=True must be rejected for agency_small tenants."""
    mock_tenant.plan = "agency_small"
    settings = make_settings(tenant_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = settings
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await client.patch(
        f"{API}/settings",
        json={"auto_engage": True},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_settings_auto_engage_allowed_on_medium_plan(client, mock_db, mock_tenant, tenant_id):
    """auto_engage=True is permitted for agency_medium tenants."""
    mock_tenant.plan = "agency_medium"
    settings = make_settings(tenant_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = settings
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    resp = await client.patch(
        f"{API}/settings",
        json={"auto_engage": True},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert settings.auto_engage is True


# ── POST /toggle ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_toggle_activates_marketing(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    settings = make_settings(tenant_id, is_active=False)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = settings
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    resp = await client.post(
        f"{API}/toggle",
        json={"is_active": True},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert settings.is_active is True


@pytest.mark.asyncio
async def test_toggle_pauses_marketing(client, mock_db, mock_tenant, tenant_id):
    mock_tenant.plan = "agency_small"
    settings = make_settings(tenant_id, is_active=True)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = settings
    mock_db.execute = AsyncMock(return_value=result_mock)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    resp = await client.post(
        f"{API}/toggle",
        json={"is_active": False},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 200
    assert settings.is_active is False


@pytest.mark.asyncio
async def test_toggle_other_tenant_forbidden_for_regular_tenant(client, mock_db, mock_tenant):
    """A non-super-admin tenant cannot toggle another tenant's settings."""
    mock_tenant.plan = "agency_small"
    mock_tenant._is_super_admin = False
    other_id = uuid.uuid4()

    resp = await client.post(
        f"{API}/toggle?tenant_id={other_id}",
        json={"is_active": True},
        headers={"Authorization": "Bearer test"},
    )

    assert resp.status_code == 403
