from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import sys
import types
from pathlib import Path


def _load_generate():
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
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_published_skip_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _canonical():
    return {
        "slug": "2026-07-23-big-taste-of-martin-county-returns-oct-6-to-support-youth-mentoring-programs",
        "headline": "Big Taste of Martin County returns to Stuart in October to support youth mentoring programs",
        "teaser": (
            "Big Brothers Big Sisters of Palm Beach and Martin Counties is preparing "
            "for the Oct. 6 fundraiser at Atlantic Aviation in Stuart."
        ),
        "category_key": "things_to_do",
        "date": "2026-07-23",
        "lastmod": "2026-07-28",
        "source_url": (
            "https://www.wptv.com/shining-a-light/"
            "big-taste-of-martin-county-returns-to-support-big-brothers-big-sisters-mentoring-programs"
        ),
        "editorial_story_id": "story_000253",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }


def _incoming():
    return {
        "title": "Big Taste of Martin County returns to support Big Brothers Big Sisters mentoring programs",
        "headline": "Big Taste of Martin County fundraiser set for October in Stuart",
        "teaser": (
            "The Big Taste fundraiser returns Oct. 6 at Atlantic Aviation in Stuart "
            "to support youth mentoring programs."
        ),
        "link": _canonical()["source_url"] + "?utm_source=rss",
        "source_url": _canonical()["source_url"] + "?utm_source=rss",
        "editorial_story_id": "story_000253",
        "_editorial_story_id": "story_000253",
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }


def test_exact_big_taste_registry_skip_is_removed_before_model_generation():
    g = _load_generate()
    kept, suppressed = g._filter_published_skip_candidates(
        [_incoming()], [_canonical()], "things_to_do"
    )
    assert kept == []
    assert len(suppressed) == 1
    assert suppressed[0]["canonical_slug"] == g.BIG_TASTE_CANONICAL_SLUG
    assert suppressed[0]["basis"] == "exact_source_and_persistent_story_skip"



def test_google_wrapper_skip_uses_high_confidence_registry_same_event():
    g = _load_generate()
    item = _incoming()
    item["link"] = "https://news.google.com/rss/articles/BIGTASTE?oc=5"
    item["source_url"] = item["link"]
    item["headline"] = "October fundraiser returns to Atlantic Aviation"
    item["teaser"] = "A community fundraiser is planned this fall."
    canonical, basis = g._published_skip_canonical(item, [_canonical()])
    assert canonical["slug"] == g.BIG_TASTE_CANONICAL_SLUG
    assert basis == "registry_same_event_and_persistent_story_skip"


def test_low_confidence_registry_relationship_cannot_suppress_unproven_source():
    g = _load_generate()
    item = _incoming()
    item["link"] = "https://news.google.com/rss/articles/UNRELATED?oc=5"
    item["source_url"] = item["link"]
    item["headline"] = "Unrelated community fundraiser"
    item["teaser"] = "A different event is planned elsewhere."
    item["_editorial_relationship_confidence"] = 0.7
    canonical, basis = g._published_skip_canonical(item, [_canonical()])
    assert canonical is None
    assert basis == ""

def test_update_existing_route_is_not_suppressed_by_no_change_guard():
    g = _load_generate()
    item = _incoming()
    item["_editorial_route"] = "update_existing"
    kept, suppressed = g._filter_published_skip_candidates(
        [item], [_canonical()], "things_to_do"
    )
    assert kept == [item]
    assert suppressed == []


def test_skip_route_preserves_existing_permalink_without_prospective_drift_quarantine():
    g = _load_generate()
    item = _incoming()
    target, basis = g._find_forward_publication_target(
        item, [_canonical()], "story_000253"
    )
    valid, reason = g._forward_publication_target_valid(
        item,
        target,
        "story_000253",
        basis,
        now=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )
    assert valid is True
    assert reason == "published_skip_preserve_existing"


def test_cached_big_taste_rewrite_is_removed_before_live_reuse():
    g = _load_generate()
    data = {
        "hero": _incoming(),
        "cards": [{"headline": "Different event", "enriched": True}],
    }
    removed = g._suppress_published_skip_placements(
        data, [_canonical()], "things_to_do"
    )
    assert len(removed) == 1
    assert data["hero"]["headline"] == "Different event"


def test_false_prospective_quarantine_is_repaired_and_newer_duplicate_redirected():
    g = _load_generate()
    old = _canonical()
    old.update({
        "exclude_from_live_recovery": True,
        "ranking_eligible": False,
        "legacy_identity_status": "quarantined_live_mismatch",
        "identity_quarantine_persistent": True,
        "identity_quarantine_reason": "prospective_headline_slug_event_drift",
    })
    new = {
        **_canonical(),
        "slug": "2026-07-29-big-taste-of-martin-county-fundraiser-set-for-october-in-stuart",
        "headline": "Big Taste of Martin County fundraiser set for October in Stuart",
        "date": "2026-07-29",
        "lastmod": "2026-07-29",
    }
    identity_index = types.SimpleNamespace(safe_story_ids={"story_000253"})
    cleaned, redirects, report = g._reconcile_archive_publication_identity(
        [old, new], identity_index
    )
    assert [row["slug"] for row in cleaned] == [g.BIG_TASTE_CANONICAL_SLUG]
    assert cleaned[0].get("exclude_from_live_recovery") is None
    assert cleaned[0]["ranking_eligible"] is True
    assert report["prospective_quarantine_repairs"] == 1
    assert redirects[0]["source_slug"] in g.BIG_TASTE_REDIRECT_SOURCE_SLUGS
    assert redirects[0]["target_slug"] == g.BIG_TASTE_CANONICAL_SLUG


