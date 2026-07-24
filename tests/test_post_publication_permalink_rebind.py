from __future__ import annotations

import importlib
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
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_live_item_rebind_prefers_persistent_story_id_after_archive_consolidation(tmp_path):
    generate = _load_generate_module()
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    canonical_slug = "2026-07-24-treasure-coast-home-prices"
    (articles_dir / f"{canonical_slug}.html").write_text("<html></html>", encoding="utf-8")

    archive = [{
        "slug": canonical_slug,
        "headline": "Treasure Coast home prices rise",
        "editorial_story_id": "story_home_prices",
    }]
    category = {
        "category_key": "martin",
        "hero": {
            "headline": "Martin County median home price rises to $655,000",
            "link": "https://example.com/removed-duplicate-source",
            "_editorial_story_id": "story_home_prices",
        },
        "cards": [],
    }

    rebound = generate._rebind_live_items_to_published_archive(
        [category], archive, articles_dir=articles_dir
    )

    assert rebound == 1
    assert category["hero"]["_archived_slug"] == canonical_slug
    assert category["hero"]["link"].endswith(f"/articles/{canonical_slug}.html")


def test_main_rebinds_after_publication_identity_and_before_integrity_gate():
    text = Path("scripts/generate.py").read_text(encoding="utf-8")
    write_position = text.index(
        "_current_regression_report = write_archives(all_categories, top_cat)"
    )
    post_rebind_position = text.index(
        "_post_publication_rebound = _rebind_live_items_to_published_archive",
        write_position,
    )
    integrity_position = text.index(
        "validate_live_permalink_integrity(all_categories, top_cat, OUTPUT_DIR)",
        post_rebind_position,
    )
    assert write_position < post_rebind_position < integrity_position
