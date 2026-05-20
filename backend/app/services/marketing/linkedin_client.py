"""LinkedIn OAuth 2.0 client for the AI Marketing Module.

Handles authorization URL generation, token exchange, profile/company page
retrieval, post creation (with optional image upload), stats collection,
and engagement actions (like, comment, group post).

All methods log at DEBUG level. Tokens are never included in log output.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED MANUAL STEPS — LinkedIn Developer Portal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before this code will work for company/showcase page posting, complete
these steps at https://developer.linkedin.com (no LinkedIn review needed):

1. Go to developer.linkedin.com → your app → Products tab
2. Ensure "Share on LinkedIn" product is enabled (self-service, instant)
3. Ensure "Sign In with LinkedIn using OpenID Connect" is enabled

4. Go to Auth tab → OAuth 2.0 scopes
5. Add these scopes if not already present:
     openid              (OpenID Connect identity)
     profile             (basic profile — replaces deprecated r_liteprofile)
     w_member_social     (post to personal profile)
     w_organization_social (post to company/showcase pages)  ← REQUIRED FOR PAGES

6. Save. No LinkedIn review is needed for these four scopes.

7. Verify the app is linked to a verified LinkedIn Company Page
   (required by LinkedIn even for personal-posting apps — go to the
   App Info tab and check the "Company" field).

8. Update LINKEDIN_API_VERSION env var if LinkedIn releases a new version
   (currently 202502). The header is read from config — no code change needed.

SCOPE NOTES:
  • w_member_social allows posting to the authenticated user's personal feed.
  • w_organization_social allows posting as any company/showcase page that
    the authenticated user administers.
  • After adding w_organization_social, existing connected users must
    re-authenticate (re-click "Connect" in Settings → Channels → LinkedIn)
    to obtain the new scope in their access token.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_API_BASE = "https://api.linkedin.com/v2"
_API_REST = "https://api.linkedin.com/rest"
_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

# All connections now request the full set of scopes in a single OAuth flow.
# w_organization_social enables posting to company/showcase pages — only included
# once LinkedIn approves the Community Management API product for this app.
# Until then, page discovery returns [] on 403 and personal posting still works.
_SCOPES_PERSONAL = ["openid", "profile", "w_member_social"]
_SCOPES_COMPANY = ["openid", "profile", "w_member_social"]


def _api_version() -> str:
    """Return the LinkedIn-Version header value from config (defaults to 202502)."""
    try:
        from app.config import settings
        return settings.linkedin_api_version or "202502"
    except Exception:
        return "202502"


def _rest_headers(access_token: str) -> dict[str, str]:
    """Headers for LinkedIn REST API calls (newer /rest/ endpoints)."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": _api_version(),
    }


# ── Custom exceptions ──────────────────────────────────────────────────────────


class LinkedInRateLimitError(Exception):
    """Raised when the LinkedIn API rate limit is exhausted."""


class LinkedInAuthError(Exception):
    """Raised when the LinkedIn API returns 401 Unauthorized."""


# ── Client ─────────────────────────────────────────────────────────────────────


