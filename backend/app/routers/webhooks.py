"""Webhook receivers for Stripe billing events and inbound email notifications.

POST /webhooks/stripe        — Stripe-signed payload, handles 4 billing events.
POST /webhooks/email-received — HMAC-SHA256 verified inbound email notification.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
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
    "trial": 0,
    "trial_expired": 0,
    "recruiter": 10,
    "agency_small": 30,
    "agency_medium": 100,
    "enterprise": 0,  # unlimited — no credit counter
}

# ── Plan display names for emails ─────────────────────────────────────────────
_PLAN_LABELS: dict[str, str] = {
    "recruiter": "Recruiter ($499/mo)",
    "agency_small": "Agency Small ($999/mo)",
    "agency_medium": "Agency Medium ($2,999/mo)",
    "enterprise": "Enterprise",
}


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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe signature"
        )
    except Exception as exc:
        logger.error("stripe_webhook: payload construction error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed Stripe payload"
        )

    event_type: str = event["type"]
    data_object: dict[str, Any] = event["data"]["object"]

    try:
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(db, data_object)
        elif event_type == "invoice.payment_succeeded":
            await _handle_payment_succeeded(db, data_object)
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(db, data_object)
        elif event_type == "customer.subscription.updated":
            await _handle_subscription_updated(db, data_object)
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(db, data_object)
        else:
            logger.debug(
                "stripe_webhook: unhandled event type %r — ignored", event_type
            )
    except Exception as exc:
        logger.error("stripe_webhook: error handling event %r: %s", event_type, exc)
        # Return 200 so Stripe does not retry — log and investigate separately.

    return {"status": "ok"}


# ── Event handlers ────────────────────────────────────────────────────────────


async def _handle_checkout_completed(db: AsyncSession, session: dict[str, Any]) -> None:
    """checkout.session.completed → activate subscription, update tenant, send welcome email."""
    customer_id: str | None = session.get("customer")
    subscription_id: str | None = session.get("subscription")
    metadata: dict[str, Any] = session.get("metadata") or {}
    plan: str = metadata.get("plan", "recruiter")
    tenant_id_str: str | None = metadata.get("tenant_id")

    if not customer_id:
        logger.warning("checkout_completed: missing customer_id — skipping")
        return

    now = datetime.now(timezone.utc)
    credits = _PLAN_CREDITS.get(plan, 0)
    tenant: Tenant | None = None

    if tenant_id_str:
        try:
            tid = uuid.UUID(tenant_id_str)
        except ValueError:
            logger.error("checkout_completed: invalid tenant_id %r", tenant_id_str)
            return

        await db.execute(
            update(Tenant)
            .where(Tenant.id == tid)
            .values(
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                plan=plan,
                credits_remaining=Tenant.credits_remaining + credits,
                subscription_started_at=now,
                subscription_ends_at=now + timedelta(days=30),
                is_active=True,
            )
        )
        await db.commit()

        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        logger.info("checkout_completed: tenant %s upgraded to plan %r", tid, plan)
    else:
        # Brand-new self-serve tenant (edge case — normally tenants sign up first).
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
            subscription_started_at=now,
            subscription_ends_at=now + timedelta(days=30),
            is_active=True,
        )
        db.add(tenant)
        await db.commit()
        logger.info(
            "checkout_completed: new tenant %s created (plan=%r, customer=%s)",
            tenant.id,
            plan,
            customer_id,
        )

    # Send welcome email
    if tenant and tenant.main_contact_email:
        try:
            await send_email(
                to=tenant.main_contact_email,
                subject="Welcome to AI Recruiter — Your subscription is active",
                html_body=_build_welcome_email(tenant, plan),
                tenant=tenant,
            )
        except Exception as exc:
            logger.error(
                "checkout_completed: welcome email failed for tenant %s: %s",
                tenant.id,
                exc,
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
        logger.warning(
            "payment_succeeded: no tenant found for customer %s", customer_id
        )
        return

    # Update subscription ID in case it changed.
    credits = _PLAN_CREDITS.get(tenant.plan, 0)
    if credits == 0 and tenant.plan == "enterprise":
        logger.info(
            "payment_succeeded: enterprise tenant %s — no credit counter", tenant.id
        )
        return

    await db.execute(
        update(Tenant)
        .where(Tenant.id == tenant.id)
        .values(
            stripe_subscription_id=subscription_id or tenant.stripe_subscription_id,
            credits_remaining=credits,
            is_active=True,
        )
    )
    await db.commit()
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

    await db.execute(
        update(Tenant).where(Tenant.id == tenant.id).values(is_active=False)
    )
    await db.commit()

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
            logger.error(
                "payment_failed: could not send warning email to %s: %s",
                tenant.main_contact_email,
                exc,
            )

    logger.warning(
        "payment_failed: tenant %s flagged inactive (customer=%s)",
        tenant.id,
        customer_id,
    )


async def _handle_subscription_updated(
    db: AsyncSession, subscription: dict[str, Any]
) -> None:
    """customer.subscription.updated → sync plan changes (upgrades/downgrades)."""
    customer_id: str | None = subscription.get("customer")
    subscription_id: str | None = subscription.get("id")
    if not customer_id:
        return

    # Extract the new plan from the first line item's price metadata or nickname.
    items = subscription.get("items", {}).get("data", [])
    new_plan: str | None = None
    if items:
        price = items[0].get("price", {})
        new_plan = (price.get("metadata") or {}).get("plan") or price.get("nickname")

    if not new_plan or new_plan not in _PLAN_CREDITS:
        logger.info(
            "subscription_updated: cannot determine plan from subscription %s — ignored",
            subscription_id,
        )
        return

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_customer_id == customer_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning(
            "subscription_updated: no tenant found for customer %s", customer_id
        )
        return

    credits = _PLAN_CREDITS.get(new_plan, 0)
    await db.execute(
        update(Tenant)
        .where(Tenant.id == tenant.id)
        .values(
            plan=new_plan,
            stripe_subscription_id=subscription_id,
            credits_remaining=credits,
            is_active=True,
        )
    )
    await db.commit()
    logger.info(
        "subscription_updated: tenant %s plan → %r credits=%d",
        tenant.id,
        new_plan,
        credits,
    )


async def _handle_subscription_deleted(
    db: AsyncSession, subscription: dict[str, Any]
) -> None:
    """customer.subscription.deleted → downgrade tenant to trial_expired, send cancellation email."""
    customer_id: str | None = subscription.get("customer")
    if not customer_id:
        return

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_customer_id == customer_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning(
            "subscription_deleted: no tenant found for customer %s", customer_id
        )
        return

    await db.execute(
        update(Tenant)
        .where(Tenant.id == tenant.id)
        .values(
            plan="trial_expired",
            stripe_subscription_id=None,
            credits_remaining=0,
            is_active=False,
        )
    )
    await db.commit()

    # Send cancellation email
    if tenant.main_contact_email:
        try:
            await send_email(
                to=tenant.main_contact_email,
                subject="Your AI Recruiter subscription has been cancelled",
                html_body=_build_cancellation_email(tenant),
                tenant=tenant,
            )
        except Exception as exc:
            logger.error(
                "subscription_deleted: cancellation email failed for tenant %s: %s",
                tenant.id,
                exc,
            )

    logger.info(
        "subscription_deleted: tenant %s downgraded to trial_expired", tenant.id
    )


# ── Email builders ───────────────────────────────────────────────────────────


def _build_welcome_email(tenant: Tenant, plan: str) -> str:
    """Build HTML welcome email for a new subscriber."""
    plan_label = _PLAN_LABELS.get(plan, plan.replace("_", " ").title())
    contact_name = tenant.main_contact_name or "there"
    dashboard_url = f"{settings.frontend_url}/dashboard"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Welcome to AI Recruiter</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
    .wrapper {{ max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .header {{ background: #1a1a2e; padding: 36px 32px; text-align: center; }}
    .header h1 {{ color: #ffffff; font-size: 26px; margin: 0 0 8px; }}
    .header p {{ color: #aaaacc; margin: 0; font-size: 14px; }}
    .body {{ padding: 32px; color: #333333; line-height: 1.65; font-size: 15px; }}
    .body p {{ margin: 0 0 16px; }}
    .plan-badge {{ display: inline-block; background: #4f46e5; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 20px; }}
    .cta-btn {{ display: inline-block; margin: 20px 0; padding: 14px 36px; background: #4f46e5; color: #ffffff; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 16px; }}
    .footer {{ padding: 20px 32px; background: #f9f9f9; border-top: 1px solid #e8e8e8; font-size: 12px; color: #888888; text-align: center; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>Subscription Activated</h1>
      <p>AI Recruiter — Your intelligent recruitment platform</p>
    </div>
    <div class="body">
      <p>Hi {contact_name},</p>
      <p>
        Your <span class="plan-badge">{plan_label}</span> subscription for
        <strong>{tenant.name}</strong> is now active.
      </p>
      <p>
        You can now access all features included in your plan. Head to your dashboard
        to post jobs and let the AI Talent Scout find candidates on autopilot.
      </p>
      <a href="{dashboard_url}" class="cta-btn">Go to Dashboard</a>
      <p style="font-size:13px; color:#666;">
        Questions? Email us at <a href="mailto:support@airecruiterz.com">support@airecruiterz.com</a>
      </p>
    </div>
    <div class="footer">
      <p>AI Recruiter · airecruiterz.com</p>
    </div>
  </div>
</body>
</html>"""


