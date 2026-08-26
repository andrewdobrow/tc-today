from __future__ import annotations

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
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    if "json_repair" not in sys.modules:
        json_repair = types.ModuleType("json_repair")
        json_repair.repair_json = lambda value: value
        sys.modules["json_repair"] = json_repair
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_final_pipeline_stabilization", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare_recovery_test(monkeypatch, g, archive):
    monkeypatch.setattr(g, "CATEGORIES", {
        "crime": {"label": "Crime & Safety", "front_page_hero": True}
    })
    monkeypatch.setattr(g, "load_archive", lambda *args, **kwargs: list(archive))
    monkeypatch.setattr(g, "_sanitize_authoritative_custom_archive", lambda rows, *_: rows)
    monkeypatch.setattr(g, "_filter_source_retirement_archive_view", lambda rows, *_: rows)
    monkeypatch.setattr(g, "_backfill_archive_editorial_story_ids", lambda rows, *args, **kwargs: (rows, {}))
    monkeypatch.setattr(g, "_load_publication_identity_index", lambda *args, **kwargs: {})
    monkeypatch.setattr(g, "enforce_live_county_membership_authority", lambda *args, **kwargs: {"rejections": []})
    monkeypatch.setattr(g, "_archive_entry_publishable", lambda entry: True)
    monkeypatch.setattr(g, "_archive_entry_has_contextless_update_lead", lambda entry: False)
    monkeypatch.setattr(g, "_archive_entry_has_article_framing_failure", lambda entry: False)
    monkeypatch.setattr(
        g,
        "_category_eligibility_contract_assessment",
        lambda category_key, item: {"mode": "enforce", "eligible": True},
    )
    monkeypatch.setattr(g, "_category_membership_contains", lambda entry, category_key: True)
    monkeypatch.setattr(g, "_hero_eligible", lambda category_key, item: bool(item.get("headline")))
    monkeypatch.setattr(g, "get_fallback_image", lambda *args, **kwargs: ("", ""))


def test_surviving_live_card_is_promoted_before_unrelated_archive_recovery(monkeypatch):
    g = _load_generate()
    barn = {
        "slug": "barn-fire",
        "headline": "Sheriff's helicopter spots massive barn fire on Southwest Martin Highway in Palm City",
        "teaser": "A barn burned in Palm City.",
        "lastmod": "2026-08-24",
        "category_key": "crime",
    }
    _prepare_recovery_test(monkeypatch, g, [barn])
    flock = {
        "headline": "Indian River County sheriff credits Flock Safety cameras in Vero Beach homicide arrest",
        "teaser": "A homicide arrest renewed debate over police camera use.",
        "body": "A homicide arrest renewed debate over police camera use.",
        "urgency_score": 6,
    }
    categories = [{
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "hero": None,
        "cards": [flock],
    }]

    g.ensure_all_category_sections(categories, min_cards=0)

    assert categories[0]["hero"]["headline"] == flock["headline"]
    assert categories[0]["hero"]["_hero_recovery_basis"] == "surviving_live_card"
    assert not categories[0]["hero"].get("_archive_only")


def test_suppressed_duplicate_recovers_exact_canonical_before_generic_archive(monkeypatch):
    g = _load_generate()
    barn = {
        "slug": "barn-fire",
        "headline": "Sheriff's helicopter spots massive barn fire on Southwest Martin Highway in Palm City",
        "teaser": "A barn burned in Palm City.",
        "lastmod": "2026-08-24",
        "category_key": "crime",
    }
    flock = {
        "slug": "flock-homicide",
        "headline": "Indian River County sheriff credits Flock Safety cameras in Vero Beach homicide arrest",
        "teaser": "A homicide arrest renewed debate over police camera use.",
        "lastmod": "2026-08-23",
        "category_key": "crime",
    }
    _prepare_recovery_test(monkeypatch, g, [barn, flock])
    categories = [{
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "hero": None,
        "cards": [],
        "_preferred_archive_recovery_slugs": ["flock-homicide"],
    }]

    g.ensure_all_category_sections(categories, min_cards=0)

    hero = categories[0]["hero"]
    assert hero["headline"] == flock["headline"]
    assert hero["_archived_slug"] == "flock-homicide"
    assert hero["_hero_recovery_basis"] == "suppressed_duplicate_canonical"


def test_port_st_lucie_headline_is_grounded_by_st_lucie_county_lead():
    g = _load_generate()
    item = {
        "headline": "National Weather Service confirms EF0 tornado damaged homes in Port St. Lucie",
        "body": (
            "The National Weather Service confirmed Monday that an EF0 tornado touched down "
            "Sunday evening in St. Lucie County, damaging homes along a 2.1-mile path."
        ),
    }

    diagnostics = g._headline_lead_claim_diagnostics(item)

    assert diagnostics["passed"] is True
    assert diagnostics["missing_jurisdictions"] == []


