"""Integration tests for promo code CRUD and public validation."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest



def _make_promo(tenant_id=None, **kwargs):
    p = MagicMock()
    p.id = kwargs.get("id", uuid.uuid4())
    p.tenant_id = tenant_id
    p.code = kwargs.get("code", "SAVE20")
    p.type = kwargs.get("type", "discount_pct")
    p.value = kwargs.get("value", Decimal("20"))
    p.expires_at = kwargs.get("expires_at", None)
    p.max_uses = kwargs.get("max_uses", None)
    p.uses_count = kwargs.get("uses_count", 0)
    p.is_active = kwargs.get("is_active", True)
    return p


@pytest.mark.asyncio
async def test_list_promo_codes_returns_200(client, mock_db, mock_tenant):
    promo = _make_promo(tenant_id=mock_tenant.id)
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=[promo])
    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=scalars)
    execute_result.scalar_one = MagicMock(return_value=1)

    call_count = 0

    async def mock_execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return execute_result

    mock_db.execute = mock_execute

    resp = await client.get("/api/v1/promo-codes")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_promo_code_returns_201(client, mock_db, mock_tenant):
    _make_promo(tenant_id=mock_tenant.id, code="NEWCODE")
    _scalars = MagicMock()
    _scalars.all = MagicMock(return_value=[])
    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=_scalars)
    execute_result.scalar_one = MagicMock(return_value=0)
    mock_db.execute = AsyncMock(return_value=execute_result)

    # Capture the added promo code via db.add()
    added_promo = None

    def capture_add(obj):
        nonlocal added_promo
        added_promo = obj

    mock_db.add = MagicMock(side_effect=capture_add)

    resp = await client.post("/api/v1/promo-codes", json={
        "code": "NEWCODE",
        "type": "credits",
        "value": "5",
        "is_active": True,
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_promo_code_returns_204(client, mock_db, mock_tenant):
    promo_id = uuid.uuid4()
    promo = _make_promo(tenant_id=mock_tenant.id, id=promo_id)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=promo)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.delete(f"/api/v1/promo-codes/{promo_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_nonexistent_promo_returns_404(client, mock_db):
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.delete(f"/api/v1/promo-codes/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validate_promo_code_valid(client, mock_db, mock_tenant):
    promo = _make_promo(tenant_id=None, code="PLATFORM10", type="discount_pct", value=Decimal("10"))
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=promo)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.post("/api/v1/promo-codes/validate", json={
        "code": "PLATFORM10",
        "tenant_id": str(mock_tenant.id),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["type"] == "discount_pct"


@pytest.mark.asyncio
async def test_validate_promo_code_invalid(client, mock_db):
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.post("/api/v1/promo-codes/validate", json={
        "code": "BADCODE",
        "tenant_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


@pytest.mark.asyncio
async def test_validate_promo_code_expired(client, mock_db, mock_tenant):
    expired_promo = _make_promo(
        tenant_id=None,
        code="EXPIRED",
        expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=expired_promo)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.post("/api/v1/promo-codes/validate", json={
        "code": "EXPIRED",
        "tenant_id": str(mock_tenant.id),
    })
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert "expired" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_validate_promo_max_uses_exceeded(client, mock_db, mock_tenant):
    maxed_promo = _make_promo(
        tenant_id=None,
        code="MAXED",
        max_uses=5,
        uses_count=5,
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=maxed_promo)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.post("/api/v1/promo-codes/validate", json={
        "code": "MAXED",
        "tenant_id": str(mock_tenant.id),
    })
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert "limit" in resp.json()["message"].lower()
