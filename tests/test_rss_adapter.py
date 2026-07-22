from datetime import datetime, timezone

import pytest

from tct_engine import (
    RawArticle,
    RSSArticleAdapter,
    RSSArticleError,
)


def test_converts_feed_entry_to_raw_article():
    adapter = RSSArticleAdapter()

    entry = {
        "id": "https://example.com/story-1",
        "title": "Deputies rescue 80 cats from Stuart home",
        "link": "https://example.com/story-1",
        "summary": "Deputies rescued 80 cats from a Stuart residence.",
        "published_parsed": (
            2026,
            7,
            20,
            14,
            30,
            0,
            0,
            0,
            0,
        ),
    }

    result = adapter.convert(
        entry,
        source="WPTV",
        county="Martin",
    )

    assert isinstance(result, RawArticle)
    assert result.article_id == "https://example.com/story-1"
    assert result.title == "Deputies rescue 80 cats from Stuart home"
    assert result.body == (
        "Deputies rescued 80 cats from a Stuart residence."
    )
    assert result.source == "WPTV"
    assert result.url == "https://example.com/story-1"
    assert result.county == "Martin"
    assert result.is_custom is False
    assert result.published_at == datetime(
        2026,
        7,
        20,
        14,
        30,
        tzinfo=timezone.utc,
    )


def test_prefers_full_content_over_summary():
    adapter = RSSArticleAdapter()

    entry = {
        "id": "story-2",
        "title": "Fire damages Fort Pierce business",
        "link": "https://example.com/story-2",
        "summary": "A fire damaged a local business.",
        "content": [
            {
                "value": (
                    "St. Lucie County Fire District crews responded "
                    "to a fire at a Fort Pierce business."
                )
            }
        ],
    }

    result = adapter.convert(
        entry,
        source="WPTV",
        county="St. Lucie",
    )

    assert result.body == (
        "St. Lucie County Fire District crews responded "
        "to a fire at a Fort Pierce business."
    )


def test_falls_back_to_summary_detail():
    adapter = RSSArticleAdapter()

    entry = {
        "id": "story-3",
        "title": "Road closes after crash",
        "link": "https://example.com/story-3",
        "summary_detail": {
            "value": "A crash closed the road Tuesday morning."
        },
    }

    result = adapter.convert(
        entry,
        source="TCPalm",
        county="Martin",
    )

    assert result.body == "A crash closed the road Tuesday morning."


def test_generates_stable_id_when_feed_id_is_missing():
    adapter = RSSArticleAdapter()

    entry = {
        "title": "Community meeting scheduled",
        "link": "https://example.com/community-meeting",
        "summary": "Residents are invited to attend.",
    }

    first = adapter.convert(entry, source="City of Stuart")
    second = adapter.convert(entry, source="City of Stuart")

    assert first.article_id == second.article_id
    assert first.article_id.startswith("rss-")


def test_custom_source_is_marked_custom():
    adapter = RSSArticleAdapter(
        custom_sources={"Treasure Coast Today"},
    )

    entry = {
        "id": "tct-1",
        "title": "TCT custom report",
        "link": "https://treasurecoast.today/story",
        "summary": "Original reporting by Treasure Coast Today.",
    }

    result = adapter.convert(
        entry,
        source="Treasure Coast Today",
    )

    assert result.is_custom is True


def test_explicit_custom_flag_overrides_source_detection():
    adapter = RSSArticleAdapter()

    entry = {
        "id": "manual-1",
        "title": "Manually submitted article",
        "link": "https://treasurecoast.today/manual",
        "summary": "A manually submitted report.",
    }

    result = adapter.convert(
        entry,
        source="Treasure Coast Today",
        is_custom=True,
    )

    assert result.is_custom is True


def test_missing_title_raises_error():
    adapter = RSSArticleAdapter()

    entry = {
        "id": "story-without-title",
        "link": "https://example.com/no-title",
        "summary": "This entry has no title.",
    }

    with pytest.raises(RSSArticleError, match="title"):
        adapter.convert(entry, source="WPTV")


def test_missing_body_raises_error():
    adapter = RSSArticleAdapter()

    entry = {
        "id": "story-without-body",
        "title": "Entry without article text",
        "link": "https://example.com/no-body",
    }

    with pytest.raises(RSSArticleError, match="body"):
        adapter.convert(entry, source="WPTV")


def test_missing_url_raises_error():
    adapter = RSSArticleAdapter()

    entry = {
        "id": "story-without-url",
        "title": "Entry without URL",
        "summary": "This entry has text but no link.",
    }

    with pytest.raises(RSSArticleError, match="URL"):
        adapter.convert(entry, source="WPTV")


def test_html_is_removed_from_article_body():
    adapter = RSSArticleAdapter()

    entry = {
        "id": "html-story",
        "title": "Crash closes U.S. 1",
        "link": "https://example.com/html-story",
        "summary": (
            "<p>A <strong>crash</strong> closed U.S. 1.</p>"
            "<p>Drivers should avoid the area.</p>"
        ),
    }

    result = adapter.convert(entry, source="WPTV")

    assert result.body == (
        "A crash closed U.S. 1. Drivers should avoid the area."
    )


def test_missing_date_uses_supplied_default():
    default_time = datetime(
        2026,
        7,
        21,
        12,
        0,
        tzinfo=timezone.utc,
    )

    adapter = RSSArticleAdapter(default_published_at=default_time)

    entry = {
        "id": "undated-story",
        "title": "Undated story",
        "link": "https://example.com/undated",
        "summary": "This story did not include a publication date.",
    }

    result = adapter.convert(entry, source="WPTV")

    assert result.published_at == default_time