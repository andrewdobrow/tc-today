from __future__ import annotations

import importlib
import json
import os
import sys
import types


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


def test_publication_receipt_rebinds_exact_headline(tmp_path):
    g = _load_generate()
    headline = "Exact Manual Headline"
    slug = "2026-07-25-exact-manual-headline"
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": slug, "headline": headline, "category_key": "florida",
        "is_custom": True, "authoritative_custom": True, "editorial_story_id": "custom:one"
    }]), encoding="utf-8")
    item = {"headline": headline, "body": "new body", "category": "florida", "is_custom": True, "authoritative_custom": True}
    g.CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS = [{
        "headline": headline, "slug": slug, "editorial_story_id": "custom:one",
        "category_key": "florida", "action": "updated"
    }]
    categories = [{"category_key": "florida", "hero": item, "cards": []}]
    rows = g._rebind_current_custom_editions_to_archive(categories, None, tmp_path)
    assert len(rows) == 1
    assert rows[0]["match_basis"] == "exact_headline_publication_receipt"
    assert item["_archived_slug"] == slug


def test_different_headline_is_never_rebound_to_old_custom_page(tmp_path):
    g = _load_generate()
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": "old", "headline": "Old Headline", "is_custom": True, "editorial_story_id": "custom:old"
    }]), encoding="utf-8")
    item = {"headline": "New Headline", "body": "body", "is_custom": True, "authoritative_custom": True}
    categories = [{"category_key": "florida", "hero": item, "cards": []}]
    g.CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS = []
    rows = g._rebind_current_custom_editions_to_archive(categories, None, tmp_path)
    assert rows == []
    report = json.loads((tmp_path / "data" / "custom-post-publication-rebind.json").read_text())
    assert report["unresolved_count"] == 1


def test_direct_publication_binding_updates_exact_headline_clones():
    g = _load_generate()
    queue = {"headline": "Exact Manual Headline", "body": "changed", "is_custom": True, "authoritative_custom": True}
    clone = dict(queue, _archived_slug="old")
    other = {"headline": "Different Manual Headline", "body": "changed", "is_custom": True, "authoritative_custom": True, "_archived_slug": "different"}
    categories = [{"category_key": "florida", "hero": clone, "cards": [other]}]
    rows = g._bind_custom_publication_directly_to_live(categories, None, queue, "new", "custom:new", "florida")
    assert len(rows) == 1
    assert clone["_archived_slug"] == "new"
    assert other["_archived_slug"] == "different"


def test_custom_coalesce_key_is_exact_headline_not_body():
    g = _load_generate()
    a = {"headline": "Same Headline", "body": "first", "is_custom": True}
    b = {"headline": "Same Headline", "body": "second", "is_custom": True}
    c = {"headline": "Same headline", "body": "first", "is_custom": True}
    assert g._publication_coalesce_key(a) == g._publication_coalesce_key(b)
    assert g._publication_coalesce_key(a) != g._publication_coalesce_key(c)
