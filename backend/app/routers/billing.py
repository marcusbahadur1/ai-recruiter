"""Billing management routes.

POST /billing/create-checkout-session — create a Stripe Checkout session
GET  /billing/portal                  — create a Stripe Customer Portal session
"""

import logging
from typing import Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

# ── Price ID lookup ───────────────────────────────────────────────────────────

_PRICE_IDS: dict[str, str] = {}


def _get_price_id(plan: str) -> str:
    """Return the Stripe price ID for the given plan, or raise 400 if not configured."""
    mapping = {
        "recruiter":    settings.stripe_price_recruiter,
        "agency_small": settings.stripe_price_agency_small,
        "agency_medium": settings.stripe_price_agency_medium,
    }
    price_id = mapping.get(plan, "")
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe price ID for plan '{plan}' is not configured. "
                   "Set STRIPE_PRICE_{PLAN} in environment variables.",
        )
    return price_id


# ── Request / response schemas ────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: Literal["recruiter", "agency_small", "agency_medium"]


class CheckoutResponse(BaseModel):
    checkout_url: str


class BillingPortalResponse(BaseModel):
    url: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/create-checkout-session", response_model=CheckoutResponse)
async def create_checkout_session(
    body: CheckoutRequest,
    tenant: Tenant = Depends(get_current_tenant),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for the requested subscription plan.

    The frontend should redirect to the returned checkout_url.
    On success, Stripe sends a webhook to /webhooks/stripe which activates
    the subscription and updates the tenant's plan.
    """
    stripe.api_key = settings.stripe_secret_key
    price_id = _get_price_id(body.plan)

    success_url = (
        f"{settings.frontend_url}/billing/success"
        f"?session_id={{CHECKOUT_SESSION_ID}}&plan={body.plan}"
    )
    cancel_url = f"{settings.frontend_url}/subscribe"

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=tenant.main_contact_email or None,
            metadata={
                "tenant_id": str(tenant.id),
                "plan": body.plan,
            },
            # Pre-fill customer if they've already subscribed before
            **({"customer": tenant.stripe_customer_id} if tenant.stripe_customer_id else {}),
        )
    except stripe.error.StripeError as exc:
        logger.error("create_checkout_session: Stripe error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {getattr(exc, 'user_message', None) or str(exc)}",
        ) from exc

    return CheckoutResponse(checkout_url=session.url)


@router.get("/portal", response_model=BillingPortalResponse)
async def get_billing_portal(
    tenant: Tenant = Depends(get_current_tenant),
) -> BillingPortalResponse:
    """Create a Stripe Customer Portal session for managing billing.

    Returns the portal URL; the frontend should redirect to it.
    Requires the tenant to have a Stripe customer ID (i.e. must have subscribed).
    """
    if not tenant.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Please subscribe to a plan first.",
        )

    stripe.api_key = settings.stripe_secret_key

    try:
        session = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=f"{settings.frontend_url}/settings?section=billing",
        )
    except stripe.error.StripeError as exc:
        logger.error("get_billing_portal: Stripe error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {getattr(exc, 'user_message', None) or str(exc)}",
        ) from exc

    return BillingPortalResponse(url=session.url)
