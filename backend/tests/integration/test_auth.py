"""Integration tests for /api/v1/auth routes (signup, login, get_current_tenant)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from tests.integration.conftest import make_db_mock


def _make_httpx_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def _db_override(mock_db):
    async def override():
        yield mock_db

    return override


# ── POST /auth/signup ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_success():
    """Supabase signup succeeds → 201 with access_token and tenant_id."""
    mock_db = make_db_mock()
    user_id = str(uuid.uuid4())

    app.dependency_overrides[get_db] = _db_override(mock_db)
    try:
        signup_resp = _make_httpx_response(
            201, {"user": {"id": user_id}, "access_token": "tok123"}
        )
        put_resp = _make_httpx_response(200, {})

        with (
            patch(
                "app.routers.auth._supabase_post",
                new=AsyncMock(return_value=signup_resp),
            ),
            patch(
                "app.routers.auth._supabase_put", new=AsyncMock(return_value=put_resp)
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/v1/auth/signup",
                    json={
                        "email": "new@example.com",
                        "password": "SecurePass123!",
                        "firm_name": "Acme Recruiting",
                        "slug": "acme-recruiting",
                    },
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 201
    data = resp.json()
    assert data["access_token"] == "tok123"
    assert data["user_id"] == user_id
    assert "tenant_id" in data


@pytest.mark.asyncio
async def test_signup_supabase_error():
    """Supabase returns 500 error → route returns 400."""
    mock_db = make_db_mock()

    app.dependency_overrides[get_db] = _db_override(mock_db)
    try:
        error_resp = _make_httpx_response(500, {"msg": "Internal server error"})

        with patch(
            "app.routers.auth._supabase_post", new=AsyncMock(return_value=error_resp)
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/v1/auth/signup",
                    json={
                        "email": "taken@example.com",
                        "password": "SecurePass123!",
                        "firm_name": "Dup Firm",
                        "slug": "dup-firm",
                    },
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 400
    assert "Internal server error" in resp.json()["detail"]


# ── POST /auth/login ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success():
    """Valid credentials → 200 with access_token, user_id, tenant_id."""
    user_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())

    login_resp = _make_httpx_response(
        200,
        {
            "access_token": "login_jwt",
            "user": {"id": user_id, "app_metadata": {"tenant_id": tenant_id}},
        },
    )

    with patch(
        "app.routers.auth._supabase_post", new=AsyncMock(return_value=login_resp)
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "correct_pass"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "login_jwt"
    assert data["user_id"] == user_id
    assert data["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """Wrong password → Supabase 401 → route returns 401."""
    error_resp = _make_httpx_response(401, {"error": "invalid_grant"})

    with patch(
        "app.routers.auth._supabase_post", new=AsyncMock(return_value=error_resp)
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "wrong_pass"},
            )

    assert resp.status_code == 401


# ── get_current_tenant dependency ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_tenant_missing_bearer():
    """Request without Bearer scheme → 401 (no Supabase call needed)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(
            "/api/v1/jobs",
            headers={"Authorization": "Basic abc123"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_current_tenant_invalid_token():
    """Expired / invalid JWT → Supabase returns 401 → route returns 401."""
    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(
        return_value=_make_httpx_response(401, {"error": "invalid_token"})
    )

    with patch("app.routers.auth.httpx.AsyncClient", return_value=mock_http_client):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get(
                "/api/v1/jobs",
                headers={"Authorization": "Bearer bad_token"},
            )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_current_tenant_no_tenant_id_in_metadata():
    """Valid token but no tenant_id in app_metadata → 403."""
    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(
        return_value=_make_httpx_response(
            200, {"id": str(uuid.uuid4()), "app_metadata": {}}
        )
    )

    with patch("app.routers.auth.httpx.AsyncClient", return_value=mock_http_client):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get(
                "/api/v1/jobs",
                headers={"Authorization": "Bearer orphan_token"},
            )

    assert resp.status_code == 403
