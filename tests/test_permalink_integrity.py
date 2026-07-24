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

        class _Messages:
            def create(self, *args, **kwargs):
                raise RuntimeError("AI calls are disabled in permalink tests")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = _Messages()

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_protected_feed_hero_rebinds_to_custom_article():
    generate = _load_generate_module()
    canonical_slug = (
        "2026-07-18-st-lucie-county-fire-district-says-3-fired-2-suspended-"
        "after-hazing-investigatio"
    )
    custom = {
        "slug": canonical_slug,
        "headline": "St. Lucie County Fire District says 3 fired, 2 suspended after hazing investigation",
        "body": "Original custom TCT reporting.",
        "teaser": "Original custom TCT reporting.",
        "is_custom": True,
        "category": "st_lucie",
    }
    entry = {
        "slug": canonical_slug,
        "headline": custom["headline"],
        "is_custom": True,
        "authoritative_custom": True,
        "custom_fingerprint": generate._custom_story_fingerprint(
            custom["headline"], custom["teaser"]
        ),
    }
    feed_hero = {
        "headline": "New depositions reveal why a St. Lucie County firefighter turned in alleged hazing videos",
        "body": "A later feed article.",
        "_is_hero_copy": True,
        "urgency_score": 8,
    }

    assert generate._bind_live_item_to_archive(
        feed_hero, entry, [custom], replace_with_custom=True
    )
    assert feed_hero["headline"] == custom["headline"]
    assert feed_hero["_archived_slug"] == canonical_slug
    assert feed_hero["_is_hero_copy"] is True
    assert feed_hero["urgency_score"] == 8


def test_resolver_never_fabricates_nonexistent_headline_slug(tmp_path):
    generate = _load_generate_module()
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    item = {
        "headline": "New depositions reveal why a firefighter turned in videos",
        "link": "https://example.com/new-depositions",
    }

    assert generate._resolve_published_slug(item, [], articles_dir) == ""


def test_bound_canonical_slug_resolves_only_when_file_exists(tmp_path):
    generate = _load_generate_module()
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    slug = "2026-07-18-existing-custom-firefighter-story"
    item = {"headline": "Updated feed headline", "_archived_slug": slug}

    assert generate._resolve_published_slug(item, [], articles_dir) == ""
    (articles_dir / f"{slug}.html").write_text("<html></html>", encoding="utf-8")
    assert generate._resolve_published_slug(item, [], articles_dir) == slug


def test_live_permalink_integrity_passes_for_rebound_hero(tmp_path):
    generate = _load_generate_module()
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    slug = "2026-07-18-existing-custom-firefighter-story"
    (articles_dir / f"{slug}.html").write_text("<html></html>", encoding="utf-8")
    archive = [{"slug": slug, "headline": "Canonical firefighter story"}]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")

    hero = {"headline": "Canonical firefighter story", "_archived_slug": slug}
    category = {"category_key": "st_lucie", "hero": hero, "cards": []}
    report = generate.validate_live_permalink_integrity(
        [category], category, tmp_path
    )

    assert report["status"] == "passed"
    assert report["missing_count"] == 0
    saved = json.loads((tmp_path / "data" / "permalink-integrity.json").read_text())
    assert saved["status"] == "passed"


def test_live_permalink_integrity_stops_missing_hero(tmp_path):
    generate = _load_generate_module()
    (tmp_path / "articles").mkdir()
    (tmp_path / "archive.json").write_text("[]", encoding="utf-8")
    hero = {"headline": "Unpublished hero with no article page"}
    category = {"category_key": "local_gov", "hero": hero, "cards": []}

    with pytest.raises(RuntimeError, match="Live permalink integrity FAILED"):
        generate.validate_live_permalink_integrity([category], category, tmp_path)

    saved = json.loads((tmp_path / "data" / "permalink-integrity.json").read_text())
    assert saved["status"] == "failed"
    assert saved["missing_count"] == 1
