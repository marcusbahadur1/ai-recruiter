"""Shared fixtures for unit tests."""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
import respx

from app.services.crypto import encrypt


@asynccontextmanager
async def mock_http():
    """Async context manager that activates respx with the httpx-level mocker.

    Use this in tests instead of ``respx.mock`` to avoid the httpcore 1.0
    bytes/str incompatibility.
    """
    async with respx.mock(using="httpx") as mock:
        yield mock


@pytest.fixture()
def tenant():
    """Minimal Tenant-like object with encrypted API key fields."""
    t = MagicMock()
    t.id = uuid.uuid4()
    t.ai_provider = "anthropic"
    t.ai_api_key = None  # uses platform key by default
    t.sendgrid_api_key = None
    t.email_inbox = "jobs-test@airecruiterz.com"
    t.scrapingdog_api_key = None
    t.brightdata_api_key = None
    t.apollo_api_key = None
    t.hunter_api_key = None
    t.snov_api_key = None
    return t


@pytest.fixture()
def tenant_with_openai_key(tenant):
    """Tenant configured to use OpenAI with a custom API key."""
    tenant.ai_provider = "openai"
    tenant.ai_api_key = encrypt("sk-test-openai-key")
    return tenant


@pytest.fixture()
def tenant_with_sendgrid_key(tenant):
    """Tenant with a custom SendGrid key."""
    tenant.sendgrid_api_key = encrypt("SG.test-tenant-key")
    return tenant
