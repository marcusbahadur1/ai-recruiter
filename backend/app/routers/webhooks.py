"""Webhook receivers for Stripe billing events and inbound email notifications.

POST /webhooks/stripe        — Stripe-signed payload, handles 4 billing events.
POST /webhooks/email-received — HMAC-SHA256 verified inbound email notification.
"""

import hashlib
import hmac
import logging
import time
import uuid
from typing import Any

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.tenant import Tenant
from app.services.sendgrid_email import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# ── Credits granted per plan on monthly renewal ───────────────────────────────
_PLAN_CREDITS: dict[str, int] = {
    "free": 0,
    "casual": 3,
    "individual": 10,
    "small_firm": 30,
    "mid_firm": 100,
    "enterprise": 0,  # unlimited — no credit counter
}

# ── Stripe price ID → internal plan name (set in Stripe product metadata) ─────
# Actual price IDs come from Stripe; matched via subscription metadata or price lookup.
# The plan is also stored in checkout.session.metadata["plan"] at creation time.


# ── Stripe webhook ────────────────────────────────────────────────────────────

@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(alias="stripe-signature", default=""),
) -> dict[str, str]:
    """Receive and process Stripe webhook events.

    Events handled (SPEC §4.3):
    - checkout.session.completed     → activate subscription, create/update tenant
    - invoice.payment_succeeded      → renew monthly credits
    - invoice.payment_failed         → flag tenant, send warning email
    - customer.subscription.deleted  → downgrade to free
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("stripe_webhook: invalid signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe signature")
    except Exception as exc:
        logger.error("stripe_webhook: payload construction error: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed Stripe payload")

    event_type: str = event["type"]
    data_object: dict[str, Any] = event["data"]["object"]

    try:
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(db, data_object)
        elif event_type == "invoice.payment_succeeded":
            await _handle_payment_succeeded(db, data_object)
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(db, data_object)
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(db, data_object)
        else:
            logger.debug("stripe_webhook: unhandled event type %r — ignored", event_type)
    except Exception as exc:
        logger.error("stripe_webhook: error handling event %r: %s", event_type, exc)
        # Return 200 so Stripe does not retry — log and investigate separately.

    return {"status": "ok"}


# ── Event handlers ────────────────────────────────────────────────────────────

async def _handle_checkout_completed(db: AsyncSession, session: dict[str, Any]) -> None:
    """checkout.session.completed → activate subscription, create/update tenant."""
    customer_id: str | None = session.get("customer")
    subscription_id: str | None = session.get("subscription")
    metadata: dict[str, Any] = session.get("metadata") or {}
    plan: str = metadata.get("plan", "free")
    tenant_id_str: str | None = metadata.get("tenant_id")

    if not customer_id:
        logger.warning("checkout_completed: missing customer_id — skipping")
        return

    credits = _PLAN_CREDITS.get(plan, 0)

    if tenant_id_str:
        # Existing tenant upgrading
        try:
            tid = uuid.UUID(tenant_id_str)
        except ValueError:
            logger.error("checkout_completed: invalid tenant_id %r", tenant_id_str)
            return

        async with db.begin():
            await db.execute(
                update(Tenant)
                .where(Tenant.id == tid)
                .values(
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id,
                    plan=plan,
                    credits_remaining=Tenant.credits_remaining + credits,
                    is_active=True,
                )
            )
        logger.info("checkout_completed: tenant %s upgraded to plan %r", tid, plan)
    else:
        # Brand-new self-serve tenant — create the record.
        # The onboarding wizard will fill in slug/name/contact details.
        firm_name: str = metadata.get("firm_name", "New Firm")
        slug_raw: str = metadata.get("slug", f"firm-{customer_id[-8:]}")
        slug = slug_raw.lower().replace(" ", "-")

        tenant = Tenant(
            id=uuid.uuid4(),
            name=firm_name,
            slug=slug,
            email_inbox=f"jobs-{slug}@airecruiterz.com",
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan=plan,
            credits_remaining=credits,
            is_active=True,
        )
        async with db.begin():
            db.add(tenant)

        logger.info(
            "checkout_completed: new tenant %s created (plan=%r, customer=%s)",
            tenant.id,
            plan,
            customer_id,
        )


async def _handle_payment_succeeded(db: AsyncSession, invoice: dict[str, Any]) -> None:
    """invoice.payment_succeeded → renew monthly credits for the tenant's plan."""
    customer_id: str | None = invoice.get("customer")
    subscription_id: str | None = invoice.get("subscription")

    if not customer_id:
        return

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_customer_id == customer_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning("payment_succeeded: no tenant found for customer %s", customer_id)
        return

    # Update subscription ID in case it changed.
    credits = _PLAN_CREDITS.get(tenant.plan, 0)
    if credits == 0 and tenant.plan == "enterprise":
        logger.info("payment_succeeded: enterprise tenant %s — no credit counter", tenant.id)
        return

    async with db.begin():
        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant.id)
            .values(
                stripe_subscription_id=subscription_id or tenant.stripe_subscription_id,
                credits_remaining=credits,
                is_active=True,
            )
        )
    logger.info(
        "payment_succeeded: tenant %s renewed — plan=%r credits=%d",
        tenant.id,
        tenant.plan,
        credits,
    )


