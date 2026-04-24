"""AI content generation engine for the AI Marketing Module.

Uses the existing AIProvider facade — never calls the Anthropic SDK directly.
Unsplash image fetching is integrated here: fire-and-forget trigger_download
is scheduled via asyncio.create_task after a photo is selected.
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from app.services.marketing.image_query import generate_image_search_query
from app.services.marketing.unsplash_client import UnsplashClient, UnsplashRateLimitError

if TYPE_CHECKING:
    from app.models.marketing import MarketingAccount, MarketingPost, MarketingSettings
    from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# ── Content validation ─────────────────────────────────────────────────────────

_BANNED_PHRASES = [
    "game-changer",
    "excited to share",
    "thrilled",
    "delighted",
]

# ── Post type config ───────────────────────────────────────────────────────────

_LENGTH_GUIDELINE: dict[str, str] = {
    "thought_leadership": "150-200 words",
    "industry_stat":      "80-100 words",
    "success_story":      "120-150 words",
    "tip":                "100-120 words",
    "poll":               "30-40 words (question only — do not add commentary)",
    "carousel":           "exactly 5 slide titles, each followed by one sentence description",
}

_HASHTAG_COUNT: dict[str, int] = {
    "thought_leadership": 5,
    "industry_stat":      3,
    "success_story":      5,
    "tip":                3,
    "poll":               3,
    "carousel":           3,
}

_TONE_GUIDANCE: dict[str, str] = {
    "professional":    "formal, authoritative, and polished",
    "conversational":  "warm, approachable, and direct — like talking to a peer",
    "bold":            "confident, provocative, and memorable — short punchy sentences",
    "educational":     "clear, structured, and informative — lead with insight",
}


class ContentGenerationError(Exception):
    """Raised when AI output fails validation checks."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class MarketingContentGenerator:
    """Generate LinkedIn post content using the AIProvider facade."""

    def __init__(self, tenant: "Tenant") -> None:
        self._tenant = tenant

    # ── Public API ─────────────────────────────────────────────────────────────

    async def generate_post(
        self,
        settings: "MarketingSettings",
        account: "MarketingAccount",
        post_type: str,
        topic: str,
    ) -> dict[str, Any]:
        """Generate content + optional image for a single post.

        Returns:
          {
            content:           str,
            hashtags:          list[str],
            topic:             str,
            image_search_query: str | None,
            image_url:         str | None,
            image_attribution: dict | None,
          }

        Raises ContentGenerationError if AI output fails validation.
        """
        prompt = _build_prompt(settings, account, post_type, topic)

        from app.services.ai_provider import AIProvider
        raw: dict[str, Any] = await AIProvider(self._tenant).complete_json(
            prompt=prompt,
            system=(
                "You are an expert social media content writer for a recruitment agency. "
                "Always respond with valid JSON only. No markdown, no explanation outside the JSON."
            ),
            max_tokens=1024,
        )

        content: str = raw.get("content", "")
        hashtags: list[str] = raw.get("hashtags", [])

        _validate(content, hashtags)

        # ── Image fetch ────────────────────────────────────────────────────────
        image_search_query: str | None = None
        image_url: str | None = None
        image_attribution: dict | None = None

        if settings.include_images:
            image_search_query = generate_image_search_query(post_type, topic)
            try:
                result = await UnsplashClient().search_photo(image_search_query)
                if result:
                    image_url = result["image_url"]
                    image_attribution = result["attribution"]
                    # Fire-and-forget ToS trigger — must not block post creation
                    asyncio.create_task(
                        UnsplashClient().trigger_download(result["download_trigger_url"])
                    )
            except UnsplashRateLimitError:
                logger.warning("Unsplash rate limit hit — post will have no image")
            except Exception as exc:
                logger.warning("Unsplash search failed (non-fatal): %s", exc)

        logger.info(
            "MarketingContentGenerator: post generated type=%s topic=%r words=%d",
            post_type,
            topic,
            len(content.split()),
        )

        return {
            "content": content,
            "hashtags": hashtags,
            "topic": topic,
            "image_search_query": image_search_query,
            "image_url": image_url,
            "image_attribution": image_attribution,
        }

    # ── Rotation helpers ───────────────────────────────────────────────────────

    def get_next_topic(
        self,
        settings: "MarketingSettings",
        recent_posts: "list[MarketingPost]",
    ) -> str:
        """Return the next topic to use, avoiding topics used in the last 14 days.

        Falls back to random.choice(settings.topics) if all topics were
        recently used or the topics list is empty.
        """
        all_topics: list[str] = list(settings.topics or [])
        if not all_topics:
            return "recruitment automation"

        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        recently_used = {
            p.topic
            for p in recent_posts
            if p.topic and p.created_at >= cutoff
        }

        available = [t for t in all_topics if t not in recently_used]
        if available:
            return available[0]

        # All topics recently used — pick least recently used
        logger.debug("All topics used in last 14 days — falling back to random choice")
        return random.choice(all_topics)

    def get_next_post_type(
        self,
        settings: "MarketingSettings",
        recent_posts: "list[MarketingPost]",
    ) -> str:
        """Return the next post type in round-robin rotation.

        Never returns the same type as the most recent post.
        Falls back to the first enabled type if rotation is exhausted.
        """
        enabled: list[str] = list(settings.post_types_enabled or [])
        if not enabled:
            return "thought_leadership"

        if len(enabled) == 1:
            return enabled[0]

        last_type: str | None = recent_posts[0].post_type if recent_posts else None

        # Find the index after the last used type and cycle from there
        if last_type and last_type in enabled:
            start = (enabled.index(last_type) + 1) % len(enabled)
        else:
            start = 0

        # Return next type that differs from the most recent
        for i in range(len(enabled)):
            candidate = enabled[(start + i) % len(enabled)]
            if candidate != last_type:
                return candidate

        return enabled[0]


