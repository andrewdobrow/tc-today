from __future__ import annotations

import importlib
import json
import os
import sys
import types


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


def test_recurring_custom_edition_rebinds_to_new_exact_payload_slug(tmp_path):
    generate = _load_generate_module()
    body = "Full manual traffic report body with all closures and detours."
    body_hash = generate._custom_body_hash(body)
    old_slug = "2026-07-10-traffic-report-july-12-17"
    new_slug = "2026-07-24-traffic-report-july-26-31"
    (tmp_path / "archive.json").write_text(json.dumps([
        {
            "slug": old_slug,
            "headline": "Old traffic report",
            "is_custom": True,
            "exclude_from_live_recovery": True,
            "identity_quarantine_reason": "recurring_custom_edition_superseded",
        },
        {
            "slug": new_slug,
            "headline": "Treasure Coast Traffic Report: I-95 Ramp Closures and Road Work Planned July 26-31",
            "category_key": "florida",
            "is_custom": True,
            "authoritative_custom": True,
            "custom_body_hash": body_hash,
            "custom_series_key": "traffic-report",
            "custom_edition_key": "2026-07-26|2026-07-31",
            "editorial_story_id": "custom:test",
        },
    ]), encoding="utf-8")
    item = {
        "headline": "Treasure Coast Traffic Report: I-95 Ramp Closures and Road Work Planned July 26-31",
        "body": body,
        "is_custom": True,
        "authoritative_custom": True,
        "custom_body_hash": body_hash,
        "custom_series_key": "traffic-report",
        "custom_edition_key": "2026-07-26|2026-07-31",
        "_archived_slug": old_slug,
        "link": f"{generate.SITE_URL}/articles/{old_slug}.html",
    }
    categories = [{"category_key": "florida", "hero": item, "cards": []}]
    rebound = generate._rebind_current_custom_editions_to_archive(categories, None, tmp_path)
    assert len(rebound) == 1
    assert item["_archived_slug"] == new_slug
    assert item["link"].endswith(f"/articles/{new_slug}.html")
    assert item["editorial_story_id"] == "custom:test"


def test_publication_receipt_disambiguates_legacy_and_new_rows_with_same_payload(tmp_path):
    generate = _load_generate_module()
    body = "Full manual traffic report body with all closures and detours."
    body_hash = generate._custom_body_hash(body)
    old_slug = "2026-07-10-treasure-coast-traffic-report-july-12-17"
    new_slug = "2026-07-25-treasure-coast-traffic-report-july-26-31"
    story_id = "custom:new-edition"
    (tmp_path / "archive.json").write_text(json.dumps([
        {
            "slug": old_slug,
            "headline": "Treasure Coast Traffic Report: I-95 Ramp Closures and Road Work Planned July 26-31",
            "category_key": "florida",
            "is_custom": True,
            "authoritative_custom": True,
            "custom_body_hash": body_hash,
            "custom_series_key": "treasure-coast-traffic-report",
            "custom_edition_key": "july-26-31",
            "editorial_story_id": "custom:legacy",
        },
        {
            "slug": new_slug,
            "headline": "Treasure Coast Traffic Report: I-95 Ramp Closures and Road Work Planned July 26-31",
            "category_key": "florida",
            "is_custom": True,
            "authoritative_custom": True,
            "custom_body_hash": body_hash,
            "custom_series_key": "treasure-coast-traffic-report",
            "custom_edition_key": "july-26-31",
            "editorial_story_id": story_id,
        },
    ]), encoding="utf-8")
    item = {
        "headline": "Treasure Coast Traffic Report: I-95 Ramp Closures and Road Work Planned July 26-31",
        "body": body,
        "category": "florida",
        "category_key": "florida",
        "is_custom": True,
        "authoritative_custom": True,
        "unique_slug": True,
        "custom_body_hash": body_hash,
        "custom_series_key": "treasure-coast-traffic-report",
        "custom_edition_key": "july-26-31",
        "_archived_slug": old_slug,
        "link": f"{generate.SITE_URL}/articles/{old_slug}.html",
    }
    generate.CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS = [
        {
            "headline": item["headline"],
            "custom_body_hash": body_hash,
            "custom_series_key": "treasure-coast-traffic-report",
            "custom_edition_key": "july-26-31",
            "slug": old_slug,
            "editorial_story_id": "custom:legacy",
            "category_key": "florida",
            "action": "updated",
            "unique_slug": False,
            "series_repair": False,
        },
        {
            "headline": item["headline"],
            "custom_body_hash": body_hash,
            "custom_series_key": "treasure-coast-traffic-report",
            "custom_edition_key": "july-26-31",
            "slug": new_slug,
            "editorial_story_id": story_id,
            "category_key": "florida",
            "action": "created",
            "unique_slug": True,
            "series_repair": True,
        },
    ]
    categories = [{"category_key": "florida", "hero": item, "cards": []}]
    rebound = generate._rebind_current_custom_editions_to_archive(categories, None, tmp_path)
    assert len(rebound) == 1
    assert rebound[0]["match_basis"] == "publication_receipt"
    assert item["_archived_slug"] == new_slug
    assert item["editorial_story_id"] == story_id


def test_archive_writer_publication_receipt_updates_rendered_custom_object():
    generate = _load_generate_module()
    generate.CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS = []
    body = "Complete editor-authored article body."
    item = {
        "headline": "Weekly custom report July 26-31",
        "body": body,
        "category": "florida",
        "is_custom": True,
        "authoritative_custom": True,
        "unique_slug": True,
        "custom_body_hash": generate._custom_body_hash(body),
    }
    receipt = generate._record_current_custom_publication(
        item,
        "2026-07-25-weekly-custom-report-july-26-31",
        "custom:receipt",
        "florida",
        "created",
    )
    assert receipt["unique_slug"] is True
    assert item["_archived_slug"] == "2026-07-25-weekly-custom-report-july-26-31"
    assert item["editorial_story_id"] == "custom:receipt"
    assert generate.CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS[-1]["slug"] == item["_archived_slug"]