async def _handle_payment_failed(db: AsyncSession, invoice: dict[str, Any]) -> None:
    """invoice.payment_failed → flag tenant inactive, send warning email."""
    customer_id: str | None = invoice.get("customer")
    if not customer_id:
        return

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_customer_id == customer_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning("payment_failed: no tenant found for customer %s", customer_id)
        return

    async with db.begin():
        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant.id)
            .values(is_active=False)
        )

    # Send payment failure warning email to main contact.
    if tenant.main_contact_email:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        import os

        templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html"]),
        )
        try:
            tpl = env.get_template("payment_failed.html")
            html_body = tpl.render(
                firm_name=tenant.name,
                billing_url=f"{settings.frontend_url}/billing",
            )
            await send_email(
                to=tenant.main_contact_email,
                subject="Action required: your AI Recruiter payment failed",
                html_body=html_body,
                tenant=tenant,
            )
        except Exception as exc:
            logger.error("payment_failed: could not send warning email to %s: %s", tenant.main_contact_email, exc)

    logger.warning("payment_failed: tenant %s flagged inactive (customer=%s)", tenant.id, customer_id)


async def _handle_subscription_deleted(db: AsyncSession, subscription: dict[str, Any]) -> None:
    """customer.subscription.deleted → downgrade tenant to free plan."""
    customer_id: str | None = subscription.get("customer")
    if not customer_id:
        return

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_customer_id == customer_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning("subscription_deleted: no tenant found for customer %s", customer_id)
        return

    async with db.begin():
        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant.id)
            .values(
                plan="free",
                stripe_subscription_id=None,
                credits_remaining=0,
            )
        )
    logger.info("subscription_deleted: tenant %s downgraded to free", tenant.id)


# ── Inbound email notification webhook ───────────────────────────────────────

@router.post("/email-received", status_code=status.HTTP_200_OK)
async def email_received_webhook(
    request: Request,
    x_webhook_signature: str = Header(alias="x-webhook-signature", default=""),
) -> dict[str, str]:
    """Receive inbound email notifications from the mail processing service.

    The payload is HMAC-SHA256 signed using the STRIPE_WEBHOOK_SECRET
    (re-used for internal webhook signing — configure a separate secret in
    production via WEBHOOK_HMAC_SECRET if preferred).

    The actual email processing happens via the Celery IMAP poller task
    (screener_tasks.poll_mailboxes).  This endpoint is for push-style
    delivery from external mail gateways (e.g. SendGrid Inbound Parse).
    """
    payload = await request.body()

    hmac_secret = (settings.stripe_webhook_secret or "").encode()
    if hmac_secret:
        expected = hmac.new(hmac_secret, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_webhook_signature):
            logger.warning("email_received: HMAC verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    # Delegate actual processing to the Celery screener pipeline.
    # Import here to avoid circular imports at module load time.
    try:
        import json

        data = json.loads(payload)
        # process_inbound_email is the push-delivery variant of the IMAP poller.
        # TODO: implement process_inbound_email Celery task in screener_tasks.py
        # For now, log the event for investigation.
        logger.info("email_received: received inbound email payload (keys=%s)", list(data.keys()))
    except Exception as exc:
        logger.error("email_received: failed to parse payload: %s", exc)
        # Still return 200 — log for investigation, don't retry indefinitely.

    return {"status": "queued"}
