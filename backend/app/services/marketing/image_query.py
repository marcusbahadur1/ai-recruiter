"""Rule-based Unsplash search query generator for marketing post types.

No AI calls — pure keyword extraction and mapping.
Keeps queries short (2–4 words) for best Unsplash results.
"""

# Context words appended based on post type to steer Unsplash results
_POST_TYPE_CONTEXT: dict[str, str] = {
    "thought_leadership": "technology",
    "industry_stat": "analytics",
    "success_story": "collaboration",
    "tip": "tips",
    "poll": "survey",
    "carousel": "workspace",
}

# Fallback queries when topic extraction yields nothing useful
_POST_TYPE_FALLBACK: dict[str, str] = {
    "thought_leadership": "recruitment technology",
    "industry_stat": "business data analytics",
    "success_story": "team success collaboration",
    "tip": "professional development tips",
    "poll": "business decision survey",
    "carousel": "modern office workspace",
}

# Short filler words to strip from topic before extraction
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "how", "what", "why", "when", "where", "who", "which", "that", "this",
    "as", "if", "it", "its", "we", "our", "your", "their", "my",
}


def generate_image_search_query(post_type: str, topic: str) -> str:
    """Return a 2–4 word Unsplash search string for the given post type and topic.

    Rule-based only — no AI calls.

    Examples:
      generate_image_search_query("thought_leadership", "AI recruitment")
      → "recruitment technology"

      generate_image_search_query("industry_stat", "hiring trends 2026")
      → "business data analytics"

      generate_image_search_query("tip", "reduce time to hire")
      → "hire tips"
    """
    context = _POST_TYPE_CONTEXT.get(post_type, "professional")
    fallback = _POST_TYPE_FALLBACK.get(post_type, "professional business")

    keywords = _extract_keywords(topic, max_words=2)
    if not keywords:
        return fallback

    if post_type in ("industry_stat", "poll"):
        # These post types look better with generic imagery regardless of topic
        return fallback

    query = " ".join(keywords) + " " + context
    return query.strip()


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_keywords(text: str, max_words: int = 2) -> list[str]:
    """Extract the first N meaningful (non-stop) words from a topic string."""
    words = text.lower().replace("-", " ").split()
    meaningful = [w for w in words if w.isalpha() and w not in _STOP_WORDS]
    return meaningful[:max_words]