def test_permanent_big_taste_redirect_exists_even_after_duplicate_archive_row_is_gone(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    canonical = _canonical()
    cleaned, redirects = g.apply_canonical_story_cleanup(
        [canonical], articles, tmp_path
    )
    assert [row["slug"] for row in cleaned] == [g.BIG_TASTE_CANONICAL_SLUG]
    redirect = next(
        row for row in redirects
        if row["source_slug"] in g.BIG_TASTE_REDIRECT_SOURCE_SLUGS
    )
    assert redirect["target_slug"] == g.BIG_TASTE_CANONICAL_SLUG
    redirect_page = articles / f"{redirect['source_slug']}.html"
    assert redirect_page.exists()
    assert g.BIG_TASTE_CANONICAL_SLUG in redirect_page.read_text(encoding="utf-8")



def test_repeated_source_copy_reuses_first_category_audit_identity():
    g = _load_generate()
    g.CURRENT_RUN_EDITORIAL_IDENTITIES.clear()
    source = _incoming()["source_url"]
    g.CURRENT_RUN_EDITORIAL_IDENTITIES[g._normalized_external_source_url(source)] = {
        "story_id": "story_000253",
        "event_key": "unknown-event-ae622bed41",
        "route": "skip",
        "relationship": "same_event",
        "relationship_confidence": 1.0,
    }
    repeated = {"title": _incoming()["title"], "link": source}
    assert g._stamp_known_current_run_identity(repeated) is True
    assert repeated["_editorial_route"] == "skip"
    assert repeated["_editorial_story_id"] == "story_000253"
    assert repeated["_editorial_relationship"] == "same_event"

def test_category_generation_report_counts_published_story_suppressions():
    g = _load_generate()
    report = g._build_category_generation_report([{
        "status": "generated_live",
        "attempt_count": 0,
        "model_elapsed_seconds": 0,
        "archive_recovery_requested": False,
        "published_story_duplicate_suppression_count": 2,
    }])
    assert report["schema_version"] == 6
    assert report["summary"]["published_story_duplicate_suppression_count"] == 2


def test_writer_preserves_repairable_quarantined_skip_without_minting_page(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    old = _canonical()
    old.update({
        "exclude_from_live_recovery": True,
        "ranking_eligible": False,
        "legacy_identity_status": "quarantined_live_mismatch",
        "identity_quarantine_persistent": True,
        "identity_quarantine_reason": "prospective_headline_slug_event_drift",
    })
    (tmp_path / "archive.json").write_text(json.dumps([old]), encoding="utf-8")
    (tmp_path / "custom_articles.json").write_text("[]", encoding="utf-8")
    articles = tmp_path / "articles"
    articles.mkdir()
    canonical_page = articles / f"{g.BIG_TASTE_CANONICAL_SLUG}.html"
    canonical_page.write_text("original canonical page", encoding="utf-8")

    hero = _incoming()
    hero.update({
        "body": " ".join(["Complete source-backed article paragraph."] * 120),
        "enriched": True,
        "image_url": "/images/event.png",
        "urgency_score": 3,
    })
    category = {
        "category_key": "things_to_do",
        "category_label": "Things To Do",
        "hero": hero,
        "cards": [],
    }
    identity_index = types.SimpleNamespace(
        safe_story_ids={"story_000253"},
        all_story_ids={"story_000253"},
    )

    monkeypatch.setattr(g, "load_custom_articles", lambda: [])
    monkeypatch.setattr(g, "_sanitize_authoritative_custom_archive", lambda rows, *_: list(rows))
    monkeypatch.setattr(g, "_purge_nonstory_archive_entries", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "apply_canonical_story_cleanup", lambda rows, *_: (list(rows), []))
    monkeypatch.setattr(g, "_repair_archive_article_lead_framing", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "_repair_archive_claim_drifted_permalinks", lambda rows, *_: (list(rows), [], {}))
    monkeypatch.setattr(g, "_load_publication_identity_index", lambda: identity_index)
    monkeypatch.setattr(g, "_backfill_archive_editorial_story_ids", lambda rows, *_args, **_kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "_reconcile_archive_publication_identity", lambda rows, *_: (list(rows), [], {}))
    monkeypatch.setattr(g, "enforce_canonical_redirects", lambda rows, *_args, **_kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "_backfill_archive_category_memberships", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "_publishable_article", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(g, "render_article_page", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("skip must not render")))
    monkeypatch.setattr(g, "write_story_regression_report", lambda *_args, **_kwargs: {"production_gate_passed": True})
    monkeypatch.setattr(g, "write_story_health_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(g, "render_archive_page", lambda *_args, **_kwargs: "archive")
    monkeypatch.setattr(g, "update_sitemap", lambda *_args, **_kwargs: "sitemap")
    monkeypatch.setattr(g, "update_news_sitemap", lambda *_args, **_kwargs: "news-sitemap")

    g.write_archives([category], category)

    saved = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert [row["slug"] for row in saved] == [g.BIG_TASTE_CANONICAL_SLUG]
    assert canonical_page.read_text(encoding="utf-8") == "original canonical page"
    assert not (articles / "2026-07-29-big-taste-of-martin-county-fundraiser-set-for-october-in-stuart.html").exists()
    forward = json.loads((tmp_path / "data" / "forward-publication-identity.json").read_text(encoding="utf-8"))
    assert forward["published_skip_preservations"][0]["canonical_slug"] == g.BIG_TASTE_CANONICAL_SLUG
