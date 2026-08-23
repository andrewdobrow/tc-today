from __future__ import annotations

import importlib
import os
import sys
import types


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_hometown_is_removed_from_live_full_text_and_google_recovery_allowlists():
    generate = _load_generate_module()
    assert "hometownnewstc.com" not in generate.FULL_TEXT_DOMAINS
    assert "hometown news" not in generate.TRUSTED_AGGREGATOR_PUBLISHERS
    assert "hometownnewstc.com" in generate.EXCLUDED_SOURCE_DOMAINS


def test_direct_hometown_entry_is_rejected_by_source_policy():
    generate = _load_generate_module()
    entry = {
        "title": "Indian River County creates Attainable Housing Trust to support development",
        "link": "https://www.hometownnewstc.com/news/indian_river/attainable-housing-trust/article_example.html",
        "source": {"title": "Hometown News", "href": "https://www.hometownnewstc.com"},
    }

    assert generate._is_excluded_source_entry(
        entry,
        title=entry["title"],
        link=entry["link"],
    ) is True


def test_google_news_hometown_wrapper_is_rejected_without_resolving_publisher_url():
    generate = _load_generate_module()
    entry = {
        "title": "Martin County deputy stops $600,000 gold bar scam targeting senior - Hometown News",
        "link": "https://news.google.com/rss/articles/CBMi-hometown-stale?oc=5",
        "source": {"title": "Hometown News Treasure Coast", "href": "https://www.hometownnewstc.com"},
    }

    assert generate._is_excluded_source_entry(
        entry,
        title=entry["title"],
        link=entry["link"],
    ) is True


def test_hometown_is_filtered_before_title_dedupe_so_fresher_duplicate_title_can_survive(monkeypatch):
    generate = _load_generate_module()
    shared_title = "Indian River County creates Attainable Housing Trust to support development"
    hometown = {
        "title": shared_title,
        "summary": "A stale republication of an older local government story.",
        "link": "https://www.hometownnewstc.com/news/indian_river/attainable-housing-trust/article_example.html",
        "published": "Sat, 22 Aug 2026 21:00:00 GMT",
        "source": {"title": "Hometown News", "href": "https://www.hometownnewstc.com"},
    }
    fresher_legitimate_source = {
        "title": shared_title,
        "summary": "Fresh reporting from another publisher on the same headline.",
        "link": "https://example.com/fresh-attainable-housing-trust",
        "published": "Sat, 22 Aug 2026 20:59:00 GMT",
        "source": {"title": "Example Local", "href": "https://example.com"},
    }

    monkeypatch.setattr(
        generate.feedparser,
        "parse",
        lambda *args, **kwargs: types.SimpleNamespace(entries=[hometown, fresher_legitimate_source]),
    )

    rows = generate.fetch_headlines(["https://example.test/rss"], limit=10)

    assert len(rows) == 1
    assert rows[0]["link"] == fresher_legitimate_source["link"]
    assert rows[0]["title"] == shared_title


def test_hometown_reference_in_normal_headline_text_is_not_blocked_without_publisher_identity():
    generate = _load_generate_module()
    entry = {
        "title": "Local museum opens Hometown News exhibit",
        "link": "https://example.com/local-museum-exhibit",
        "source": {"title": "Example Local", "href": "https://example.com"},
    }

    assert generate._is_excluded_source_entry(
        entry,
        title=entry["title"],
        link=entry["link"],
    ) is False