# ── Private helpers ────────────────────────────────────────────────────────────


def _build_prompt(
    settings: "MarketingSettings",
    account: "MarketingAccount",
    post_type: str,
    topic: str,
) -> str:
    length = _LENGTH_GUIDELINE.get(post_type, "100-150 words")
    hashtag_count = _HASHTAG_COUNT.get(post_type, 3)
    tone_desc = _TONE_GUIDANCE.get(settings.tone, settings.tone)
    audience = settings.target_audience or "recruitment professionals"
    post_type_label = post_type.replace("_", " ").title()

    return f"""You are writing a LinkedIn post for {account.account_name}, a recruitment agency.

Post type:       {post_type_label}
Topic:           {topic}
Target audience: {audience}
Tone:            {tone_desc}
Length:          {length}
Hashtags:        Include exactly {hashtag_count} relevant hashtags

Instructions:
- Write for LinkedIn — professional network context
- Do NOT start with "I " as the first word
- Do NOT use any of these phrases: game-changer, excited to share, thrilled, delighted
- Hashtags must each start with the # character
- Return ONLY valid JSON with this exact structure:

{{
  "content": "<the post text, hashtags NOT included here>",
  "hashtags": ["#tag1", "#tag2", ...]
}}"""


def _validate(content: str, hashtags: list) -> None:
    """Raise ContentGenerationError if the AI response fails quality checks."""
    if not content or not isinstance(content, str):
        raise ContentGenerationError("AI returned empty or non-string content")

    if not isinstance(hashtags, list):
        raise ContentGenerationError("AI returned non-list hashtags field")

    if content.lstrip().startswith("I "):
        raise ContentGenerationError(
            "Content starts with 'I ' — rewrite to avoid first-person opening"
        )

    content_lower = content.lower()
    for phrase in _BANNED_PHRASES:
        if phrase.lower() in content_lower:
            raise ContentGenerationError(
                f"Content contains banned phrase: '{phrase}'"
            )

    for tag in hashtags:
        if not isinstance(tag, str) or not tag.startswith("#"):
            raise ContentGenerationError(
                f"Hashtag {tag!r} does not start with '#'"
            )
