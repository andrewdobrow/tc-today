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
        "headline": "Hurricane Season Ready: 12 Treasure Coast Essentials to Stock Up On",
        "category": "florida",
        "slug": "2026-07-25-hurricane-season-ready-12-treasure-coast-essentials-to-stock-up-on",
        "intro": "Prepare before a storm approaches.",
        "products": [
            {
                "name": "Emergency Radio",
                "image_url": "https://images.example/radio.jpg",
                "affiliate_url": "https://www.amazon.com/dp/ABC?tag=tct-20",
                "summary": "Receives weather alerts.",
                "why_we_chose_it": ["NOAA alerts", "Backup light"],
                "best_for": "Weather information",
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


def test_different_current_custom_cannot_replace_archive_recovery_copy(monkeypatch):
    g = _load_generate()
    archived = {
        "slug": "sports-custom-recap",
        "headline": "Zayas Homers Twice as St. Lucie Mets Cruise Past Mighty Mussels",
        "body": "Archived sports copy",
        "category_key": "sports",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:sports",
    }
    recovered = dict(
        archived,
        _archived_slug=archived["slug"],
        _archive_only=True,
        _archive_verified_quality=True,
    )
    guide = _guide()
    g._normalize_product_guide(guide)
    guide.update({"is_custom": True, "authoritative_custom": True})

    # Recreate the dangerous condition: the broad event matcher claims two distinct
    # custom stories are related. Exact-headline authority must still prevent a swap.
    monkeypatch.setattr(g, "_same_event_items", lambda *args, **kwargs: True)
    assert g._bind_live_item_to_archive(
        recovered, archived, [guide], replace_with_custom=True
    ) is True

    assert recovered["headline"] == archived["headline"]
    assert recovered["body"] == archived["body"]
    assert recovered["_archive_only"] is True
    assert recovered["category_key"] == "sports"


def test_exact_headline_refresh_restores_declared_category_and_active_state():
    g = _load_generate()
    headline = "Exact Manual Headline"
    archived = {
        "slug": "exact-manual-headline",
        "headline": headline,
        "body": "Old body",
        "category_key": "sports",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:exact",
    }
    recovered = dict(
        archived,
        _archived_slug=archived["slug"],
        _archive_only=True,
        _archive_verified_quality=True,
    )
    current = {
        "headline": headline,
        "body": "New complete body",
        "category": "florida",
        "is_custom": True,
        "authoritative_custom": True,
    }

    assert g._bind_live_item_to_archive(
        recovered, archived, [current], replace_with_custom=True
    ) is True

    assert recovered["body"] == "New complete body"
    assert recovered["category"] == "florida"
    assert recovered["category_key"] == "florida"
    assert recovered["category_label"] == "Florida"
    assert "_archive_only" not in recovered
    assert "_archive_verified_quality" not in recovered


def test_active_custom_queue_payload_outranks_archive_only_hero_clone():
    g = _load_generate()
    active = (
        "florida",
        "Florida",
        {
            "headline": "Manual Guide",
            "body": "active payload",
            "is_custom": True,
            "authoritative_custom": True,
        },
    )
    recovered_hero = (
        "sports",
        "Sports",
        {
            "headline": "Manual Guide",
            "body": "archive clone " * 100,
            "image_url": "https://images.example/archive.jpg",
            "is_custom": True,
            "authoritative_custom": True,
            "_archive_only": True,
            "_is_hero_copy": True,
        },
    )
    assert g._publication_copy_rank(active) > g._publication_copy_rank(recovered_hero)


def test_write_archives_publishes_queue_payload_when_live_clone_is_archive_only(
    tmp_path, monkeypatch
):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    guide = _guide()
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([guide]), encoding="utf-8"
    )
    (tmp_path / "archive.json").write_text("[]", encoding="utf-8")
    (tmp_path / "articles").mkdir()

    loaded = g.load_custom_articles()
    assert len(loaded) == 1
    live_clone = dict(
        loaded[0],
        _archive_only=True,
        _archive_verified_quality=True,
        _is_hero_copy=True,
    )
    sports = {
        "category_key": "sports",
        "category_label": "Sports",
        "hero": live_clone,
        "cards": [],
    }
    florida = {
        "category_key": "florida",
        "category_label": "Florida",
        "hero": {"headline": "Florida placeholder", "_section_placeholder": True},
        "cards": [],
    }

    # Keep this regression focused on queue write-through rather than canonical,
    # redirect, sitemap, or presentation behavior already covered elsewhere.
    monkeypatch.setattr(g, "_sanitize_authoritative_custom_archive", lambda rows, *_: list(rows))
    monkeypatch.setattr(g, "_purge_nonstory_archive_entries", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "apply_canonical_story_cleanup", lambda rows, *_: (list(rows), []))
    monkeypatch.setattr(g, "_load_publication_identity_index", lambda: {})
    monkeypatch.setattr(g, "_backfill_archive_editorial_story_ids", lambda rows, *args, **kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "_reconcile_archive_publication_identity", lambda rows, *_: (list(rows), [], {}))
    monkeypatch.setattr(g, "enforce_canonical_redirects", lambda rows, *_args, **_kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "render_article_page", lambda *_args, **_kwargs: "<html>custom guide</html>")
    monkeypatch.setattr(g, "validate_custom_body_fidelity", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(g, "write_story_regression_report", lambda *_args, **_kwargs: {"production_gate_passed": True})
    monkeypatch.setattr(g, "write_story_health_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(g, "render_archive_page", lambda *_args, **_kwargs: "archive")
    monkeypatch.setattr(g, "update_sitemap", lambda *_args, **_kwargs: "sitemap")
    monkeypatch.setattr(g, "update_news_sitemap", lambda *_args, **_kwargs: "news-sitemap")

    g.write_archives([sports, florida], sports)

    archive = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    matching = [row for row in archive if row.get("headline") == guide["headline"]]
    assert len(matching) == 1
    assert matching[0]["slug"] == guide["slug"]
    assert matching[0]["category_key"] == "florida"
    assert matching[0]["is_custom"] is True
    assert matching[0]["product_count"] == 2
    assert (tmp_path / "articles" / f"{guide['slug']}.html").exists()


def test_unchanged_published_custom_remains_active_queue_item(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    headline = "Port St. Lucie Police Unveil New $28 Million Training Facility"
    body = "The police department unveiled a new training facility."
    slug = "2026-07-25-port-st-lucie-police-unveil-28-million-training-facility"
    queue = [{
        "headline": headline,
        "body": body,
        "category": "st_lucie",
        "image_url": "/images/psltrainingfacility.png",
        "slug": slug,
        "urgency_score": 2,
    }]
    archive = [{
        "slug": slug,
        "headline": headline,
        "teaser": body,
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "date": "2026-07-26",
        "first_published": "Sat, 25 Jul 2026 23:59:00 -0400",
        "published_raw": "Sat, 25 Jul 2026 23:59:00 -0400",
        "lastmod": "2026-07-26",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_body_hash": g._custom_body_hash(body),
        "product_guide_hash": "",
        "editorial_story_id": "custom:psl-training",
        "ranking_eligible": True,
        "legacy_identity_status": "identified",
    }]
    (tmp_path / "custom_articles.json").write_text(json.dumps(queue), encoding="utf-8")
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (tmp_path / "articles").mkdir()
    (tmp_path / "articles" / f"{slug}.html").write_text("<html>published</html>", encoding="utf-8")

    loaded = g.load_custom_articles()

    assert len(loaded) == 1
    item = loaded[0]
    assert item["headline"] == headline
    assert item["_custom_payload_unchanged"] is True
    assert item["_custom_active_queue"] is True
    assert item["_archived_slug"] == slug
    assert item["link"].endswith(f"/articles/{slug}.html")
    assert item["published_raw"] == archive[0]["published_raw"]
    assert item["editorial_story_id"] == "custom:psl-training"
    assert "_archive_only" not in item


def test_write_archives_preserves_long_recurring_traffic_slug_and_live_contract(
    tmp_path, monkeypatch
):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    headline = "Treasure Coast Traffic Report: I-95 Ramp and Road Closures Planned Aug. 2-7"
    slug = (
        "2026-07-31-treasure-coast-traffic-report-i-95-ramp-and-road-"
        "closures-planned-aug-2-7"
    )
    queue = [{
        "headline": headline,
        "slug": slug,
        "category": "local_gov",
        "image_url": "https://treasurecoast.today/images/fdot.png",
        "body": "Motorists should prepare for overnight closures.\n\nFull county-by-county report.",
        "expires": "2026-08-08",
    }]
    (tmp_path / "custom_articles.json").write_text(json.dumps(queue), encoding="utf-8")
    (tmp_path / "archive.json").write_text("[]", encoding="utf-8")
    (tmp_path / "articles").mkdir()

    loaded = g.load_custom_articles()
    assert len(loaded) == 1
    live = loaded[0]
    category = {
        "category_key": "local_gov",
        "category_label": "Local Government",
        "hero": live,
        "cards": [],
    }

    monkeypatch.setattr(g, "_sanitize_authoritative_custom_archive", lambda rows, *_: list(rows))
    monkeypatch.setattr(g, "_purge_nonstory_archive_entries", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "apply_canonical_story_cleanup", lambda rows, *_: (list(rows), []))
    monkeypatch.setattr(g, "_load_publication_identity_index", lambda: {})
    monkeypatch.setattr(g, "_backfill_archive_editorial_story_ids", lambda rows, *args, **kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "_reconcile_archive_publication_identity", lambda rows, *_: (list(rows), [], {}))
    monkeypatch.setattr(g, "enforce_canonical_redirects", lambda rows, *_args, **_kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "render_article_page", lambda *_args, **_kwargs: "<html>traffic report</html>")
    monkeypatch.setattr(g, "validate_custom_body_fidelity", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(g, "write_story_regression_report", lambda *_args, **_kwargs: {"production_gate_passed": True})
    monkeypatch.setattr(g, "write_story_health_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(g, "render_archive_page", lambda *_args, **_kwargs: "archive")
    monkeypatch.setattr(g, "update_sitemap", lambda *_args, **_kwargs: "sitemap")
    monkeypatch.setattr(g, "update_news_sitemap", lambda *_args, **_kwargs: "news-sitemap")

    g.write_archives([category], category)

    archive = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    row = next(entry for entry in archive if entry.get("headline") == headline)
    assert row["slug"] == slug
    assert row["custom_edition_key"] == "aug-2-7"
    assert g._archive_headline_slug_alignment(row)["aligned"] is True
    assert live["_archived_slug"] == slug
    assert live["link"].endswith(f"/{slug}.html")

    report = g.validate_forward_live_identity([category], category, tmp_path)
    assert report["passed"] is True
