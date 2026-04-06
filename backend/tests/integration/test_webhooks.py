"""Integration tests for webhook routes (Stripe + email-received)."""

import hashlib
import hmac
import json
import time
import unittest.mock as mock
import uuid

import pytest
import stripe
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.routers.auth import get_current_tenant

from tests.integration.conftest import make_db_mock


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_stripe_signature(payload: bytes, secret: str = "whsec_test") -> str:
    """Build a Stripe-compatible Signature header for a test payload."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def _stripe_event(event_type: str, data_object: dict) -> bytes:
    return json.dumps({
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "type": event_type,
        "data": {"object": data_object},
    }).encode()


@pytest.fixture()
async def webhook_client():
    """Client with no auth override — webhooks are public endpoints."""
    db = make_db_mock()

    # Scalars mock returns None (no tenant found by default).
    scalars_result = mock.MagicMock()
    scalars_result.scalar_one_or_none = mock.MagicMock(return_value=None)
    db.execute = mock.AsyncMock(return_value=scalars_result)

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    # Don't override get_current_tenant — webhooks must not require it.

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, db

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_stripe_webhook_invalid_signature(webhook_client):
    ac, _ = webhook_client
    payload = _stripe_event("checkout.session.completed", {})
    resp = await ac.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"content-type": "application/json", "stripe-signature": "bad-sig"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_stripe_webhook_checkout_completed(webhook_client):
    ac, db = webhook_client
    secret = "whsec_test"
    customer_id = "cus_test123"
    data_object = {
        "customer": customer_id,
        "subscription": "sub_test456",
        "metadata": {"plan": "individual", "firm_name": "Test Firm", "slug": "test-firm"},
    }
    payload = _stripe_event("checkout.session.completed", data_object)

    with mock.patch("app.config.settings.stripe_webhook_secret", secret), \
         mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={"content-type": "application/json", "stripe-signature": "t=1,v1=abc"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_stripe_webhook_invoice_payment_succeeded(webhook_client):
    ac, db = webhook_client
    tenant_mock = mock.MagicMock()
    tenant_mock.id = uuid.uuid4()
    tenant_mock.plan = "individual"
    tenant_mock.credits_remaining = 5

    scalars_result = mock.MagicMock()
    scalars_result.scalar_one_or_none = mock.MagicMock(return_value=tenant_mock)
    db.execute = mock.AsyncMock(return_value=scalars_result)

    data_object = {"customer": "cus_abc", "subscription": "sub_abc"}

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "invoice.payment_succeeded",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=json.dumps({"type": "invoice.payment_succeeded", "data": {"object": data_object}}).encode(),
            headers={"content-type": "application/json", "stripe-signature": "t=1,v1=abc"},
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stripe_webhook_subscription_deleted(webhook_client):
    ac, db = webhook_client
    tenant_mock = mock.MagicMock()
    tenant_mock.id = uuid.uuid4()
    tenant_mock.plan = "individual"

    scalars_result = mock.MagicMock()
    scalars_result.scalar_one_or_none = mock.MagicMock(return_value=tenant_mock)
    db.execute = mock.AsyncMock(return_value=scalars_result)

    data_object = {"customer": "cus_delete_me"}

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "customer.subscription.deleted",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=json.dumps({"type": "customer.subscription.deleted", "data": {"object": data_object}}).encode(),
            headers={"content-type": "application/json", "stripe-signature": "t=1,v1=abc"},
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stripe_webhook_payment_failed_no_tenant(webhook_client):
    """invoice.payment_failed with unknown customer returns 200 (don't retry)."""
    ac, db = webhook_client
    data_object = {"customer": "cus_unknown"}

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "invoice.payment_failed",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=json.dumps({"type": "invoice.payment_failed", "data": {"object": data_object}}).encode(),
            headers={"content-type": "application/json", "stripe-signature": "t=1,v1=abc"},
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_email_received_webhook_bad_hmac(webhook_client):
    ac, _ = webhook_client
    with mock.patch("app.config.settings.stripe_webhook_secret", "secret123"):
        resp = await ac.post(
            "/api/v1/webhooks/email-received",
            content=b'{"from":"test@example.com"}',
            headers={"content-type": "application/json", "x-webhook-signature": "invalidsig"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_received_webhook_valid_hmac(webhook_client):
    ac, _ = webhook_client
    secret = "secret123"
    payload = b'{"from":"test@example.com","subject":"TEST1234 - John Smith"}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    with mock.patch("app.config.settings.stripe_webhook_secret", secret):
        resp = await ac.post(
            "/api/v1/webhooks/email-received",
            content=payload,
            headers={"content-type": "application/json", "x-webhook-signature": sig},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