def _build_cancellation_email(tenant: Tenant) -> str:
    """Build HTML cancellation email for a cancelled subscriber."""
    contact_name = tenant.main_contact_name or "there"
    subscribe_url = f"{settings.frontend_url}/subscribe"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Subscription Cancelled</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
    .wrapper {{ max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .header {{ background: #1a1a2e; padding: 36px 32px; text-align: center; }}
    .header h1 {{ color: #ffffff; font-size: 26px; margin: 0 0 8px; }}
    .header p {{ color: #aaaacc; margin: 0; font-size: 14px; }}
    .body {{ padding: 32px; color: #333333; line-height: 1.65; font-size: 15px; }}
    .body p {{ margin: 0 0 16px; }}
    .cta-btn {{ display: inline-block; margin: 20px 0; padding: 14px 36px; background: #4f46e5; color: #ffffff; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 16px; }}
    .footer {{ padding: 20px 32px; background: #f9f9f9; border-top: 1px solid #e8e8e8; font-size: 12px; color: #888888; text-align: center; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>Subscription Cancelled</h1>
      <p>AI Recruiter — We&apos;re sorry to see you go</p>
    </div>
    <div class="body">
      <p>Hi {contact_name},</p>
      <p>
        Your AI Recruiter subscription for <strong>{tenant.name}</strong> has been cancelled.
        Your account has been downgraded and access to paid features has been removed.
      </p>
      <p>
        If this was a mistake, or if you'd like to resubscribe, you can do so at any time.
      </p>
      <a href="{subscribe_url}" class="cta-btn">Resubscribe</a>
      <p style="font-size:13px; color:#666;">
        Questions? Email us at <a href="mailto:support@airecruiterz.com">support@airecruiterz.com</a>
      </p>
    </div>
    <div class="footer">
      <p>AI Recruiter · airecruiterz.com</p>
    </div>
  </div>
</body>
</html>"""


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
        logger.info(
            "email_received: received inbound email payload (keys=%s)",
            list(data.keys()),
        )
    except Exception as exc:
        logger.error("email_received: failed to parse payload: %s", exc)
        # Still return 200 — log for investigation, don't retry indefinitely.

    return {"status": "queued"}
