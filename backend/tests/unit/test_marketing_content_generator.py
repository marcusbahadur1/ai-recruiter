"""Unit tests for MarketingContentGenerator — validation, rotation helpers, generate_post."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.marketing.content_generator import (
    ContentGenerationError,
    MarketingContentGenerator,
    _validate,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


def make_tenant() -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.ai_provider = "anthropic"
    t.ai_api_key = None
    return t


def make_settings(**kwargs) -> MagicMock:
    s = MagicMock()
    s.tone = kwargs.get("tone", "professional")
    s.target_audience = kwargs.get("target_audience", "recruiters")
    s.post_types_enabled = kwargs.get("post_types_enabled", ["thought_leadership", "tip", "poll"])
    s.topics = kwargs.get("topics", ["AI recruiting", "talent acquisition", "hiring trends"])
    s.include_images = kwargs.get("include_images", False)
    return s


def make_account(**kwargs) -> MagicMock:
    a = MagicMock()
    a.account_name = kwargs.get("account_name", "Test Recruitment Agency")
    a.account_type = kwargs.get("account_type", "company")
    a.author_urn = "urn:li:organization:12345"
    return a


def make_post(post_type: str = "thought_leadership", topic: str | None = "AI recruiting", days_ago: int = 1) -> MagicMock:
    p = MagicMock()
    p.post_type = post_type
    p.topic = topic
    p.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return p


# ── _validate ─────────────────────────────────────────────────────────────────


def test_validate_passes_valid_content():
    # Should not raise
    _validate("Recruitment is evolving rapidly. Here are three key trends.", ["#Recruiting", "#HR"])


def test_validate_raises_on_empty_content():
    with pytest.raises(ContentGenerationError, match="empty"):
        _validate("", ["#Recruiting"])


def test_validate_raises_on_non_string_content():
    with pytest.raises(ContentGenerationError, match="empty"):
        _validate(None, ["#Recruiting"])  # type: ignore[arg-type]


def test_validate_raises_on_first_person_opener():
    with pytest.raises(ContentGenerationError, match="first-person"):
        _validate("I am excited to share this update.", ["#HR"])


def test_validate_passes_content_with_i_not_at_start():
    # "I" in the middle is fine
    _validate("When I think about recruiting, the future is bright.", ["#HR"])


def test_validate_raises_on_banned_phrase_game_changer():
    with pytest.raises(ContentGenerationError, match="game-changer"):
        _validate("This platform is a game-changer for hiring teams.", ["#HR"])


def test_validate_raises_on_banned_phrase_excited_to_share():
    with pytest.raises(ContentGenerationError, match="excited to share"):
        _validate("We are excited to share our new approach.", ["#HR"])


def test_validate_raises_on_banned_phrase_case_insensitive():
    with pytest.raises(ContentGenerationError, match="thrilled"):
        _validate("THRILLED to announce our new partnership.", ["#HR"])


def test_validate_raises_on_hashtag_without_hash():
    with pytest.raises(ContentGenerationError, match="does not start with '#'"):
        _validate("Great content here.", ["Recruiting", "#HR"])


def test_validate_raises_on_non_list_hashtags():
    with pytest.raises(ContentGenerationError, match="non-list"):
        _validate("Good content.", "#Recruiting")  # type: ignore[arg-type]


# ── get_next_topic ─────────────────────────────────────────────────────────────


def test_get_next_topic_returns_first_unused():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(topics=["AI recruiting", "talent acquisition", "hiring trends"])
    recent = [make_post(topic="AI recruiting", days_ago=5)]
    result = gen.get_next_topic(settings, recent)
    assert result == "talent acquisition"


def test_get_next_topic_no_recent_posts():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(topics=["AI recruiting", "talent acquisition"])
    result = gen.get_next_topic(settings, [])
    assert result == "AI recruiting"


def test_get_next_topic_avoids_topics_used_within_14_days():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(topics=["topic_a", "topic_b", "topic_c"])
    recent = [
        make_post(topic="topic_a", days_ago=3),
        make_post(topic="topic_b", days_ago=7),
    ]
    result = gen.get_next_topic(settings, recent)
    assert result == "topic_c"


def test_get_next_topic_allows_topic_used_over_14_days_ago():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(topics=["old_topic"])
    recent = [make_post(topic="old_topic", days_ago=15)]
    result = gen.get_next_topic(settings, recent)
    assert result == "old_topic"


def test_get_next_topic_fallback_when_all_used():
    gen = MarketingContentGenerator(make_tenant())
    topics = ["a", "b"]
    settings = make_settings(topics=topics)
    recent = [make_post(topic="a", days_ago=2), make_post(topic="b", days_ago=4)]
    result = gen.get_next_topic(settings, recent)
    assert result in topics


def test_get_next_topic_empty_topics_returns_fallback():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(topics=[])
    result = gen.get_next_topic(settings, [])
    assert result == "recruitment automation"


# ── get_next_post_type ────────────────────────────────────────────────────────


def test_get_next_post_type_no_recent_posts():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(post_types_enabled=["thought_leadership", "tip", "poll"])
    result = gen.get_next_post_type(settings, [])
    assert result == "thought_leadership"


def test_get_next_post_type_round_robins():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(post_types_enabled=["thought_leadership", "tip", "poll"])
    recent = [make_post(post_type="thought_leadership")]
    result = gen.get_next_post_type(settings, recent)
    assert result == "tip"


def test_get_next_post_type_wraps_around():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(post_types_enabled=["thought_leadership", "tip", "poll"])
    recent = [make_post(post_type="poll")]
    result = gen.get_next_post_type(settings, recent)
    assert result == "thought_leadership"


def test_get_next_post_type_single_type_always_returns_same():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(post_types_enabled=["tip"])
    result = gen.get_next_post_type(settings, [make_post(post_type="tip")])
    assert result == "tip"


def test_get_next_post_type_empty_list_returns_default():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(post_types_enabled=[])
    result = gen.get_next_post_type(settings, [])
    assert result == "thought_leadership"


# ── generate_post ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_post_returns_expected_keys():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(include_images=False)
    account = make_account()

    mock_ai_result = {
        "content": "Recruitment technology is reshaping how we find talent in 2026.",
        "hashtags": ["#Recruiting", "#HR", "#AI"],
    }

    with patch("app.services.ai_provider.AIProvider") as mock_ai_cls:
        mock_ai_instance = MagicMock()
        mock_ai_instance.complete_json = AsyncMock(return_value=mock_ai_result)
        mock_ai_cls.return_value = mock_ai_instance

        result = await gen.generate_post(settings, account, "thought_leadership", "AI recruiting")

    assert result["content"] == mock_ai_result["content"]
    assert result["hashtags"] == mock_ai_result["hashtags"]
    assert result["topic"] == "AI recruiting"
    assert result["image_url"] is None
    assert result["image_attribution"] is None


@pytest.mark.asyncio
async def test_generate_post_fetches_image_when_enabled():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(include_images=True)
    account = make_account()

    mock_ai_result = {
        "content": "Hiring the right talent starts with the right tools.",
        "hashtags": ["#Recruiting"],
    }
    mock_unsplash_result = {
        "image_url": "https://images.unsplash.com/photo-test",
        "download_trigger_url": "https://api.unsplash.com/photos/test/download",
        "attribution": {
            "photographer_name": "Jane Doe",
            "photographer_url": "https://unsplash.com/@janedoe",
            "unsplash_url": "https://unsplash.com",
        },
    }

    with patch("app.services.ai_provider.AIProvider") as mock_ai_cls, \
         patch("app.services.marketing.content_generator.UnsplashClient") as mock_unsplash_cls:

        mock_ai_instance = MagicMock()
        mock_ai_instance.complete_json = AsyncMock(return_value=mock_ai_result)
        mock_ai_cls.return_value = mock_ai_instance

        mock_unsplash_instance = MagicMock()
        mock_unsplash_instance.search_photo = AsyncMock(return_value=mock_unsplash_result)
        mock_unsplash_instance.trigger_download = AsyncMock(return_value=None)
        mock_unsplash_cls.return_value = mock_unsplash_instance

        result = await gen.generate_post(settings, account, "tip", "candidate experience")

    assert result["image_url"] == "https://images.unsplash.com/photo-test"
    assert result["image_attribution"]["photographer_name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_generate_post_raises_on_validation_failure():
    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(include_images=False)
    account = make_account()

    bad_ai_result = {
        "content": "I am excited to share this game-changer update.",
        "hashtags": ["#HR"],
    }

    with patch("app.services.ai_provider.AIProvider") as mock_ai_cls:
        mock_ai_instance = MagicMock()
        mock_ai_instance.complete_json = AsyncMock(return_value=bad_ai_result)
        mock_ai_cls.return_value = mock_ai_instance

        with pytest.raises(ContentGenerationError):
            await gen.generate_post(settings, account, "thought_leadership", "AI")


@pytest.mark.asyncio
async def test_generate_post_unsplash_rate_limit_does_not_fail():
    """UnsplashRateLimitError must be swallowed — post should still be created."""
    from app.services.marketing.unsplash_client import UnsplashRateLimitError

    gen = MarketingContentGenerator(make_tenant())
    settings = make_settings(include_images=True)
    account = make_account()

    mock_ai_result = {
        "content": "Great content about talent acquisition strategy.",
        "hashtags": ["#Talent"],
    }

    with patch("app.services.ai_provider.AIProvider") as mock_ai_cls, \
         patch("app.services.marketing.content_generator.UnsplashClient") as mock_unsplash_cls:

        mock_ai_cls.return_value.complete_json = AsyncMock(return_value=mock_ai_result)
        mock_unsplash_cls.return_value.search_photo = AsyncMock(side_effect=UnsplashRateLimitError("rate limit"))

        result = await gen.generate_post(settings, account, "tip", "candidate sourcing")

    assert result["content"] == mock_ai_result["content"]
    assert result["image_url"] is None
