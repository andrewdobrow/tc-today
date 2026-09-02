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


def test_custom_copy_outranks_generated_copy():
    g = _load_generate()
    custom = ("florida", "Florida", {"headline": "Manual", "body": "manual " * 50, "is_custom": True})
    generated = ("florida", "Florida", {"headline": "Generated", "body": "generated " * 500, "image_url": "https://wptv.com/a.jpg", "_is_hero_copy": True})
    assert g._publication_copy_rank(custom) > g._publication_copy_rank(generated)


def test_only_exact_same_headline_can_update_custom_permalink():
    g = _load_generate()
    old = {"slug": "custom-page", "headline": "Exact Headline", "is_custom": True, "editorial_story_id": "custom:old"}
    same = {"headline": "Exact Headline", "body": "changed body", "is_custom": True, "_custom_active_queue": True}
    different = {"headline": "Exact Headline!", "body": "changed body", "is_custom": True, "_custom_active_queue": True}
    target, forced, story_id = g._resolve_custom_publication_target(same, [old], None, same["headline"])
    assert target is old and forced is None and story_id == "custom:old"
    target, forced, story_id = g._resolve_custom_publication_target(different, [old], old, different["headline"])
    assert target is None and forced is None and story_id.startswith("custom:")


def test_explicit_replace_slug_cannot_override_different_headline():
    g = _load_generate()
    old = {"slug": "existing-custom", "headline": "Old Headline", "is_custom": True}
    new = {"headline": "New Headline", "body": "new", "is_custom": True, "_custom_active_queue": True, "replace_slug": "existing-custom"}
    target, forced, _ = g._resolve_custom_publication_target(new, [old], old, new["headline"])
    assert target is None
    assert forced is None


def test_exact_payload_is_retained_as_active_placement_without_republication(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    headline, body = "Custom city budget article", "budget " * 100
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": "custom-city-budget", "headline": headline, "is_custom": True,
        "custom_body_hash": g._custom_body_hash(body), "product_guide_hash": ""
    }]), encoding="utf-8")
    (tmp_path / "custom_articles.json").write_text(json.dumps([{
        "headline": headline, "body": body, "category": "local_gov", "expires": "2099-01-01"
    }]), encoding="utf-8")

    retained = g.load_custom_articles()

    assert len(retained) == 1
    assert retained[0]["_custom_payload_unchanged"] is True
    assert retained[0]["_custom_active_queue"] is True
    assert retained[0]["_archived_slug"] == "custom-city-budget"
    assert retained[0]["link"].endswith("/articles/custom-city-budget.html")


def test_changed_body_updates_exact_headline_in_place(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    headline = "Custom city budget article"
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": "custom-city-budget", "headline": headline, "is_custom": True,
        "custom_body_hash": g._custom_body_hash("old")
    }]), encoding="utf-8")
    (tmp_path / "custom_articles.json").write_text(json.dumps([{
        "headline": headline, "body": "new complete body", "category": "local_gov", "expires": "2099-01-01"
    }]), encoding="utf-8")
    rows = g.load_custom_articles()
    assert len(rows) == 1
    assert rows[0]["replace_slug"] == "custom-city-budget"
    assert rows[0]["body"] == "new complete body"


def test_custom_category_repair_still_honors_declared_category():
    g = _load_generate()
    custom = {"headline": "Manual Florida Story", "body": "copy", "category": "florida", "is_custom": True, "authoritative_custom": True}
    categories = [
        {"category_key": "sports", "category_label": "Sports", "hero": custom, "cards": []},
        {"category_key": "florida", "category_label": "Florida", "hero": {"headline": "Other"}, "cards": []},
    ]
    report = g.enforce_custom_category_placement(categories)
    assert report["moved"] == 1
    assert custom in categories[1]["cards"]


def test_custom_body_fidelity_for_normal_article():
    g = _load_generate()
    body = "**Lead.**\n\n## Section\n\n- One\n- Two\n\nFinal."
    hero = {"headline": "Manual", "body": body, "is_custom": True, "authoritative_custom": True}
    page = '<div class="article-body">' + g.make_paragraphs(body, preserve_all=True) + '</div><div class="article-share">share</div>'
    assert g.validate_custom_body_fidelity(hero, page) is True


def test_custom_body_fidelity_tolerates_inline_newsletter_before_share():
    g = _load_generate()
    body = "Lead paragraph.\n\nSecond paragraph with local details."
    hero = {
        "headline": "Manual newsletter placement test",
        "body": body,
        "is_custom": True,
        "authoritative_custom": True,
    }
    page = (
        '<div class="article-body">'
        + g.make_paragraphs(body, preserve_all=True)
        + "</div>"
        + g._newsletter_inline_embed("article")
        + '<div class="article-share">share</div>'
    )
    assert g.validate_custom_body_fidelity(hero, page) is True
