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
        "v1.13.0.3-source-focus-cache-integrity"
    )
