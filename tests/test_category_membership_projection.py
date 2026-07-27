from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path


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


def _p1_entry():
    return {
        "slug": "2026-07-22-private-racetrack-resort-p1-motor-club-under-construction-on-650-acres-in-st-luc",
        "headline": "Private racetrack resort community breaks ground in St. Lucie County on 650 acres",
        "teaser": "P1 Motor Club is under construction in St. Lucie County.",
        "category_key": "business",
        "category_label": "Business & Development",
        "feed_url": "https://www.wptv.com/news/region-st-lucie-county.rss",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-st-lucie-county/p1-motor-club",
    }


def test_business_story_retains_st_lucie_membership():
    generate = _load_generate_module()
    memberships = generate._item_category_memberships(_p1_entry(), "business")
    assert "business" in memberships
    assert "st_lucie" in memberships


def test_archive_backfill_persists_secondary_county_membership(tmp_path: Path):
    generate = _load_generate_module()
    archive, report = generate._backfill_archive_category_memberships([_p1_entry()], tmp_path)
    assert archive[0]["category_keys"] == ["business", "st_lucie"]
    assert archive[0]["county_keys"] == ["st_lucie"]
    assert report["passed"] is True
    persisted = json.loads((tmp_path / "data" / "category-membership-report.json").read_text())
    assert persisted["records_backfilled"] == 1


def test_homepage_permalink_dedupe_unions_category_memberships():
    generate = _load_generate_module()
    business = {**_p1_entry(), "cat_key": "business", "urgency_score": 7}
    county = {**_p1_entry(), "cat_key": "st_lucie", "category_key": "st_lucie", "urgency_score": 5}

    kept, report = generate._dedupe_homepage_cards_by_permalink(
        [business, county],
        lambda card: f"https://treasurecoast.today/articles/{card['slug']}.html",
        topnews_ids={id(business)},
    )

    assert kept == [business]
    assert set(business["category_keys"]) == {"business", "st_lucie"}
    assert report["removed_count"] == 1


def test_frontend_filters_use_multi_category_memberships():
    root = Path(__file__).resolve().parents[1]
    generate_source = (root / "scripts" / "generate.py").read_text(encoding="utf-8")
    main_js = (root / "main.js").read_text(encoding="utf-8")
    assert 'data-cats="{data_cats}"' in generate_source
    assert "card.dataset.cats || card.dataset.cat" in main_js
    assert "memberships.includes(cat)" in main_js
