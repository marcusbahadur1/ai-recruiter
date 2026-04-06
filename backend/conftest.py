"""Root conftest: set test environment variables before any app module is imported.

This runs before pydantic-settings tries to read .env, so every required
setting is satisfied without a real .env file in CI or test environments.
"""

import os

# Fixed Fernet key for tests — 32 url-safe base64 bytes, consistent across runs
# Valid 32-byte URL-safe base64 Fernet key (DO NOT use outside tests)
_TEST_FERNET_KEY = "bXlfdGVzdF9rZXlfZm9yX3Rlc3RpbmdfcHVycG9zZXM="

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-openai-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy")
os.environ.setdefault("SENDGRID_API_KEY", "SG.test-platform-key")
os.environ.setdefault("IMAP_HOST", "mail.test.com")
os.environ.setdefault("IMAP_MASTER_PASSWORD", "test-password")
os.environ.setdefault("ENCRYPTION_KEY", _TEST_FERNET_KEY)
os.environ.setdefault("ENVIRONMENT", "development")
