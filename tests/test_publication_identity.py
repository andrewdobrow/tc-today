from __future__ import annotations

import importlib
import os
import sys
import types

from tct_engine import build_publication_identity_index


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _registry_payload():
    return {
        "stories": {
            "story_big_taste": {
                "canonical_title": "Big Taste of Martin County returns to support mentoring programs",
                "titles": [
                    "Big Taste of Martin County returns to support Big Brothers Big Sisters mentoring programs",
                    "Big Taste of Martin County returns to support Big Brothers Big Sisters mentoring programs - WPTV",
                ],
                "sources": [
                    "https://www.wptv.com/shining-a-light/big-taste-of-martin-county-returns",
                    "https://news.google.com/rss/articles/BIGTASTE?oc=5",
                ],
                "timeline": [
                    {"url": "https://www.wptv.com/shining-a-light/big-taste-of-martin-county-returns"},
                    {"url": "https://news.google.com/rss/articles/BIGTASTE?oc=5"},
                ],
                "relationship_history": [{"relationship": "new_story"}],
            },
            "story_childcare": {
                "canonical_title": "Fort Pierce mom among thousands struggling with Florida's childcare crisis",
                "titles": [
                    "Fort Pierce mom among thousands struggling with Florida's childcare crisis",
                    "Fort Pierce mom among thousands struggling with Florida's childcare crisis - WPTV",
                ],
                "timeline": [
                    {"url": "https://www.wptv.com/money/consumer/fort-pierce-mom-childcare-crisis"},
                    {"url": "https://news.google.com/rss/articles/CHILDCARE?oc=5"},
                ],
                "relationship_history": [{"relationship": "new_story"}],
            },
            "story_followup": {
                "canonical_title": "Suspect arrested after initial investigation",
                "titles": ["Initial investigation", "Suspect arrested"],
                "timeline": [
                    {"url": "https://example.com/initial"},
                    {"url": "https://example.com/arrest"},
                ],
                "relationship_history": [{"relationship": "follow_up"}],
            },
        }
    }


def test_rewritten_big_taste_headlines_resolve_through_source_story_identity():
    index = build_publication_identity_index(_registry_payload())
    first = {
        "headline": "Big Taste of Martin County returns Oct. 6 to support youth mentoring programs",
        "source_url": "https://www.wptv.com/shining-a-light/big-taste-of-martin-county-returns",
    }
    second = {
        "headline": "Big Taste of Martin County fundraiser set for October 6 at Atlantic Aviation",
        "source_url": "https://news.google.com/rss/articles/BIGTASTE?oc=5",
    }
    assert index.resolve(first) == "story_big_taste"
    assert index.resolve(second) == "story_big_taste"


def test_childcare_rewrites_resolve_to_one_publication_story():
    index = build_publication_identity_index(_registry_payload())
    urls = [
        "https://www.wptv.com/money/consumer/fort-pierce-mom-childcare-crisis",
        "https://news.google.com/rss/articles/CHILDCARE?oc=5",
    ]
    headlines = [
        "Fort Pierce mom leaves nursing job as Florida childcare costs consume 20% of household income",
        "85% of Florida families spend over 7% of income on childcare, Fed study finds",
        "Fort Pierce child care crisis forces mother to leave nursing job",
    ]
    assert {
        index.resolve({"headline": headline, "source_url": urls[i % 2]})
        for i, headline in enumerate(headlines)
    } == {"story_childcare"}


def test_follow_up_story_remains_outside_publication_enforcement():
    index = build_publication_identity_index(_registry_payload())
    assert index.resolve({"source_url": "https://example.com/arrest"}) == ""


def test_archive_reconciliation_creates_redirects_and_keeps_oldest_permalink():
    generate = _load_generate_module()
    index = build_publication_identity_index(_registry_payload())
    archive = [
        {
            "slug": "2026-07-23-big-taste-returns",
            "headline": "Big Taste returns Oct. 6",
            "source_url": "https://www.wptv.com/shining-a-light/big-taste-of-martin-county-returns",
            "first_published": "Wed, 23 Jul 2026 10:00:00 -0400",
            "date": "2026-07-23",
        },
        {
            "slug": "2026-07-23-big-taste-fundraiser",
            "headline": "Big Taste fundraiser set at Atlantic Aviation",
            "source_url": "https://news.google.com/rss/articles/BIGTASTE?oc=5",
            "first_published": "Wed, 23 Jul 2026 11:00:00 -0400",
            "date": "2026-07-23",
        },
    ]
    cleaned, redirects, report = generate._reconcile_archive_publication_identity(archive, index)
    assert [entry["slug"] for entry in cleaned] == ["2026-07-23-big-taste-returns"]
    assert redirects[0]["target_slug"] == "2026-07-23-big-taste-returns"
    assert redirects[0]["source_slug"] == "2026-07-23-big-taste-fundraiser"
    assert report["groups_resolved"] == 1
    assert report["records_removed"] == 1
    assert report["remaining_duplicate_groups"] == 0


def test_custom_permalink_wins_publication_identity_group():
    generate = _load_generate_module()
    index = build_publication_identity_index(_registry_payload())
    archive = [
        {
            "slug": "generated-childcare",
            "headline": "Fort Pierce child care crisis forces mother to leave nursing job",
            "source_url": "https://news.google.com/rss/articles/CHILDCARE?oc=5",
            "first_published": "Wed, 22 Jul 2026 08:00:00 -0400",
        },
        {
            "slug": "custom-childcare",
            "headline": "Fort Pierce mom describes childcare crisis",
            "source_url": "https://www.wptv.com/money/consumer/fort-pierce-mom-childcare-crisis",
            "first_published": "Wed, 22 Jul 2026 09:00:00 -0400",
            "is_custom": True,
            "authoritative_custom": True,
        },
    ]
    cleaned, redirects, _ = generate._reconcile_archive_publication_identity(archive, index)
    assert [entry["slug"] for entry in cleaned] == ["custom-childcare"]
    assert redirects[0]["target_slug"] == "custom-childcare"


def test_known_article_slug_resolves_to_persistent_story_id():
    payload = _registry_payload()
    payload["stories"]["story_big_taste"]["canonical_slug"] = "2026-07-23-big-taste-returns"
    payload["stories"]["story_big_taste"]["article_slugs"] = [
        "2026-07-23-big-taste-returns",
        "2026-07-23-big-taste-fundraiser",
    ]
    index = build_publication_identity_index(payload)
    assert index.resolve({"slug": "2026-07-23-big-taste-returns"}) == "story_big_taste"
    assert index.resolve({"link": "https://treasurecoast.today/articles/2026-07-23-big-taste-fundraiser.html?x=1"}) == "story_big_taste"
