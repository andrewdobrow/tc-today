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


def test_custom_live_clone_and_queue_copy_coalesce_by_exact_payload_not_stale_story_id():
    generate = _load_generate_module()
    body = "Complete weekly traffic report body."
    body_hash = generate._custom_body_hash(body)
    live = {
        "headline": "Treasure Coast Traffic Report: I-95 Ramp Closures July 26-31",
        "body": body,
        "is_custom": True,
        "authoritative_custom": True,
        "unique_slug": True,
        "custom_body_hash": body_hash,
        "custom_series_key": "treasure-coast-traffic-report",
        "custom_edition_key": "july-26-31",
        "editorial_story_id": "custom:legacy-edition",
        "_editorial_story_id": "custom:legacy-edition",
        "_archived_slug": "2026-07-10-traffic-report-july-12-17",
        "slug": "2026-07-10-traffic-report-july-12-17",
    }
    queue = {
        "headline": live["headline"],
        "body": body,
        "is_custom": True,
        "authoritative_custom": True,
        "unique_slug": True,
        "custom_body_hash": body_hash,
        "custom_series_key": "treasure-coast-traffic-report",
        "custom_edition_key": "july-26-31",
    }
    assert generate._publication_coalesce_key(live, None) == generate._publication_coalesce_key(queue, None)


def test_runtime_bound_legacy_slug_is_not_treated_as_editor_requested_unique_slug():
    generate = _load_generate_module()
    item = {
        "headline": "Treasure Coast Traffic Report: I-95 Ramp Closures July 26-31",
        "body": "Complete manual report.",
        "is_custom": True,
        "authoritative_custom": True,
        "unique_slug": True,
        "_custom_requested_slug": "",
        "_custom_requested_replace_slug": "",
        "_archived_slug": "2026-07-10-traffic-report-july-12-17",
        "slug": "2026-07-10-traffic-report-july-12-17",
    }
    existing, forced_slug, story_id = generate._resolve_custom_publication_target(
        item, [], None, item["headline"]
    )
    assert existing is None
    assert forced_slug is None
    assert story_id.startswith("custom:")


def test_direct_publication_binding_updates_all_live_clones_and_survives_generic_rebind(tmp_path):
    generate = _load_generate_module()
    body = "Complete weekly traffic report with every closure and detour."
    body_hash = generate._custom_body_hash(body)
    old_slug = "2026-07-10-traffic-report-july-12-17"
    new_slug = "2026-07-25-traffic-report-july-26-31"
    story_id = "custom:new-edition"
    queue = {
        "headline": "Treasure Coast Traffic Report: I-95 Ramp Closures July 26-31",
        "body": body,
        "category": "florida",
        "category_key": "florida",
        "is_custom": True,
        "authoritative_custom": True,
        "unique_slug": True,
        "custom_body_hash": body_hash,
        "custom_series_key": "treasure-coast-traffic-report",
        "custom_edition_key": "july-26-31",
    }
    live_one = dict(queue, _archived_slug=old_slug, slug=old_slug,
                    link=f"{generate.SITE_URL}/articles/{old_slug}.html")
    live_two = dict(queue, _archived_slug=old_slug, slug=old_slug,
                    link=f"{generate.SITE_URL}/articles/{old_slug}.html")
    categories = [{"category_key": "florida", "hero": live_one, "cards": [live_two]}]
    rows = generate._bind_custom_publication_directly_to_live(
        categories, None, queue, new_slug, story_id, "florida"
    )
    assert len(rows) == 2
    for item in (live_one, live_two):
        assert item["_current_custom_publication_slug"] == new_slug
        assert item["_archived_slug"] == new_slug
        assert item["editorial_story_id"] == story_id

    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / f"{old_slug}.html").write_text("old", encoding="utf-8")
    (articles / f"{new_slug}.html").write_text("new", encoding="utf-8")
    archive = [
        {
            "slug": old_slug,
            "headline": queue["headline"],
            "is_custom": True,
            "authoritative_custom": True,
            "editorial_story_id": "custom:legacy-edition",
            "custom_body_hash": body_hash,
        },
        {
            "slug": new_slug,
            "headline": queue["headline"],
            "is_custom": True,
            "authoritative_custom": True,
            "editorial_story_id": story_id,
            "custom_body_hash": body_hash,
            "category_key": "florida",
        },
    ]
    generate._rebind_live_items_to_published_archive(
        categories, archive, current_customs=[queue], articles_dir=articles
    )
    for item in (live_one, live_two):
        assert item["_archived_slug"] == new_slug
        assert item["editorial_story_id"] == story_id
