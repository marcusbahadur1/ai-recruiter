"""Billing management routes.

GET /billing/portal — create a Stripe Customer Portal session and return the URL
"""

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant

router = APIRouter(prefix="/billing", tags=["billing"])


class BillingPortalResponse(BaseModel):
    url: str


@router.get("/portal", response_model=BillingPortalResponse)
async def get_billing_portal(
    tenant: Tenant = Depends(get_current_tenant),
) -> BillingPortalResponse:
    """Create a Stripe Customer Portal session for managing billing.

    Returns the portal URL; the frontend should redirect to it.
    """
    if not tenant.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Please subscribe to a plan first via the AI Recruiter.",
        )

    stripe.api_key = settings.stripe_secret_key

    try:
        session = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=f"{settings.frontend_url}/settings?section=billing",
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {exc.user_message or str(exc)}",
        ) from exc

    return BillingPortalResponse(url=session.url)
