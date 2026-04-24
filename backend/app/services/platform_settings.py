"""Runtime platform settings stored in Redis.

These settings can be toggled at runtime by the super admin without requiring
a deployment or env var change. Redis is the source of truth; the env var is
the fallback when Redis is unavailable or the key has never been set.
"""

import logging

logger = logging.getLogger(__name__)

_KEY_EMAIL_TEST_MODE = "platform:email_test_mode"
_KEY_EMAIL_TEST_RECIPIENT = "platform:email_test_recipient"


def _get_redis():
    from app.config import settings
    import redis as redis_lib
    return redis_lib.from_url(settings.redis_url, socket_connect_timeout=2, decode_responses=True)


def get_email_test_mode() -> tuple[bool, str | None]:
    """Return (enabled, recipient).

    Reads from Redis first. Falls back to env-var values if Redis is
    unavailable or the key was never set via the super admin UI.
    """
    from app.config import settings
    try:
        r = _get_redis()
        mode_val = r.get(_KEY_EMAIL_TEST_MODE)
        recipient_val = r.get(_KEY_EMAIL_TEST_RECIPIENT)
        if mode_val is not None:
            return mode_val == "true", recipient_val or settings.email_test_recipient
    except Exception as exc:
        logger.warning("platform_settings: Redis unavailable, falling back to env: %s", exc)
    return settings.email_test_mode, settings.email_test_recipient


def set_email_test_mode(enabled: bool, recipient: str | None = None) -> None:
    """Persist email test mode toggle to Redis.

    If ``recipient`` is None and a recipient is already stored in Redis it is
    preserved; clearing it requires passing an explicit empty string.
    """
    r = _get_redis()
    r.set(_KEY_EMAIL_TEST_MODE, "true" if enabled else "false")
    if recipient is not None:
        if recipient:
            r.set(_KEY_EMAIL_TEST_RECIPIENT, recipient)
        else:
            r.delete(_KEY_EMAIL_TEST_RECIPIENT)
