import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_generate():
    path = Path("scripts/generate.py")
    spec = importlib.util.spec_from_file_location("scripts.generate_canonical_hero_freshness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _category(key, label, item):
    return {
        "category_key": key,
        "category_label": label,
        "hero": item,
        "cards": [],
    }


def _item(headline, when, urgency=6, *, body=None):
    text = body or f"{headline} in Martin County with additional local reporting."
    return {
        "headline": headline,
        "teaser": text,
        "body": text,
        "published_raw": when,
        "date": when,
        "urgency_score": urgency,
        "ranking_eligible": True,
        "enriched": True,
    }


def test_archive_rebind_replaces_fresh_source_time_with_old_canonical_time():
    g = _load_generate()
    item = _item(
        "Martin County hoarding case grows to 108 animals rescued",
        "Wed, 30 Jul 2026 08:00:00 GMT",
        urgency=9,
    )
    entry = {
        "slug": "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response",
        "headline": "More Than 70 Animals Found in Stuart Home During Large-Scale Hoarding Response",
        "first_published": "Mon, 20 Jul 2026 12:00:00 -0400",
        "date": "2026-07-20",
        "editorial_story_id": "story_hoarding",
        "ranking_eligible": True,
    }

    assert g._bind_live_item_to_archive(item, entry)
    assert item["_canonical_freshness_bound"] is True
    assert item["published_raw"] == entry["first_published"]
    assert item["first_published"] == entry["first_published"]

    assessment = g._canonical_hero_freshness_assessment(
        item, now=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    )
    assert assessment["stale"] is True
    assert assessment["date_field"] == "first_published"
    assert assessment["reason"] == "canonical_publication_stale"


def test_lastmod_or_source_date_cannot_refresh_old_canonical():
    g = _load_generate()
    item = _item(
        "Old canonical with a fresh technical rewrite",
        "Wed, 30 Jul 2026 08:00:00 GMT",
    )
    item.update({
        "_canonical_freshness_bound": True,
        "canonical_slug": "old-story",
        "first_published": "Mon, 20 Jul 2026 12:00:00 -0400",
        "date": "2026-07-20",
        "lastmod": "2026-07-30",
    })

    assessment = g._canonical_hero_freshness_assessment(
        item, now=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    )
    assert assessment["stale"] is True
    assert assessment["date_field"] == "first_published"


def test_validated_meaningful_update_can_refresh_canonical_hero_eligibility():
    g = _load_generate()
    item = _item("Existing story receives a real new development", "2026-07-20")
    item.update({
        "_canonical_freshness_bound": True,
        "canonical_slug": "existing-story",
        "first_published": "2026-07-20",
        "meaningful_update_validated": True,
        "last_meaningful_update_at": "2026-07-30T10:30:00Z",
    })

    assessment = g._canonical_hero_freshness_assessment(
        item, now=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    )
    assert assessment["stale"] is False
    assert assessment["date_field"] == "last_meaningful_update_at"
    assert assessment["reason"] == "validated_meaningful_update_fresh"


def test_meaningful_update_stamp_requires_context_novelty_and_real_change():
    g = _load_generate()
    existing = {"slug": "existing-story"}
    item = {"_editorial_route": "update_existing"}
    diagnostics = {
        "required": True,
        "passed": True,
        "baseline_present": True,
        "novelty_present": True,
    }
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)

    assert g._record_validated_meaningful_update(
        existing, item, diagnostics, changed=True, now=now
    )
    assert existing["meaningful_update_validated"] is True
    assert existing["last_meaningful_update_at"] == "2026-07-30T12:00:00Z"

    unchanged = {}
    assert not g._record_validated_meaningful_update(
        unchanged, item, diagnostics, changed=False, now=now
    )
    assert "last_meaningful_update_at" not in unchanged


