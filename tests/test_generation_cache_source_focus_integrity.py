from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

from scripts.sanitize_generation_cache import (
    CACHE_INTEGRITY_VERSION,
    sanitize_cache_file,
    sanitize_cache_payload,
)


INVALID_URL = (
    "https://www.wpbf.com/article/florida-sharks-caught-on-video-off-shore"
    "martin-county-jupiter/73324831"
)


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


def _contaminated_item():
    return {
        "headline": (
            "Martin County commissioners delay decision on shark fishing rules "
            "after state order"
        ),
        "body": (
            "Martin County commissioners postponed a decision on shark fishing "
            "rules after state officials ordered the county to align its ordinance."
        ),
        "source_index": 1,
        "source_url": INVALID_URL,
        "link": INVALID_URL,
        "source_title": (
            "Sharks caught on video off shore in Martin County, Jupiter - WPBF"
        ),
        "article_text": (
            "Two sharks were spotted along the Atlantic Ocean shore. A Jensen Beach "
            "resident filmed fishermen struggling with a hooked shark at Normandy "
            "Beach on Hutchinson Island. The fishermen released the shark. A separate "
            "hammerhead shark was found dead near Jupiter Beach later that day. "
            "Wildlife officers removed the animal after video was submitted to WPBF. "
            "The report focused on the sightings and the videos recorded by witnesses."
        ),
    }


def test_sanitizer_removes_known_restored_source_focus_contamination():
    payload = {
        "schema_version": 1,
        "categories": {
            "bad": {
                "value": {
                    "data": {
                        "hero": _contaminated_item(),
                        "cards": [],
                    }
                }
            },
            "good": {
                "value": {
                    "data": {
                        "hero": {
                            "headline": "Port St. Lucie council approves road project",
                            "source_url": "https://example.com/road-project",
                        },
                        "cards": [],
                    }
                }
            },
        },
    }

    sanitized, result = sanitize_cache_payload(payload)

    assert result.removed_category_keys == ("bad",)
    assert "bad" not in sanitized["categories"]
    assert "good" in sanitized["categories"]
    assert sanitized["cache_integrity_version"] == CACHE_INTEGRITY_VERSION


def test_sanitizer_is_idempotent_and_writes_atomically(tmp_path: Path):
    path = tmp_path / "generation-cache.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "categories": {
                    "bad": {"value": {"data": {"hero": _contaminated_item(), "cards": []}}}
                },
            }
        ),
        encoding="utf-8",
    )

    first = sanitize_cache_file(path)
    second = sanitize_cache_file(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert first.removed_category_keys == ("bad",)
    assert second.changed is False
    assert payload["categories"] == {}
    assert payload["cache_integrity_version"] == CACHE_INTEGRITY_VERSION
    assert not path.with_suffix(".json.tmp").exists()


def test_persistent_cache_sanitizes_restored_file_on_load(tmp_path: Path):
    generate = _load_generate_module()
    path = tmp_path / "generation-cache.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": generate.GENERATION_CACHE_SCHEMA_VERSION,
                "source_text": {},
                "source_resolutions": {},
                "classifications": {},
                "categories": {
                    "bad": {"value": {"data": {"hero": _contaminated_item(), "cards": []}}}
                },
                "hero_enhancements": {},
                "card_enhancements": {},
            }
        ),
        encoding="utf-8",
    )

    cache = generate.PersistentGenerationCache(path)

    assert cache.get("categories", "bad") is generate._CACHE_MISS
    assert cache.dirty is True
    cache.save()
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["categories"] == {}
    assert persisted["cache_integrity_version"] == CACHE_INTEGRITY_VERSION


def test_cached_output_is_revalidated_against_current_source_row():
    generate = _load_generate_module()
    cached_item = _contaminated_item()
    # Simulate a legacy cache row whose embedded source fields were stale or absent.
    cached_item.pop("source_title")
    cached_item.pop("article_text")
    current_sources = [
        {
            "title": "Sharks caught on video off shore in Martin County, Jupiter - WPBF",
            "link": INVALID_URL,
            "article_text": _contaminated_item()["article_text"],
            "summary": "Two shark sightings were captured on video.",
        }
    ]

    source = generate._cached_source_for_generated_item(cached_item, current_sources)
    diagnostics = generate._article_framing_diagnostics(cached_item, source)

    assert source is current_sources[0]
    assert diagnostics["passed"] is False
    assert "generated_copy_drifted_from_source_focus" in diagnostics["missing"]


def test_category_cache_contract_version_invalidates_pre_guard_keys():
    generate = _load_generate_module()
    assert generate.CATEGORY_GENERATION_PROMPT_VERSION == (
        "v1.13.7.2-full-article-parity"
    )


def test_cached_source_resolution_prefers_exact_url_over_stale_source_index():
    generate = _load_generate_module()
    wflx_url = "https://www.wflx.com/2026/08/27/hit-and-run-suspect-arrested-after-manhunt-through-palm-city-swamps-brush"
    wpbf_url = "https://www.wpbf.com/article/florida-drones-swamp-crash-deputy-police/73555828"
    cached_item = {
        "headline": "Man arrested after hit-and-run crash, two-hour manhunt through Palm City swamp",
        "source_index": 1,
        "source_url": wflx_url,
        "link": wflx_url,
    }
    current_sources = [
        {
            "title": "'Trying to swim and get away from those drones': Martin County uses multiple drones to catch suspect - WPBF",
            "link": wpbf_url,
            "article_text": "Martin County deputies used multiple drones to locate a suspect underwater in a swamp.",
        },
        {
            "title": "Hit-and-run suspect arrested after manhunt through Palm City swamps and brush - WFLX",
            "link": wflx_url,
            "article_text": "Likenson Daceus led deputies through dense woods and swamp after a hit-and-run crash in Palm City.",
        },
    ]

    source = generate._cached_source_for_generated_item(cached_item, current_sources)
    probe = generate._cached_item_authority_probe(dict(cached_item), current_sources)

    assert source is current_sources[1]
    assert probe["source_url"] == wflx_url
    assert probe["source_title"].endswith("- WFLX")
    assert "multiple drones" not in probe["article_text"]


def test_category_cache_key_separates_promoted_editor_writer_architecture(monkeypatch):
    generate = _load_generate_module()
    source = {
        "title": "Palm City source",
        "link": "https://example.com/palm-city",
        "published": "Thu, 03 Sep 2026 12:00:00 -0400",
        "source_type": "publisher",
        "source_quality": "full",
        "hero_eligible": "yes",
        "category_match_score": 9,
        "article_text": "Palm City source body",
    }
    live_key = generate._category_generation_cache_key("martin", [source])
    monkeypatch.setattr(generate, "ASSIGNMENT_EDITOR_LIVE_ENABLED", False)
    legacy_key = generate._category_generation_cache_key("martin", [source])
    assert live_key != legacy_key
