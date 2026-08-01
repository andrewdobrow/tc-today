from datetime import datetime, timezone
import importlib.util
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
    spec = importlib.util.spec_from_file_location("generate_forward_identity_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_current_run_decision_stamps_generated_rewrite_by_exact_source_url():
    g = _load_generate()
    g.CURRENT_RUN_EDITORIAL_IDENTITIES = {
        "https://source.test/news/article": {
            "story_id": "story-current",
            "event_key": "event-current",
            "route": "generate_new",
        }
    }
    headlines = [{"title": "Original source title", "link": "https://source.test/news/article?utm_source=rss"}]
    data = {
        "hero": {
            "headline": "Substantially rewritten TCT headline",
            "source_index": 1,
            "link": "https://source.test/news/article?utm_source=rss",
        },
        "cards": [],
    }
    assert g._stamp_current_run_story_ids(data, headlines) == 1
    assert data["hero"]["editorial_story_id"] == "story-current"
    assert data["hero"]["_editorial_route"] == "generate_new"
    assert data["hero"]["source_headline"] == "Original source title"


def test_forward_target_never_reuses_fuzzy_unrelated_slug():
    g = _load_generate()
    item = {
        "headline": "Leon County judge to rule on ballot eligibility",
        "source_url": "https://source.test/ballot-case",
        "editorial_story_id": "story-ballot",
        "_editorial_route": "generate_new",
    }
    archive = [{
        "slug": "2026-06-12-police-union-backs-paul-renner",
        "headline": "Police union backs Paul Renner",
        "source_url": "https://source.test/endorsement",
    }]
    target, basis = g._find_forward_publication_target(item, archive, "story-ballot")
    assert target is None
    assert basis == "new_publication"


def test_forward_target_updates_same_exact_source_and_preserves_identity():
    g = _load_generate()
    item = {
        "headline": "Updated headline",
        "source_url": "https://source.test/news/article?utm_medium=rss",
        "editorial_story_id": "story-one",
        "_editorial_route": "update_existing",
    }
    archive = [{
        "slug": "2026-07-24-original",
        "headline": "Original headline",
        "source_url": "https://source.test/news/article",
        "editorial_story_id": "story-one",
    }]
    target, basis = g._find_forward_publication_target(item, archive, "story-one")
    assert target["slug"] == "2026-07-24-original"
    assert basis == "exact_source_url"
    valid, reason = g._forward_publication_target_valid(
        item,
        target,
        "story-one",
        basis,
        now=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )
    assert valid is True
    assert reason == "exact_source_url"


def test_prospective_alignment_does_not_invent_age_for_undated_archive_row():
    g = _load_generate()
    entry = {
        "slug": "2026-07-24-original",
        "headline": "Original headline",
        "source_url": "https://source.test/news/article",
        "editorial_story_id": "story-one",
    }
    incoming = {
        "headline": "Updated headline",
        "source_url": "https://source.test/news/article?utm_medium=rss",
        "editorial_story_id": "story-one",
    }

    result = g._prospective_archive_update_alignment(
        incoming,
        entry,
        now=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )

    assert result["aligned"] is True
    assert result["timestamp_evidence"] == "missing_existing_archive_timestamp"
    assert result["date_gap_days"] is None


def test_recurring_custom_report_rejects_previous_edition_slug():
    g = _load_generate()
    hero = {
        "headline": "Treasure Coast Traffic Report: I-95 Work Planned July 26-31",
        "body": "Complete manually authored report body.",
        "is_custom": True,
        "slug": "2026-07-10-treasure-coast-traffic-report-july-12-17",
    }
    archive = [{
        "slug": "2026-07-10-treasure-coast-traffic-report-july-12-17",
        "headline": "Treasure Coast Traffic Report: Work Planned July 12-17",
        "is_custom": True,
    }]
    existing, forced_slug, story_id = g._resolve_custom_publication_target(
        hero, archive, archive[0], hero["headline"]
    )
    assert existing is None
    assert forced_slug is None
    assert story_id.startswith("custom:")
    assert hero["_superseded_custom_slug"] == archive[0]["slug"]


def test_recurring_custom_edition_alignment_detects_old_date_range():
    g = _load_generate()
    entry = {
        "slug": "2026-07-10-treasure-coast-traffic-report-july-12-17",
        "headline": "Treasure Coast Traffic Report: I-95 Work Planned July 26-31",
        "is_custom": True,
        "lastmod": "2026-07-25",
    }
    result = g._archive_headline_slug_alignment(entry)
    assert result["aligned"] is False
    assert result["reason"] == "recurring_custom_edition_slug_mismatch"


def test_forward_live_identity_contract_rejects_story_id_conflict(tmp_path):
    g = _load_generate()
    (tmp_path / "data").mkdir()
    (tmp_path / "archive.json").write_text(
        '[{"slug":"one","headline":"One","editorial_story_id":"story-a","ranking_eligible":true}]',
        encoding="utf-8",
    )
    categories = [{
        "category_key": "crime",
        "hero": {
            "headline": "One",
            "_archived_slug": "one",
            "link": "https://treasurecoast.today/articles/one.html",
            "editorial_story_id": "story-b",
        },
        "cards": [],
    }]
    try:
        g.validate_forward_live_identity(categories, categories[0], tmp_path)
    except RuntimeError as exc:
        assert "story_id_conflict" in str(exc)
    else:
        raise AssertionError("expected forward live identity contract to fail")


def test_quarantined_headline_slug_drift_is_never_reused_as_forward_target():
    g = _load_generate()
    item = {
        "headline": "Leon County judge to rule Monday on ballot eligibility",
        "source_url": "https://source.test/ballot-case",
        "editorial_story_id": "story-ballot",
        "_editorial_route": "update_existing",
    }
    quarantined = {
        "slug": "2026-06-12-police-union-backs-paul-renner",
        "headline": item["headline"],
        "source_url": item["source_url"],
        "editorial_story_id": "story-ballot",
        "exclude_from_live_recovery": True,
        "identity_quarantine_reason": "headline_slug_event_drift",
    }

    target, basis = g._find_forward_publication_target(
        item, [quarantined], "story-ballot"
    )

    assert target is None
    assert basis == "new_publication"
    valid, reason = g._forward_publication_target_valid(
        item, quarantined, "story-ballot", "exact_source_url"
    )
    assert valid is False
    assert reason == "headline_slug_event_drift"


def test_post_publication_rebind_prefers_repaired_slug_over_quarantined_older_slug(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "2026-06-12-police-union-backs-paul-renner.html").write_text(
        "old", encoding="utf-8"
    )
    repaired_slug = "2026-07-26-leon-county-judge-to-rule-monday-on-ballot-eligibility"
    (articles / f"{repaired_slug}.html").write_text("new", encoding="utf-8")
    headline = "Leon County judge to rule Monday on ballot eligibility"
    archive = [
        {
            "slug": "2026-06-12-police-union-backs-paul-renner",
            "headline": headline,
            "editorial_story_id": "story-ballot",
            "exclude_from_live_recovery": True,
            "identity_quarantine_reason": "headline_slug_event_drift",
        },
        {
            "slug": repaired_slug,
            "headline": headline,
            "date": "2026-07-26",
            "lastmod": "2026-07-26",
            "editorial_story_id": "story-ballot",
            "ranking_eligible": True,
        },
    ]
    categories = [{
        "category_key": "florida",
        "hero": {
            "headline": headline,
            "editorial_story_id": "story-ballot",
            "_editorial_story_id": "story-ballot",
            "_archived_slug": archive[0]["slug"],
        },
        "cards": [],
    }]

    rebound = g._rebind_live_items_to_published_archive(
        categories, archive, articles_dir=articles
    )

    assert rebound == 1
    assert categories[0]["hero"]["_archived_slug"] == repaired_slug
    assert categories[0]["hero"]["link"].endswith(f"/{repaired_slug}.html")


def test_editor_supplied_custom_slug_preserves_suffix_beyond_generic_slug_limit():
    g = _load_generate()
    requested = (
        "2026-07-31-treasure-coast-traffic-report-i-95-ramp-and-road-"
        "closures-planned-aug-2-7"
    )
    assert len(requested) > 80
    hero = {
        "headline": "Treasure Coast Traffic Report: I-95 Ramp and Road Closures Planned Aug. 2-7",
        "body": "Complete manually authored traffic report.",
        "is_custom": True,
        "_custom_requested_slug": requested,
    }

    existing, forced_slug, story_id = g._resolve_custom_publication_target(
        hero, [], None, hero["headline"]
    )

    assert existing is None
    assert forced_slug == requested
    assert forced_slug.endswith("aug-2-7")
    assert story_id.startswith("custom:")


def test_abbreviated_month_recurring_edition_marker_matches_explicit_custom_slug():
    g = _load_generate()
    entry = {
        "headline": "Treasure Coast Traffic Report: I-95 Ramp and Road Closures Planned Aug. 2-7",
        "slug": (
            "2026-07-31-treasure-coast-traffic-report-i-95-ramp-and-road-"
            "closures-planned-aug-2-7"
        ),
        "is_custom": True,
    }

    assert g._custom_edition_marker(entry) == "aug-2-7"
    assert g._custom_series_slug_mismatch(entry, entry["slug"]) is False
    assert g._archive_headline_slug_alignment(entry)["aligned"] is True


def test_truncated_recurring_custom_slug_is_rejected_before_live_publication():
    g = _load_generate()
    entry = {
        "headline": "Treasure Coast Traffic Report: I-95 Ramp and Road Closures Planned Aug. 2-7",
        "slug": (
            "2026-07-31-treasure-coast-traffic-report-i-95-ramp-and-road-"
            "closures-planned-aug"
        ),
        "is_custom": True,
    }

    result = g._archive_headline_slug_alignment(entry)
    assert result["aligned"] is False
    assert result["reason"] == "recurring_custom_edition_slug_mismatch"


def test_forward_live_identity_accepts_exact_long_custom_edition_slug(tmp_path):
    g = _load_generate()
    (tmp_path / "data").mkdir()
    slug = (
        "2026-07-31-treasure-coast-traffic-report-i-95-ramp-and-road-"
        "closures-planned-aug-2-7"
    )
    headline = "Treasure Coast Traffic Report: I-95 Ramp and Road Closures Planned Aug. 2-7"
    story_id = "custom:traffic-aug-2-7"
    (tmp_path / "archive.json").write_text(
        __import__("json").dumps([
            {
                "slug": slug,
                "headline": headline,
                "editorial_story_id": story_id,
                "ranking_eligible": True,
                "is_custom": True,
                "authoritative_custom": True,
                "custom_series_key": "treasure-coast-traffic-report",
                "custom_edition_key": "aug-2-7",
            }
        ]),
        encoding="utf-8",
    )
    placement = {
        "headline": headline,
        "slug": slug,
        "_archived_slug": slug,
        "link": f"https://treasurecoast.today/articles/{slug}.html",
        "editorial_story_id": story_id,
        "is_custom": True,
        "authoritative_custom": True,
    }
    categories = [{"category_key": "local_gov", "hero": placement, "cards": []}]

    report = g.validate_forward_live_identity(categories, categories[0], tmp_path)

    assert report["passed"] is True
    assert report["violation_count"] == 0
