"""EmailDeductionService — derives and SMTP-verifies candidate email addresses.

Algorithm (SPEC §7.4.4):
1. Look up company domain via Google search.
2. Try common email formats: firstname.lastname, f.lastname, firstname, flastname.
3. SMTP-verify each candidate: connect, issue RCPT TO, check 250 — do NOT send.
4. Rate limit: max 5 SMTP checks per minute per domain.
5. Return first verified address (email_source='deduced'), or None.
"""

import asyncio
import logging
import smtplib
import socket
import time
from collections import defaultdict
from functools import partial
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_GOOGLE_SEARCH_URL = "https://api.scrapingdog.com/google"
_SMTP_TIMEOUT = 10  # seconds
_SMTP_FROM = "noreply@verify.local"
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60.0  # seconds


class EmailDeductionService:
    """Deduce and SMTP-verify candidate email addresses from name + company."""

    def __init__(self, scrapingdog_api_key: Optional[str] = None) -> None:
        # timestamps keyed by domain for sliding-window rate limiting
        self._rate_timestamps: dict[str, list[float]] = defaultdict(list)
        self._rate_lock = asyncio.Lock()
        self._scrapingdog_api_key = scrapingdog_api_key

    async def find_email(
        self,
        first_name: str,
        last_name: str,
        company: str,
    ) -> Optional[str]:
        """Attempt to deduce and SMTP-verify an email for a candidate.

        Args:
            first_name: Candidate's first name.
            last_name: Candidate's last name.
            company: Company name used to look up the domain.

        Returns:
            A verified email address string, or ``None`` if none could be found.
        """
        domain = await self._lookup_domain(company)
        if not domain:
            logger.info("EmailDeduction: could not resolve domain for %r", company)
            return None

        candidates = _email_candidates(first_name, last_name, domain)
        for address in candidates:
            verified = await self._smtp_verify(address, domain)
            if verified:
                logger.info("EmailDeduction: verified %r via SMTP", address)
                return address

        return None

    # ── Domain lookup ─────────────────────────────────────────────────────────

    async def _lookup_domain(self, company: str) -> Optional[str]:
        """Search Google for the company website domain."""
        if not self._scrapingdog_api_key:
            return None

        params = {
            "api_key": self._scrapingdog_api_key,
            "query": f"{company} official website",
            "advance_search": "false",
            "results": "5",
            "start": "0",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(_GOOGLE_SEARCH_URL, params=params)
                response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error("EmailDeduction domain lookup error for %r: %s", company, exc)
            return None

        data = response.json()
        for result in data.get("organic_results", []):
            link = result.get("link", "")
            domain = _extract_domain(link)
            if domain and not _is_social_domain(domain):
                return domain
        return None

    # ── SMTP verification ──────────────────────────────────────────────────────

    async def _smtp_verify(self, email: str, domain: str) -> bool:
        """SMTP-verify *email* without sending a message.

        Applies rate limiting: at most 5 SMTP checks per minute per domain.

        Args:
            email: The candidate email address to verify.
            domain: Used for rate-limit bucketing.

        Returns:
            ``True`` if the mail server returned a 250 for RCPT TO, else ``False``.
        """
        await self._wait_for_rate_limit(domain)
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, partial(_smtp_check, email))
        except Exception as exc:
            logger.debug("EmailDeduction SMTP check error for %r: %s", email, exc)
            return False

    async def _wait_for_rate_limit(self, domain: str) -> None:
        """Block until the rate limit allows another check for *domain*."""
        async with self._rate_lock:
            now = time.monotonic()
            window_start = now - _RATE_LIMIT_WINDOW
            timestamps = self._rate_timestamps[domain]
            # Prune entries outside the window
            timestamps[:] = [t for t in timestamps if t > window_start]

            if len(timestamps) >= _RATE_LIMIT_MAX:
                # Wait until the oldest entry falls outside the window
                sleep_for = timestamps[0] - window_start
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                # Re-prune after sleep
                now = time.monotonic()
                window_start = now - _RATE_LIMIT_WINDOW
                timestamps[:] = [t for t in timestamps if t > window_start]

            timestamps.append(time.monotonic())


# ── Module-level helpers ───────────────────────────────────────────────────────

def _email_candidates(first: str, last: str, domain: str) -> list[str]:
    """Return the standard email format guesses for a name + domain."""
    f = first.lower().strip()
    l = last.lower().strip()
    return [
        f"{f}.{l}@{domain}",
        f"{f[0]}.{l}@{domain}" if f else f".{l}@{domain}",
        f"{f}@{domain}",
        f"{f}{l}@{domain}",
    ]


def _smtp_check(email: str) -> bool:
    """Synchronous SMTP verification — run in a thread executor."""
    domain = email.split("@", 1)[-1]
    try:
        mx = _get_mx_host(domain)
        if not mx:
            return False
        with smtplib.SMTP(mx, port=25, timeout=_SMTP_TIMEOUT) as smtp:
            smtp.ehlo_or_helo_if_needed()
            smtp.mail(_SMTP_FROM)
            code, _ = smtp.rcpt(email)
            return code == 250
    except (smtplib.SMTPException, socket.error, OSError):
        return False


def _get_mx_host(domain: str) -> Optional[str]:
    """Resolve the first MX record for *domain* using dnspython if available,
    falling back to a direct connection attempt on the domain itself."""
    try:
        import dns.resolver  # type: ignore[import]

        records = dns.resolver.resolve(domain, "MX")
        best = sorted(records, key=lambda r: r.preference)[0]
        return str(best.exchange).rstrip(".")
    except Exception:
        # No dnspython or resolution failed — try the domain directly
        return domain


def _extract_domain(url: str) -> Optional[str]:
    """Extract the bare domain from a URL string."""
    url = url.lower()
    for prefix in ("https://", "http://", "www."):
        url = url.removeprefix(prefix)
    domain = url.split("/")[0].split("?")[0]
    return domain if "." in domain else None


_SOCIAL_DOMAINS = frozenset(
    {
        "linkedin.com",
        "facebook.com",
        "twitter.com",
        "instagram.com",
        "youtube.com",
        "wikipedia.org",
        "glassdoor.com",
        "indeed.com",
    }
)


def _is_social_domain(domain: str) -> bool:
    return any(domain.endswith(s) for s in _SOCIAL_DOMAINS)