class LinkedInClient:
    """Async LinkedIn API client using httpx."""

    def __init__(self) -> None:
        from app.config import settings
        self._client_id = settings.linkedin_client_id or ""
        self._client_secret = settings.linkedin_client_secret or ""
        self._redirect_uri = settings.linkedin_redirect_uri or ""

    # ── OAuth helpers ──────────────────────────────────────────────────────────

    def get_authorization_url(self, state: str, account_type: str) -> str:
        """Build LinkedIn OAuth authorization URL with appropriate scopes.

        Personal profile: openid, profile, w_member_social
        Company page:     adds r_organization_social, w_organization_social
        """
        scopes = _SCOPES_COMPANY if account_type == "company" else _SCOPES_PERSONAL
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "state": state,
            "scope": " ".join(scopes),
        }
        query = urlencode(params)
        url = f"{_AUTH_URL}?{query}"
        logger.debug("LinkedIn auth URL built for account_type=%s", account_type)
        return url

    async def exchange_code_for_tokens(self, code: str) -> dict[str, Any]:
        """Exchange an authorization code for access + refresh tokens.

        Returns dict with: access_token, refresh_token, expires_in
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("LinkedIn token exchange succeeded")
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 0),
        }

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired access token.

        Returns dict with: access_token, refresh_token, expires_in
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("LinkedIn token refresh succeeded")
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 0),
        }

    # ── Profile / company data ─────────────────────────────────────────────────

    async def get_personal_profile(self, access_token: str) -> dict[str, Any]:
        """Fetch the authenticated user's basic profile via LinkedIn OIDC.

        Returns dict with: id, localizedFirstName, localizedLastName, name, picture
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _USERINFO_URL,
                headers=_auth_headers(access_token),
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        member_id = data.get("sub") or data.get("id", "")
        first = data.get("given_name") or data.get("localizedFirstName", "")
        last = data.get("family_name") or data.get("localizedLastName", "")
        logger.debug("LinkedIn personal profile fetched id=%s", member_id)
        return {
            "id": member_id,
            "localizedFirstName": first,
            "localizedLastName": last,
            "name": data.get("name") or f"{first} {last}".strip(),
            "picture": data.get("picture"),
        }

    async def get_admin_pages(self, access_token: str) -> list[dict[str, Any]]:
        """Return all organization URNs where the user is an admin.

        Uses the LinkedIn REST API (v202502). Returns list of dicts with:
          organizationalTarget — the org URN e.g. "urn:li:organization:12345678"

        Returns [] on 403 (scope w_organization_social not granted).
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_API_REST}/organizationAcls",
                    headers=_rest_headers(access_token),
                    params={"q": "roleAssignee"},
                )
            if resp.status_code == 403:
                logger.warning(
                    "LinkedIn organizationAcls 403 — w_organization_social scope missing"
                )
                return []
            _check_auth(resp)
            _check_rate_limit(resp)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            results = []
            for el in elements:
                org_urn = el.get("organizationalTarget", "")
                if org_urn:
                    results.append({"organizationalTarget": org_urn})
            logger.debug("LinkedIn admin pages fetched count=%d", len(results))
            return results
        except (LinkedInAuthError, LinkedInRateLimitError):
            raise
        except Exception as exc:
            logger.warning("LinkedIn get_admin_pages failed: %s", exc)
            return []

    async def get_organization(self, access_token: str, org_id: str) -> dict[str, Any] | None:
        """Fetch details for a single organization by its numeric ID.

        Returns dict with: localizedName, vanityName, logoV2, parentOrganization
        Returns None on error.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_API_REST}/organizations/{org_id}",
                    headers=_rest_headers(access_token),
                )
            if resp.status_code == 404:
                return None
            _check_auth(resp)
            _check_rate_limit(resp)
            resp.raise_for_status()
            return resp.json()
        except (LinkedInAuthError, LinkedInRateLimitError):
            raise
        except Exception as exc:
            logger.warning("LinkedIn get_organization org_id=%s failed: %s", org_id, exc)
            return None

    async def get_company_pages(self, access_token: str) -> list[dict[str, Any]]:
        """Return company pages the authenticated user administers.

        Returns list of dicts with: organizationId, organizationName
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_API_BASE}/organizationAcls",
                headers=_auth_headers(access_token),
                params={"q": "roleAssignee"},
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        pages = []
        for el in elements:
            org_urn: str = el.get("organization", "")
            # URN format: urn:li:organization:123456
            org_id = org_urn.split(":")[-1] if ":" in org_urn else org_urn
            pages.append({"organizationId": org_id, "organizationName": el.get("role", "")})
        logger.debug("LinkedIn company pages fetched count=%d", len(pages))
        return pages

    # ── Post creation ──────────────────────────────────────────────────────────

    async def create_post(
        self,
        access_token: str,
        author_urn: str,
        text: str,
        hashtags: list[str],
        image_url: str | None = None,
    ) -> str:
        """Create a LinkedIn UGC post and return the post URN (platform_post_id).

        If image_url is provided, the image is registered and uploaded via the
        LinkedIn asset upload API before the post is created.
        """
        # Merge hashtags into content if not already present
        content = text
        for tag in hashtags:
            if tag not in content:
                content = f"{content} {tag}"

        asset_urn: str | None = None
        if image_url:
            asset_urn = await self._upload_image(access_token, author_urn, image_url)

        payload = _build_ugc_post(author_urn, content, asset_urn)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_API_BASE}/ugcPosts",
                headers={**_auth_headers(access_token), "X-Restli-Protocol-Version": "2.0.0"},
                json=payload,
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()

        post_urn = resp.headers.get("X-RestLi-Id") or resp.json().get("id", "")
        logger.debug("LinkedIn post created urn=%s", post_urn)
        return post_urn

    async def _upload_image(
        self, access_token: str, author_urn: str, image_url: str
    ) -> str | None:
        """Register and upload an image asset. Returns the asset URN or None on failure."""
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": author_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Step 1: register upload
                reg_resp = await client.post(
                    f"{_API_BASE}/assets?action=registerUpload",
                    headers={**_auth_headers(access_token), "X-Restli-Protocol-Version": "2.0.0"},
                    json=register_payload,
                )
                reg_resp.raise_for_status()
                reg_data = reg_resp.json()
                upload_url: str = (
                    reg_data["value"]["uploadMechanism"]
                    ["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]
                    ["uploadUrl"]
                )
                asset_urn: str = reg_data["value"]["asset"]

                # Step 2: fetch image bytes from Unsplash URL
                img_resp = await client.get(image_url, follow_redirects=True, timeout=15.0)
                img_resp.raise_for_status()

                # Step 3: upload binary
                await client.put(
                    upload_url,
                    content=img_resp.content,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

            logger.debug("LinkedIn image uploaded asset_urn=%s", asset_urn)
            return asset_urn
        except Exception as exc:
            logger.warning("LinkedIn image upload failed, posting without image: %s", exc)
            return None

    async def create_post_v2(
        self,
        access_token: str,
        author_urn: str,
        text: str,
        hashtags: list[str],
        image_url: str | None = None,
    ) -> str:
        """Create a LinkedIn post using the new Posts API (LinkedIn-Version 202502).

        Supports both personal (urn:li:person:) and organization (urn:li:organization:) authors.
        Returns the post URN extracted from the Location header.
        """
        # Merge hashtags into body if not already present
        content = text
        for tag in hashtags:
            if tag not in content:
                content = f"{content} {tag}"

        image_urn: str | None = None
        if image_url:
            image_urn = await self._upload_image_v2(access_token, author_urn, image_url)

        payload: dict[str, Any] = {
            "author": author_urn,
            "commentary": content,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if image_urn:
            payload["content"] = {"media": {"id": image_urn}}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_API_REST}/posts",
                headers=_rest_headers(access_token),
                json=payload,
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()

        # LinkedIn returns the post URN in the Location header for 201 Created
        location = resp.headers.get("Location") or resp.headers.get("x-restli-id", "")
        post_urn = location.split("/")[-1] if "/" in location else location
        if not post_urn:
            try:
                post_urn = resp.json().get("id", "")
            except Exception:
                post_urn = ""
        logger.debug("LinkedIn Posts API v2: post created urn=%s author=%s", post_urn, author_urn)
        return post_urn

    async def _upload_image_v2(
        self, access_token: str, owner_urn: str, image_url: str
    ) -> str | None:
        """Register and upload an image using the new LinkedIn Images API.

        Returns the image URN to embed in the post payload, or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: initialize upload
                init_resp = await client.post(
                    f"{_API_REST}/images?action=initializeUpload",
                    headers=_rest_headers(access_token),
                    json={"initializeUploadRequest": {"owner": owner_urn}},
                )
                init_resp.raise_for_status()
                init_data = init_resp.json()
                upload_url: str = init_data["value"]["uploadUrl"]
                image_urn: str = init_data["value"]["image"]

                # Step 2: fetch image bytes
                img_resp = await client.get(image_url, follow_redirects=True, timeout=15.0)
                img_resp.raise_for_status()

                # Step 3: PUT binary to upload URL
                await client.put(
                    upload_url,
                    content=img_resp.content,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

            logger.debug("LinkedIn Images API v2: image uploaded urn=%s", image_urn)
            return image_urn
        except Exception as exc:
            logger.warning("LinkedIn image upload v2 failed, posting without image: %s", exc)
            return None

    # ── Stats ──────────────────────────────────────────────────────────────────

    async def get_post_stats(self, access_token: str, post_urn: str) -> dict[str, int]:
        """Return engagement stats for a post.

        Returns dict with: num_likes, num_comments, impressions
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_API_BASE}/socialActions/{post_urn}",
                headers=_auth_headers(access_token),
            )
        if resp.status_code == 404:
            return {"num_likes": 0, "num_comments": 0, "impressions": 0}
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        return {
            "num_likes": data.get("likesSummary", {}).get("totalLikes", 0),
            "num_comments": data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
            "impressions": data.get("impressionCount", 0),
        }

    # ── Engagement ─────────────────────────────────────────────────────────────

    async def like_post(
        self, access_token: str, actor_urn: str, post_urn: str
    ) -> bool:
        """Like a post. Returns True on success."""
        payload = {"actor": actor_urn}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_API_BASE}/socialActions/{post_urn}/likes",
                headers={**_auth_headers(access_token), "X-Restli-Protocol-Version": "2.0.0"},
                json=payload,
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        logger.debug("LinkedIn like posted on %s", post_urn)
        return resp.status_code in (200, 201, 204)

    async def comment_on_post(
        self, access_token: str, actor_urn: str, post_urn: str, text: str
    ) -> bool:
        """Comment on a post. Returns True on success."""
        payload = {
            "actor": actor_urn,
            "message": {"text": text},
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_API_BASE}/socialActions/{post_urn}/comments",
                headers={**_auth_headers(access_token), "X-Restli-Protocol-Version": "2.0.0"},
                json=payload,
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        logger.debug("LinkedIn comment posted on %s", post_urn)
        return resp.status_code in (200, 201)

    async def get_groups(self, access_token: str) -> list[dict[str, Any]]:
        """Return LinkedIn groups the authenticated user belongs to."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_API_BASE}/groups",
                headers=_auth_headers(access_token),
            )
        if resp.status_code == 404:
            return []
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()
        return resp.json().get("elements", [])

    async def post_to_group(
        self, access_token: str, group_id: str, text: str
    ) -> str:
        """Post to a LinkedIn group. Returns the post URN."""
        payload = {"text": text}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_API_BASE}/groups/{group_id}/posts",
                headers={**_auth_headers(access_token), "X-Restli-Protocol-Version": "2.0.0"},
                json=payload,
            )
        _check_auth(resp)
        _check_rate_limit(resp)
        resp.raise_for_status()
        post_urn = resp.headers.get("X-RestLi-Id") or resp.json().get("id", "")
        logger.debug("LinkedIn group post created group=%s urn=%s", group_id, post_urn)
        return post_urn


# ── Private helpers ────────────────────────────────────────────────────────────


def _auth_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _check_auth(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise LinkedInAuthError(f"LinkedIn 401: {resp.text[:200]}")


def _check_rate_limit(resp: httpx.Response) -> None:
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining == "0" or resp.status_code == 429:
        raise LinkedInRateLimitError("LinkedIn rate limit exhausted")


def _build_ugc_post(author_urn: str, content: str, asset_urn: str | None) -> dict:
    """Build the LinkedIn ugcPost payload."""
    share_content: dict[str, Any] = {
        "shareCommentary": {"text": content},
        "shareMediaCategory": "NONE" if not asset_urn else "IMAGE",
    }
    if asset_urn:
        share_content["media"] = [
            {
                "status": "READY",
                "description": {"text": ""},
                "media": asset_urn,
                "title": {"text": ""},
            }
        ]
    return {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": share_content,
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
        },
    }
