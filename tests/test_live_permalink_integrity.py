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
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _category():
    return {
        "category_key": "crime",
        "hero": {
            "headline": "Stuart woman arrested in animal hoarding case",
            "link": "https://example.com/source-story",
        },
        "cards": [],
    }


def test_live_permalink_integrity_passes_for_resolved_hero(tmp_path):
    generate = _load_generate_module()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    slug = "2026-07-24-stuart-woman-arrested"
    (tmp_path / "articles" / f"{slug}.html").write_text("<html></html>")
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": slug,
        "headline": "Stuart woman arrested in animal hoarding case",
        "source_url": "https://example.com/source-story",
        "date": "2026-07-24",
    }]))

    report = generate.validate_live_permalink_integrity([_category()], tmp_path)

    assert report["passed"] is True
    assert report["checked_hero_placements"] == 1
    saved = json.loads((tmp_path / "data" / "live-permalink-integrity.json").read_text())
    assert saved["passed"] is True


def test_live_permalink_integrity_blocks_missing_article_page(tmp_path):
    generate = _load_generate_module()
    (tmp_path / "articles").mkdir()
    (tmp_path / "archive.json").write_text("[]")

    with pytest.raises(RuntimeError, match="Live permalink integrity failed"):
        generate.validate_live_permalink_integrity([_category()], tmp_path)

    report = json.loads((tmp_path / "data" / "live-permalink-integrity.json").read_text())
    assert report["passed"] is False
    assert report["failures"][0]["category_key"] == "crime"


def test_live_permalink_integrity_ignores_section_placeholders(tmp_path):
    generate = _load_generate_module()
    (tmp_path / "archive.json").write_text("[]")
    category = _category()
    category["hero"]["_section_placeholder"] = True

    report = generate.validate_live_permalink_integrity([category], tmp_path)

    assert report["passed"] is True
    assert report["checked_hero_placements"] == 0
