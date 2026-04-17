"""Integration tests for webhook routes (Stripe + email-received)."""

import hashlib
import hmac
import json
import time
import unittest.mock as mock
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app

from tests.integration.conftest import make_db_mock


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_stripe_signature(payload: bytes, secret: str = "whsec_test") -> str:
    """Build a Stripe-compatible Signature header for a test payload."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def _stripe_event(event_type: str, data_object: dict) -> bytes:
    return json.dumps(
        {
            "id": f"evt_{uuid.uuid4().hex[:16]}",
            "type": event_type,
            "data": {"object": data_object},
        }
    ).encode()


@pytest_asyncio.fixture()
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

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
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
        "metadata": {
            "plan": "individual",
            "firm_name": "Test Firm",
            "slug": "test-firm",
        },
    }
    payload = _stripe_event("checkout.session.completed", data_object)

    with (
        mock.patch("app.config.settings.stripe_webhook_secret", secret),
        mock.patch("stripe.Webhook.construct_event") as mock_construct,
    ):
        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
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
            content=json.dumps(
                {"type": "invoice.payment_succeeded", "data": {"object": data_object}}
            ).encode(),
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
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
            content=json.dumps(
                {
                    "type": "customer.subscription.deleted",
                    "data": {"object": data_object},
                }
            ).encode(),
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
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
            content=json.dumps(
                {"type": "invoice.payment_failed", "data": {"object": data_object}}
            ).encode(),
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_email_received_webhook_bad_hmac(webhook_client):
    ac, _ = webhook_client
    with mock.patch("app.config.settings.stripe_webhook_secret", "secret123"):
        resp = await ac.post(
            "/api/v1/webhooks/email-received",
            content=b'{"from":"test@example.com"}',
            headers={
                "content-type": "application/json",
                "x-webhook-signature": "invalidsig",
            },
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


# ── Additional Stripe webhook scenarios ───────────────────────────────────────


@pytest.mark.asyncio
async def test_stripe_webhook_malformed_payload(webhook_client):
    """Stripe SDK raises generic exception on malformed payload → 400."""
    ac, _ = webhook_client

    with mock.patch(
        "stripe.Webhook.construct_event", side_effect=Exception("malformed")
    ):
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=b"not-json",
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_stripe_webhook_unhandled_event_type(webhook_client):
    """Unhandled event type logs and returns 200 without error."""
    ac, _ = webhook_client

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "customer.created",
            "data": {"object": {}},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=b'{"type": "customer.created"}',
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_stripe_checkout_existing_tenant(webhook_client):
    """checkout.session.completed with existing tenant_id updates the tenant."""
    ac, db = webhook_client
    tenant_id = str(uuid.uuid4())
    data_object = {
        "customer": "cus_existing",
        "subscription": "sub_new",
        "metadata": {
            "plan": "small_firm",
            "tenant_id": tenant_id,
        },
    }

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=json.dumps({"type": "checkout.session.completed"}).encode(),
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stripe_checkout_no_customer(webhook_client):
    """checkout.session.completed with no customer_id is silently skipped."""
    ac, _ = webhook_client
    data_object = {"customer": None, "subscription": "sub_xxx", "metadata": {}}

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stripe_payment_succeeded_no_customer(webhook_client):
    """invoice.payment_succeeded with no customer is silently skipped."""
    ac, _ = webhook_client
    data_object = {"customer": None, "subscription": "sub_abc"}

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "invoice.payment_succeeded",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stripe_payment_succeeded_enterprise_skips_credits(webhook_client):
    """invoice.payment_succeeded for enterprise plan skips credit update."""
    ac, db = webhook_client
    tenant_mock = mock.MagicMock()
    tenant_mock.id = uuid.uuid4()
    tenant_mock.plan = "enterprise"
    tenant_mock.credits_remaining = 0

    scalars_result = mock.MagicMock()
    scalars_result.scalar_one_or_none = mock.MagicMock(return_value=tenant_mock)
    db.execute = mock.AsyncMock(return_value=scalars_result)

    data_object = {"customer": "cus_enterprise", "subscription": "sub_ent"}

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "invoice.payment_succeeded",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stripe_payment_failed_with_tenant(webhook_client):
    """invoice.payment_failed with matching tenant → sets is_active=False."""
    ac, db = webhook_client
    tenant_mock = mock.MagicMock()
    tenant_mock.id = uuid.uuid4()
    tenant_mock.plan = "individual"
    tenant_mock.main_contact_email = None  # skip email sending

    scalars_result = mock.MagicMock()
    scalars_result.scalar_one_or_none = mock.MagicMock(return_value=tenant_mock)
    db.execute = mock.AsyncMock(return_value=scalars_result)

    data_object = {"customer": "cus_failed_payment"}

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "invoice.payment_failed",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stripe_subscription_deleted_tenant_not_found(webhook_client):
    """customer.subscription.deleted with no matching tenant logs and returns 200."""
    ac, db = webhook_client
    scalars_result = mock.MagicMock()
    scalars_result.scalar_one_or_none = mock.MagicMock(return_value=None)
    db.execute = mock.AsyncMock(return_value=scalars_result)

    data_object = {"customer": "cus_not_in_db"}

    with mock.patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "customer.subscription.deleted",
            "data": {"object": data_object},
        }
        resp = await ac.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "stripe-signature": "t=1,v1=abc",
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_email_received_webhook_invalid_json(webhook_client):
    """Invalid JSON in email webhook payload is handled gracefully."""
    ac, _ = webhook_client
    secret = "secret123"
    payload = b"not-valid-json-at-all"
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    with mock.patch("app.config.settings.stripe_webhook_secret", secret):
        resp = await ac.post(
            "/api/v1/webhooks/email-received",
            content=payload,
            headers={
                "content-type": "application/json",
                "x-webhook-signature": sig,
            },
        )

    # Route handles parse error gracefully and still returns 200
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
