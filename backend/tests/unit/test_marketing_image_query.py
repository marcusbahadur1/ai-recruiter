"""Unit tests for the rule-based Unsplash image query generator."""

import pytest

from app.services.marketing.image_query import generate_image_search_query, _extract_keywords


# ── _extract_keywords ─────────────────────────────────────────────────────────


def test_extract_keywords_basic():
    assert _extract_keywords("AI recruitment") == ["ai", "recruitment"]


def test_extract_keywords_strips_stop_words():
    result = _extract_keywords("the future of hiring")
    assert "the" not in result
    assert "of" not in result
    assert "future" in result
    assert "hiring" in result


def test_extract_keywords_respects_max_words():
    result = _extract_keywords("talent acquisition strategy transformation", max_words=2)
    assert len(result) == 2


def test_extract_keywords_empty_string():
    assert _extract_keywords("") == []


def test_extract_keywords_all_stop_words():
    assert _extract_keywords("the and or but") == []


def test_extract_keywords_strips_hyphens():
    result = _extract_keywords("time-to-hire reduction")
    assert "time" in result or "hire" in result


def test_extract_keywords_non_alpha_excluded():
    result = _extract_keywords("2026 hiring trends")
    assert "2026" not in result
    assert "hiring" in result


# ── generate_image_search_query ────────────────────────────────────────────────


def test_thought_leadership_appends_technology():
    q = generate_image_search_query("thought_leadership", "AI recruitment")
    assert "technology" in q
    assert "ai" in q or "recruitment" in q


def test_tip_appends_context():
    q = generate_image_search_query("tip", "reduce time to hire")
    assert "tips" in q


def test_success_story_appends_collaboration():
    q = generate_image_search_query("success_story", "remote onboarding")
    assert "collaboration" in q


def test_carousel_appends_workspace():
    q = generate_image_search_query("carousel", "employer branding")
    assert "workspace" in q


def test_industry_stat_uses_fallback():
    """industry_stat always uses fallback regardless of topic."""
    q = generate_image_search_query("industry_stat", "hiring trends 2026")
    assert q == "business data analytics"


def test_poll_uses_fallback():
    """poll always uses fallback regardless of topic."""
    q = generate_image_search_query("poll", "any topic")
    assert q == "business decision survey"


def test_unknown_post_type_uses_professional_context():
    q = generate_image_search_query("unknown_type", "leadership")
    assert "professional" in q or "leadership" in q


def test_all_stop_word_topic_returns_fallback():
    """When topic has only stop words, uses post-type fallback."""
    q = generate_image_search_query("thought_leadership", "the and or")
    assert q == "recruitment technology"


def test_returns_string():
    result = generate_image_search_query("tip", "candidate experience")
    assert isinstance(result, str)
    assert len(result) > 0
