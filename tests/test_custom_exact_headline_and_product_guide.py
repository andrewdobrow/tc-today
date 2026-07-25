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


def _guide():
    return {
        "article_type": "product_guide",
        "headline": "Hurricane Season Ready: Treasure Coast Essentials",
        "category": "florida",
        "intro": "Prepare before a storm approaches.",
        "products": [
            {
                "name": "Emergency Radio",
                "image_url": "https://images.example/radio.jpg",
                "affiliate_url": "https://www.amazon.com/dp/ABC?tag=tct-20",
                "label": "Best Overall",
                "summary": "Receives weather alerts.",
                "why_we_chose_it": ["NOAA alerts", "Backup light"],
                "best_for": "Weather information",
                "key_feature": "NOAA alerts",
            },
            {
                "name": "Portable Power Station",
                "image_url": "https://images.example/power.jpg",
                "affiliate_url": "https://www.amazon.com/dp/XYZ?tag=tct-20",
                "summary": "Charges phones and lights.",
                "why_we_chose_it": ["Multiple outputs"],
                "best_for": "Short outages",
            },
        ],
        "closing": "Review supplies before hurricane season.",
    }


def test_same_exact_headline_updates_even_when_body_changes(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    headline = "Exact Custom Headline"
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": "exact-custom-headline",
        "headline": headline,
        "is_custom": True,
        "authoritative_custom": True,
        "custom_body_hash": g._custom_body_hash("old body"),
        "editorial_story_id": "custom:existing",
    }]), encoding="utf-8")
    (tmp_path / "custom_articles.json").write_text(json.dumps([{
        "headline": headline,
        "body": "entirely new body",
        "category": "florida",
        "expires": "2099-01-01",
    }]), encoding="utf-8")
    loaded = g.load_custom_articles()
    assert len(loaded) == 1
    assert loaded[0]["replace_slug"] == "exact-custom-headline"
    assert loaded[0]["body"] == "entirely new body"
    target, forced, story_id = g._resolve_custom_publication_target(
        loaded[0], json.loads((tmp_path / "archive.json").read_text()), None, headline
    )
    assert target["slug"] == "exact-custom-headline"
    assert forced is None
    assert story_id == "custom:existing"


def test_any_headline_difference_creates_a_new_article():
    g = _load_generate()
    old = {"slug": "old", "headline": "Weekly Report July 12-17", "is_custom": True}
    new = {"headline": "Weekly Report July 26-31", "body": "new", "is_custom": True}
    target, forced, story_id = g._resolve_custom_publication_target(new, [old], old, new["headline"])
    assert target is None
    assert forced is None
    assert story_id.startswith("custom:")


def test_case_or_punctuation_change_is_not_exact():
    g = _load_generate()
    old = {"slug": "old", "headline": "City Budget Update", "is_custom": True}
    for headline in ("city Budget Update", "City Budget Update!", "City  Budget Update"):
        target, _, _ = g._resolve_custom_publication_target(
            {"headline": headline, "body": "new", "is_custom": True}, [old], old, headline
        )
        assert target is None


def test_product_guide_normalizes_and_preserves_exact_links():
    g = _load_generate()
    guide = _guide()
    g._normalize_product_guide(guide)
    html = g._render_product_guide_body(guide)
    assert guide["product_count"] == 2
    assert 'rel="sponsored nofollow noopener noreferrer"' in html
    for product in guide["products"]:
        assert product["affiliate_url"] in html
        assert product["image_url"] in html
        assert product["name"] in html
    assert g.validate_product_guide_fidelity(guide, html) is True


def test_product_guide_rejects_missing_or_invalid_links():
    g = _load_generate()
    guide = _guide()
    guide["products"][0]["affiliate_url"] = ""
    try:
        g._normalize_product_guide(guide)
    except ValueError as exc:
        assert "invalid affiliate_url" in str(exc)
    else:
        raise AssertionError("invalid affiliate link should fail")


def test_product_guide_full_page_uses_article_and_itemlist_schema():
    g = _load_generate()
    guide = _guide()
    guide.update({"is_custom": True, "authoritative_custom": True, "published": "Sat, 25 Jul 2026 18:00:00 -0400"})
    g._normalize_product_guide(guide)
    page = g.render_article_page(guide, "Florida", "florida", "2026-07-25", "hurricane-essentials")
    assert '"@type": "Article"' in page
    assert '"@type": "ItemList"' in page
    assert 'class="pg-product-card"' in page
    assert g.validate_custom_body_fidelity(guide, page) is True


def test_retired_traffic_article_is_skipped_removed_and_quarantined(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    headline = "Treasure Coast Traffic Report: I-95 Ramp Closures and Road Work Planned July 26-31"
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "custom-retirements.json").write_text(json.dumps({"headlines": [headline]}), encoding="utf-8")
    (tmp_path / "custom_articles.json").write_text(json.dumps([{
        "headline": headline, "body": "legacy", "category": "florida", "expires": "2099-01-01"
    }]), encoding="utf-8")
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": "legacy-traffic", "headline": headline, "is_custom": True
    }]), encoding="utf-8")
    assert g.load_custom_articles() == []
    item = {"headline": headline, "is_custom": True, "authoritative_custom": True}
    categories = [{"category_key": "florida", "hero": item, "cards": [{"headline": "Other"}]}]
    assert g.apply_custom_retirements_to_live(categories, output_root=tmp_path) == 1
    assert categories[0]["hero"]["headline"] == "Other"
    assert g.apply_custom_retirements_to_archive(tmp_path) == 1
    archive = json.loads((tmp_path / "archive.json").read_text())
    assert archive[0]["exclude_from_live_recovery"] is True
    assert archive[0]["identity_quarantine_reason"] == "editor_retired_custom_article"
