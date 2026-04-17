"""SendGrid transactional email service.

Uses the tenant's sendgrid_api_key when configured, falling back to the
platform-level SENDGRID_API_KEY environment variable.
"""

import logging
from typing import TYPE_CHECKING

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config import settings
from app.services.crypto import decrypt

if TYPE_CHECKING:
    from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    tenant: "Tenant",
) -> bool:
    """Send a transactional email via SendGrid.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_body: HTML content of the email body.
        tenant: Tenant record; its ``sendgrid_api_key`` takes priority over the
                platform key when set.

    Returns:
        ``True`` if SendGrid accepted the message (2xx response), ``False`` otherwise.
    """
    api_key = _resolve_api_key(tenant)
    if not api_key:
        logger.error("send_email: no SendGrid API key available for tenant %s", tenant.id)
        return False

    from_email = _resolve_from_address(tenant)
    message = Mail(
        from_email=from_email,
        to_emails=to,
        subject=subject,
        html_content=html_body,
    )

    try:
        client = SendGridAPIClient(api_key)
        # SendGrid SDK is synchronous; the call is fast so thread overhead is negligible
        response = client.send(message)
        accepted = 200 <= response.status_code < 300
        if not accepted:
            logger.error(
                "SendGrid rejected message to %r (status %s): %s",
                to,
                response.status_code,
                response.body,
            )
        return accepted
    except Exception as exc:
        logger.error("send_email error sending to %r: %s", to, exc)
        return False


# ── Internal helpers ───────────────────────────────────────────────────────────

def _resolve_api_key(tenant: "Tenant") -> str | None:
    """Return the effective SendGrid API key (tenant > platform)."""
    if tenant.sendgrid_api_key:
        return decrypt(tenant.sendgrid_api_key)
    return settings.sendgrid_api_key or None


def _resolve_from_address(tenant: "Tenant") -> str:
    """Derive the From address: tenant inbox > platform setting > fallback."""
    if getattr(tenant, "email_inbox", None):
        return tenant.email_inbox
    return settings.sendgrid_from_email or "noreply@airecruiterz.com"