def test_sibling_cities_are_not_treated_as_jurisdiction_equivalents():
    g = _load_generate()
    item = {
        "headline": "National Weather Service confirms EF0 tornado damaged homes in Port St. Lucie",
        "body": "The National Weather Service confirmed Monday that storm damage occurred in Fort Pierce.",
    }

    diagnostics = g._headline_lead_claim_diagnostics(item)

    assert diagnostics["passed"] is False
    assert diagnostics["missing_jurisdictions"] == ["port_st_lucie"]
    assert "headline_jurisdiction_missing_from_lead" in diagnostics["missing"]


def test_canonical_rebind_replaces_story_copy_atomically(monkeypatch, tmp_path):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    (tmp_path / "articles").mkdir(parents=True)
    slug = "canonical-crash-story"
    (tmp_path / "articles" / f"{slug}.html").write_text(
        '<div class="article-body"><p>An 86-year-old woman died after a Port St. Lucie crash.</p>'
        '<p>Police are investigating the collision.</p></div><div class="article-share">',
        encoding="utf-8",
    )
    item = {
        "headline": "Tornado damages homes in Port St. Lucie",
        "teaser": "A tornado damaged homes.",
        "body": "A tornado touched down and damaged several homes.",
        "category_key": "st_lucie",
        "link": "https://treasurecoast.today/articles/duplicate.html",
    }
    identity = {
        "canonical_slug": slug,
        "canonical_permalink": f"https://treasurecoast.today/articles/{slug}.html",
        "identity_basis": "persistent_story_id",
        "story_id": "story_crash",
        "canonical_entry": {
            "slug": slug,
            "headline": "86-year-old woman dies after Port St. Lucie intersection crash",
            "teaser": "An 86-year-old woman died after a Port St. Lucie crash.",
            "date": "2026-08-20",
            "editorial_story_id": "story_crash",
        },
    }

    changed = g._apply_final_canonical_surface_identity(item, identity)

    assert changed is True
    assert item["headline"] == identity["canonical_entry"]["headline"]
    assert "86-year-old woman died" in item["body"]
    assert "tornado" not in item["body"].lower()
    assert item["published"] == "2026-08-20"
    assert item["category_key"] == "st_lucie"
    assert item["_canonical_story_copy_atomic"] is True


def test_final_topic_integrity_removes_wrong_crime_hero_and_promotes_valid_card(monkeypatch, tmp_path):
    g = _load_generate()
    monkeypatch.setattr(g, "_category_contract_config", lambda key: {"mode": "enforce"})

    def assess(key, item):
        headline = (item.get("headline") or "").lower()
        if "tornado" in headline:
            return {"eligible": False, "reason": "missing_primary_crime_safety_focus", "positive_signals": [], "competing_signals": []}
        return {"eligible": True, "reason": "primary_crime_safety_focus_confirmed", "positive_signals": ["law_enforcement_crime:homicide"], "competing_signals": []}

    monkeypatch.setattr(g, "_category_eligibility_contract_assessment", assess)
    categories = [{
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "hero": {"headline": "National Weather Service confirms EF0 tornado in Port St. Lucie"},
        "cards": [{"headline": "Flock Safety cameras credited in Vero Beach homicide arrest"}],
    }]

    report = g.enforce_final_topic_category_integrity(categories, tmp_path)

    assert len(report["rejections"]) == 1
    assert categories[0]["hero"]["headline"].startswith("Flock Safety")
    assert categories[0]["hero"]["_hero_recovery_basis"] == "final_topic_integrity_surviving_card"


def test_fresh_official_confirmation_is_not_stale_without_current_weekday_literal():
    from datetime import datetime, timezone

    g = _load_generate()
    item = {
        "headline": "NWS confirms EF0 tornado with 75 mph winds touched down in Port St. Lucie Sunday",
        "teaser": "The National Weather Service confirmed the EF0 tornado after completing its damage survey.",
        "body": (
            "The National Weather Service confirmed an EF0 tornado with peak winds of 75 mph "
            "touched down in Port St. Lucie Sunday evening. The completed survey found a 2.1-mile path."
        ),
    }
    published = "Mon, 24 Aug 2026 20:23:50 GMT"
    now = datetime(2026, 8, 24, 23, 54, tzinfo=timezone.utc)

    assert g._category_story_is_stale(item, [], published_raw=published, now=now) is False


def test_fresh_timestamp_alone_cannot_revive_old_incident_without_new_official_development():
    from datetime import datetime, timezone

    g = _load_generate()
    source_url = "https://www.wptv.com/news/local/retouched-tornado-story"
    item = {
        "headline": "EF0 tornado touched down in Port St. Lucie Sunday",
        "teaser": "A tornado touched down Sunday evening in Port St. Lucie.",
        "body": "The tornado touched down Sunday evening and damaged fences in Port St. Lucie.",
        "source_url": source_url,
    }
    published = "Mon, 24 Aug 2026 20:23:50 GMT"
    now = datetime(2026, 8, 24, 23, 54, tzinfo=timezone.utc)
    archive = [{
        "headline": item["headline"],
        "source_url": source_url,
        "first_published": "2026-08-21T20:23:50+00:00",
    }]

    assert g._category_story_is_stale(item, archive, published_raw=published, now=now) is True
