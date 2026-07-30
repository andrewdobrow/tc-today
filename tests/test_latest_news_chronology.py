from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


def _load_generate():
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
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_latest_news_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _entry(slug: str, published: str, *, date: str, lastmod: str = "", urgency: int = 0):
    return {
        "slug": slug,
        "headline": slug.replace("-", " ").title(),
        "teaser": "A complete local article with enough archived content for publication.",
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "date": date,
        "lastmod": lastmod or date,
        "first_published": published,
        "article_word_count": 320,
        "article_paragraph_count": 6,
        "urgency_score": urgency,
        "ranking_eligible": True,
        "publication_id": f"publication:{slug}",
        "canonical_publication_id": f"publication:{slug}",
    }


def test_latest_news_uses_publication_time_not_importance_or_lastmod():
    g = _load_generate()
    old_high_priority = _entry(
        "2026-07-22-old-breaking-story",
        "Wed, 22 Jul 2026 09:00:00 -0400",
        date="2026-07-22",
        lastmod="2026-07-30",
        urgency=10,
    )
    newest = _entry(
        "2026-07-30-new-community-story",
        "Thu, 30 Jul 2026 01:45:00 -0400",
        date="2026-07-30",
        urgency=3,
    )
    middle = _entry(
        "2026-07-29-middle-story",
        "Wed, 29 Jul 2026 21:00:00 -0400",
        date="2026-07-29",
        urgency=7,
    )

    selected = g._select_latest_news_entries(
        [old_high_priority, newest, middle], limit=3
    )

    assert [item["slug"] for item in selected] == [
        newest["slug"],
        middle["slug"],
        old_high_priority["slug"],
    ]


def test_latest_news_selects_five_newest_across_categories():
    g = _load_generate()
    entries = [
        _entry(
            f"2026-07-{day:02d}-story-{day}",
            f"Wed, {day:02d} Jul 2026 12:00:00 -0400",
            date=f"2026-07-{day:02d}",
        )
        for day in range(20, 31)
    ]

    selected = g._select_latest_news_entries(entries, limit=5)

    assert [item["date"] for item in selected] == [
        "2026-07-30",
        "2026-07-29",
        "2026-07-28",
        "2026-07-27",
        "2026-07-26",
    ]


def test_latest_news_deduplicates_only_the_same_canonical_publication():
    g = _load_generate()
    canonical = _entry(
        "2026-07-30-canonical",
        "Thu, 30 Jul 2026 02:00:00 -0400",
        date="2026-07-30",
    )
    duplicate_copy = dict(canonical)
    duplicate_copy["slug"] = "2026-07-30-redirect-source-copy"
    older = _entry(
        "2026-07-29-older",
        "Wed, 29 Jul 2026 22:00:00 -0400",
        date="2026-07-29",
    )

    selected = g._select_latest_news_entries(
        [duplicate_copy, older, canonical], limit=5
    )

    assert len(selected) == 2
    assert selected[0]["canonical_publication_id"] == canonical["canonical_publication_id"]
    assert selected[1]["slug"] == older["slug"]


def test_latest_news_contract_fails_for_importance_order(tmp_path):
    g = _load_generate()
    older = _entry(
        "2026-07-22-old",
        "Wed, 22 Jul 2026 09:00:00 -0400",
        date="2026-07-22",
    )
    newer = _entry(
        "2026-07-30-new",
        "Thu, 30 Jul 2026 01:00:00 -0400",
        date="2026-07-30",
    )

    with pytest.raises(RuntimeError, match="Latest News rail contract FAILED"):
        g._write_latest_news_rail_contract([older, newer], [older, newer], tmp_path)

    report = json.loads(
        (tmp_path / "data" / "latest-news-rail-contract.json").read_text()
    )
    assert report["passed"] is False
    assert report["expected_slugs"] == [newer["slug"], older["slug"]]


def test_renderer_does_not_take_latest_news_from_top_stories_slice():
    source = (
        Path(__file__).parents[1] / "scripts" / "generate.py"
    ).read_text(encoding="utf-8")
    assert "for _latest in all_cards_display[:5]" not in source
    assert "latest_entries = _select_latest_news_entries(archive_for_links, limit=5)" in source
