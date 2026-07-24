from __future__ import annotations

from tct_engine.source_identity import (
    find_matching_source_story,
    normalize_source_identity_url,
    story_source_identity_urls,
)


def test_google_news_article_url_is_identity_and_tracking_is_removed() -> None:
    url = "https://news.google.com/rss/articles/ABC123?oc=5&utm_source=test#fragment"
    assert normalize_source_identity_url(url) == "https://news.google.com/rss/articles/ABC123"


def test_feed_and_search_urls_are_not_article_identities() -> None:
    assert normalize_source_identity_url(
        "https://news.google.com/rss/search?q=martin+county"
    ) == ""
    assert normalize_source_identity_url("https://www.wptv.com/news/local-news.rss") == ""
    assert normalize_source_identity_url("https://example.com/feed/local") == ""


def test_direct_article_url_keeps_identity_and_drops_tracking() -> None:
    assert normalize_source_identity_url(
        "https://Example.com/news/local/story/?utm_medium=social&id=7#top"
    ) == "https://example.com/news/local/story?id=7"
    assert normalize_source_identity_url("https://example.com/") == ""


def test_story_source_identity_collects_sources_and_candidates() -> None:
    story = {
        "sources": [
            "https://www.wptv.com/news/local-news.rss",
            "https://news.google.com/rss/articles/ABC123?oc=5",
        ],
        "title_candidates": [
            {"source": "https://example.com/news/story?utm_source=x"},
        ],
    }
    assert story_source_identity_urls(story) == frozenset(
        {
            "https://news.google.com/rss/articles/ABC123",
            "https://example.com/news/story",
        }
    )


def test_find_matching_source_story_ignores_shared_feed_urls() -> None:
    stories = (
        {
            "story_id": "story_000001",
            "sources": ["https://www.wptv.com/news/local-news.rss"],
        },
    )
    match = find_matching_source_story(
        "https://www.wptv.com/news/local-news.rss", stories
    )
    assert match.matched is False


def test_find_matching_source_story_accepts_exact_article_identity() -> None:
    stories = (
        {
            "story_id": "story_000001",
            "sources": ["https://news.google.com/rss/articles/ABC123?oc=5"],
        },
    )
    match = find_matching_source_story(
        "https://news.google.com/rss/articles/ABC123?utm_source=x", stories
    )
    assert match.matched is True
    assert match.story_id == "story_000001"
    assert match.confidence == 1.0
