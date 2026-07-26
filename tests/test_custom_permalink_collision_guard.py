from __future__ import annotations

import importlib
import os
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
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _old_cardinals_custom():
    return {
        "slug": "2026-07-19-cardinals-homer-twice-defeat-st-lucie-mets-7-4",
        "headline": "Cardinals Homer Twice, Defeat St. Lucie Mets 7-4",
        "teaser": "The St. Lucie Mets fell behind early in a loss to Palm Beach.",
        "category_key": "sports",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:old-cardinals-game",
        "ranking_eligible": True,
        "legacy_identity_status": "identified",
    }


def _new_mussels_custom():
    return {
        "headline": "Mets’ Comeback Falls Short in 15-14 Loss to Mighty Mussels",
        "teaser": "Randy Guzman hit two home runs as St. Lucie nearly erased an eight-run deficit.",
        "body": "Complete current game recap. " * 80,
        "category": "sports",
        "category_key": "sports",
        "is_custom": True,
        "authoritative_custom": True,
        "_custom_active_queue": True,
        "_custom_requested_slug": "2026-07-25-st-lucie-mets-comeback-falls-short-15-14-mighty-mussels",
        "slug": "2026-07-25-st-lucie-mets-comeback-falls-short-15-14-mighty-mussels",
    }


def test_new_custom_game_does_not_rebind_to_prior_custom_game(tmp_path):
    g = _load_generate()
    old = _old_cardinals_custom()
    new = _new_mussels_custom()
    # Reproduce the production collision: the persistent registry grouped both
    # recaps under one broader story ID before permalink rebinding.
    new["editorial_story_id"] = old["editorial_story_id"]
    new["_editorial_story_id"] = old["editorial_story_id"]
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / f"{old['slug']}.html").write_text("old game", encoding="utf-8")
    sports = {
        "category_key": "sports",
        "category_label": "Sports",
        "hero": new,
        "cards": [],
    }

    rebound = g._rebind_live_items_to_published_archive(
        [sports], [old], [new], articles
    )

    assert rebound == 0
    assert new["headline"] == "Mets’ Comeback Falls Short in 15-14 Loss to Mighty Mussels"
    assert new["slug"] == "2026-07-25-st-lucie-mets-comeback-falls-short-15-14-mighty-mussels"
    assert new.get("_archived_slug") is None


def test_exact_custom_headline_can_recover_its_existing_permalink(tmp_path):
    g = _load_generate()
    old = _old_cardinals_custom()
    current = {
        "headline": old["headline"],
        "body": "Updated exact-headline copy " * 60,
        "category": "sports",
        "category_key": "sports",
        "is_custom": True,
        "authoritative_custom": True,
        "_custom_active_queue": True,
    }
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / f"{old['slug']}.html").write_text("old game", encoding="utf-8")
    sports = {
        "category_key": "sports",
        "category_label": "Sports",
        "hero": current,
        "cards": [],
    }

    rebound = g._rebind_live_items_to_published_archive(
        [sports], [old], [current], articles
    )

    assert rebound == 1
    assert current["_archived_slug"] == old["slug"]
    assert current["link"].endswith(f"/articles/{old['slug']}.html")


def test_legacy_custom_backfill_never_uses_generic_sports_similarity():
    g = _load_generate()
    old = _old_cardinals_custom()
    old.pop("is_custom")
    old.pop("authoritative_custom")
    new = _new_mussels_custom()

    stamped = g._backfill_active_custom_archive_authority([old], [new])

    assert stamped == 0
    assert old.get("is_custom") is None
    assert old.get("custom_headline_key") is None


def test_new_custom_slug_collision_with_different_archive_headline_fails_closed():
    g = _load_generate()
    old = _old_cardinals_custom()
    new = _new_mussels_custom()
    new["_custom_requested_slug"] = old["slug"]

    with pytest.raises(RuntimeError, match="Custom publication slug collision"):
        g._resolve_custom_publication_target(new, [old], old, new["headline"])


def test_new_custom_explicit_slug_survives_persistent_story_false_match():
    g = _load_generate()
    old = _old_cardinals_custom()
    new = _new_mussels_custom()

    target, forced_slug, story_id = g._resolve_custom_publication_target(
        new, [old], old, new["headline"]
    )

    assert target is None
    assert forced_slug == new["_custom_requested_slug"]
    assert story_id.startswith("custom:")
