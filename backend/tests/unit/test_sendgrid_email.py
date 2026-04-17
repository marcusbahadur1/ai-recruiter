"""Unit tests for the SendGrid email service."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.sendgrid_email import send_email


@pytest.fixture()
def mock_sendgrid_response(status_code: int = 202):
    response = MagicMock()
    response.status_code = status_code
    return response


# ── Happy path ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_email_uses_platform_key_when_tenant_has_none(tenant, monkeypatch):
    monkeypatch.setattr(
        "app.services.sendgrid_email.settings.sendgrid_api_key", "SG.platform-key"
    )

    mock_response = MagicMock()
    mock_response.status_code = 202

    with patch("app.services.sendgrid_email.SendGridAPIClient") as MockSG:
        MockSG.return_value.send.return_value = mock_response
        result = await send_email(
            to="candidate@example.com",
            subject="Your application",
            html_body="<p>Hello</p>",
            tenant=tenant,
        )

    MockSG.assert_called_once_with("SG.platform-key")
    assert result is True


@pytest.mark.asyncio
async def test_send_email_uses_tenant_key_when_configured(
    tenant_with_sendgrid_key, monkeypatch
):
    monkeypatch.setattr(
        "app.services.sendgrid_email.settings.sendgrid_api_key", "SG.platform-key"
    )

    mock_response = MagicMock()
    mock_response.status_code = 202

    with patch("app.services.sendgrid_email.SendGridAPIClient") as MockSG:
        MockSG.return_value.send.return_value = mock_response
        await send_email(
            to="candidate@example.com",
            subject="Hi",
            html_body="<p>Hello</p>",
            tenant=tenant_with_sendgrid_key,
        )

    # Tenant key takes priority over platform key
    MockSG.assert_called_once_with("SG.test-tenant-key")


@pytest.mark.asyncio
async def test_send_email_returns_false_on_4xx(tenant, monkeypatch):
    monkeypatch.setattr(
        "app.services.sendgrid_email.settings.sendgrid_api_key", "SG.platform-key"
    )

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.body = b"Bad Request"

    with patch("app.services.sendgrid_email.SendGridAPIClient") as MockSG:
        MockSG.return_value.send.return_value = mock_response
        result = await send_email(
            to="x@y.com",
            subject="Hi",
            html_body="<p>Hi</p>",
            tenant=tenant,
        )

    assert result is False


@pytest.mark.asyncio
async def test_send_email_returns_false_when_no_api_key(tenant, monkeypatch):
    monkeypatch.setattr("app.services.sendgrid_email.settings.sendgrid_api_key", None)
    tenant.sendgrid_api_key = None

    result = await send_email(
        to="x@y.com",
        subject="Hi",
        html_body="<p>Hi</p>",
        tenant=tenant,
    )

    assert result is False


@pytest.mark.asyncio
async def test_send_email_returns_false_on_sdk_exception(tenant, monkeypatch):
    monkeypatch.setattr(
        "app.services.sendgrid_email.settings.sendgrid_api_key", "SG.key"
    )

    with patch("app.services.sendgrid_email.SendGridAPIClient") as MockSG:
        MockSG.return_value.send.side_effect = Exception("network error")
        result = await send_email(
            to="x@y.com",
            subject="Hi",
            html_body="<p>Hi</p>",
            tenant=tenant,
        )

    assert result is False


@pytest.mark.asyncio
async def test_send_email_uses_tenant_inbox_as_from_address(tenant, monkeypatch):
    monkeypatch.setattr(
        "app.services.sendgrid_email.settings.sendgrid_api_key", "SG.key"
    )
    tenant.email_inbox = "jobs-myco@airecruiterz.com"

    mock_response = MagicMock()
    mock_response.status_code = 202

    with (
        patch("app.services.sendgrid_email.SendGridAPIClient") as MockSG,
        patch("app.services.sendgrid_email.Mail") as MockMail,
    ):
        MockSG.return_value.send.return_value = mock_response
        await send_email(
            to="c@example.com",
            subject="Hi",
            html_body="<p>Hi</p>",
            tenant=tenant,
        )

    MockMail.assert_called_once_with(
        from_email="jobs-myco@airecruiterz.com",
        to_emails="c@example.com",
        subject="Hi",
        html_content="<p>Hi</p>",
    )