def test_exact_hoarding_regression_reselects_fresh_canonical_after_final_binding(tmp_path):
    g = _load_generate()
    g.CANONICAL_HERO_FRESHNESS_REPORT_PATH = tmp_path / "canonical-hero-freshness-contract.json"
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=10)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    fresh = (now - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")

    hoarding = _item(
        "Martin County hoarding case grows to 108 animals rescued, more charges possible",
        fresh,
        urgency=10,
        body="Martin County officials said today that the Stuart hoarding response now involves 108 animals.",
    )
    hoarding.update({
        "_canonical_freshness_bound": True,
        "canonical_slug": "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response",
        "_archived_slug": "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response",
        "first_published": old,
        "date": (now - timedelta(days=10)).strftime("%Y-%m-%d"),
        "published_raw": old,
    })
    fresh_story = _item(
        "Martin County School District approves new transportation plan",
        fresh,
        urgency=7,
        body="Martin County School District approved a transportation plan today after a public meeting.",
    )
    fresh_story.update({
        "_canonical_freshness_bound": True,
        "canonical_slug": "fresh-school-plan",
        "_archived_slug": "fresh-school-plan",
        "first_published": fresh,
        "published_raw": fresh,
    })

    old_cat = _category("martin", "Martin County", hoarding)
    fresh_cat = _category("local_gov", "Local Government", fresh_story)

    selected = g.enforce_final_canonical_hero_freshness(
        [old_cat, fresh_cat], old_cat, tmp_path
    )

    assert selected is fresh_cat
    report = (tmp_path / "canonical-hero-freshness-contract.json").read_text()
    assert '"passed": true' in report
    assert '"action": "reselected_after_final_canonical_binding"' in report
    assert "fresh-school-plan" in report


def test_stale_fallback_is_allowed_only_when_no_fresh_canonical_exists(tmp_path):
    g = _load_generate()
    g.CANONICAL_HERO_FRESHNESS_REPORT_PATH = tmp_path / "canonical-hero-freshness-contract.json"
    old = (datetime.now(timezone.utc) - timedelta(days=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    item = _item("Old but only available Martin County story", old, urgency=4)
    item.update({
        "_canonical_freshness_bound": True,
        "canonical_slug": "old-only-story",
        "_archived_slug": "old-only-story",
        "first_published": old,
    })
    category = _category("martin", "Martin County", item)

    selected = g.enforce_final_canonical_hero_freshness([category], category, tmp_path)
    assert selected is category
    report = (tmp_path / "canonical-hero-freshness-contract.json").read_text()
    assert '"action": "stale_fallback_no_fresh_canonical_candidates"' in report


def test_final_freshness_gate_can_reselect_recent_archive_recovery(tmp_path):
    g = _load_generate()
    g.CANONICAL_HERO_FRESHNESS_REPORT_PATH = tmp_path / "canonical-hero-freshness-contract.json"
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    fresh = (now - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")

    stale_live_item = _item(
        "Martin County School District consolidates older bus routes",
        old,
        urgency=8,
        body="Martin County school officials discussed the route changes earlier this week.",
    )
    stale_live_item.update({
        "_canonical_freshness_bound": True,
        "canonical_slug": "older-martin-county-bus-routes",
        "_archived_slug": "older-martin-county-bus-routes",
        "first_published": old,
    })
    fresh_archive_item = _item(
        "Fort Pierce police announce a new public-safety development",
        fresh,
        urgency=6,
        body="Fort Pierce police announced the new public-safety development today.",
    )
    fresh_archive_item.update({
        "_archive_only": True,
        "_archive_verified_quality": True,
        "_canonical_freshness_bound": True,
        "canonical_slug": "fresh-fort-pierce-public-safety-development",
        "_archived_slug": "fresh-fort-pierce-public-safety-development",
        "first_published": fresh,
        "ranking_eligible": True,
    })

    stale_live = _category("local_gov", "Local Government", stale_live_item)
    fresh_archive = _category("crime", "Crime & Safety", fresh_archive_item)

    selected = g.enforce_final_canonical_hero_freshness(
        [stale_live, fresh_archive], stale_live, tmp_path
    )

    assert selected is fresh_archive
    report = (tmp_path / "canonical-hero-freshness-contract.json").read_text()
    assert '"passed": true' in report
    assert '"action": "reselected_after_final_canonical_binding"' in report
    assert "fresh-fort-pierce-public-safety-development" in report
