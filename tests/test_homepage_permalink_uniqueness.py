from __future__ import annotations

import importlib
import json
import os
import sys
import types

import pytest


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser

    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(
                        RuntimeError("unexpected model call")
                    )
                )

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _resolver(card):
    slug = card.get("slug")
    return f"https://treasurecoast.today/articles/{slug}.html" if slug else None


def test_cross_category_copies_are_deduped_by_permalink():
    generate = _load_generate_module()
    local_copy = {
        "headline": "60 St. Lucie County teens complete summer internship program",
        "slug": "summer-internship",
        "cat_key": "local_gov",
        "cat_label": "Local Government",
        "urgency_score": 6,
    }
    county_copy = {
        **local_copy,
        "cat_key": "st_lucie",
        "cat_label": "St. Lucie County",
    }
    crime_copy = {
        "headline": "Miami man arrested for stealing GPS units from boats",
        "slug": "boat-gps-arrest",
        "cat_key": "crime",
        "cat_label": "Crime & Safety",
        "urgency_score": 7,
    }
    martin_copy = {
        **crime_copy,
        "cat_key": "martin",
        "cat_label": "Martin County",
    }

    kept, report = generate._dedupe_homepage_cards_by_permalink(
        [local_copy, county_copy, crime_copy, martin_copy],
        _resolver,
        topnews_ids={id(local_copy), id(crime_copy)},
    )

    assert kept == [local_copy, crime_copy]
    assert report["resolved_unique_permalink_count"] == 2
    assert report["removed_count"] == 2
    assert {row["category_key"] for row in report["removed"]} == {
        "st_lucie",
        "martin",
    }


def test_pinned_copy_wins_permalink_group():
    generate = _load_generate_module()
    ordinary = {
        "headline": "Same article",
        "slug": "same-article",
        "cat_key": "business",
        "urgency_score": 8,
    }
    pinned = {
        "headline": "Same article",
        "slug": "same-article",
        "cat_key": "martin",
        "urgency_score": 3,
        "pin_position": 2,
    }

    kept, report = generate._dedupe_homepage_cards_by_permalink(
        [ordinary, pinned],
        _resolver,
        topnews_ids={id(ordinary)},
    )

    assert kept == [pinned]
    assert report["removed_count"] == 1
    assert report["removed"][0]["reason"] == "duplicate_permalink_replaced_by_preferred_placement"


def test_card_matching_front_page_hero_permalink_is_removed():
    generate = _load_generate_module()
    card = {
        "headline": "Hero duplicated as a card",
        "slug": "hero-story",
        "cat_key": "crime",
    }

    kept, report = generate._dedupe_homepage_cards_by_permalink(
        [card],
        _resolver,
        hero_permalink="https://treasurecoast.today/articles/hero-story.html",
    )

    assert kept == []
    assert report["removed_count"] == 1
    assert report["removed"][0]["reason"] == "duplicates_front_page_hero"


def _homepage_html(card_links):
    cards = "".join(
        f'<a href="{href}" class="grid-card fade-in" data-cat="all"></a>'
        for href in card_links
    )
    return (
        '<section class="hero hero-v3" data-cat-hero="all">'
        '<a class="hero-v3-link" href="https://treasurecoast.today/articles/hero.html"></a>'
        "</section>"
        + cards
    )


def test_rendered_homepage_permalink_contract_passes_for_unique_links(tmp_path):
    generate = _load_generate_module()
    html = _homepage_html([
        "https://treasurecoast.today/articles/one.html",
        "https://treasurecoast.today/articles/two.html",
    ])

    report = generate.validate_homepage_permalink_uniqueness(html, tmp_path)

    assert report["passed"] is True
    assert report["checked_visible_article_links"] == 3
    persisted = json.loads(
        (tmp_path / "data" / "homepage-permalink-contract.json").read_text()
    )
    assert persisted["duplicate_count"] == 0


def test_rendered_homepage_permalink_contract_fails_closed_on_duplicate(tmp_path):
    generate = _load_generate_module()
    html = _homepage_html([
        "https://treasurecoast.today/articles/one.html",
        "https://treasurecoast.today/articles/one.html?utm_source=duplicate#card",
    ])

    with pytest.raises(RuntimeError, match="Homepage permalink contract FAILED"):
        generate.validate_homepage_permalink_uniqueness(html, tmp_path)

    persisted = json.loads(
        (tmp_path / "data" / "homepage-permalink-contract.json").read_text()
    )
    assert persisted["passed"] is False
    assert persisted["duplicate_count"] == 1
