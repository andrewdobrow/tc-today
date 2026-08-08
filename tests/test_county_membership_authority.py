from __future__ import annotations

import importlib
import json
import os
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest


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


def _source_entry(source_headline, source_text, source_url, **updates):
    item = {
        "slug": "fixture",
        "headline": source_headline,
        "teaser": "Generated TCT teaser.",
        "body": "Generated TCT body.",
        "category_key": "business",
        "category_keys": ["business"],
        "county_keys": [],
        "source_headline": source_headline,
        "source_title": source_headline,
        "article_text": source_text,
        "source_url": source_url,
        "event_identity": {
            "origin": "source_derived",
            "source_headline": source_headline,
            "source_url": source_url,
            "locality": [],
        },
    }
    item.update(updates)
    return item


def test_generated_copy_cannot_self_authorize_martin_county():
    generate = _load_generate()
    item = _source_entry(
        "Extreme heat is fueling a countywide push for more trees and shade in Palm Beach County",
        "Palm Beach County cities are considering tree canopy and shade policies near Lake Worth.",
        "https://www.wptv.com/news/palm-beach-county/extreme-heat-trees-shade",
        headline="Martin County leaders push for more shade as extreme heat bakes neighborhoods",
        teaser="Martin County communities are considering more trees.",
        body="Officials in Martin County are discussing shade and tree canopy policy.",
        category_keys=["business", "martin"],
        county_keys=["martin"],
    )
    assessment = generate._county_membership_authority_assessment(item, "business")
    assert "martin" not in assessment["supported_counties"]
    assert "martin" in assessment["rejected_memberships"]
    assert any(row["county"] == "palm_beach" for row in assessment["conflicting_counties"])
    assert "martin" not in generate._item_category_memberships(item, "business")


def test_exact_palm_beach_heat_archive_membership_is_repaired(tmp_path: Path):
    generate = _load_generate()
    bad = {
        "slug": "2026-08-05-palm-beach-county-cities-push-for-more-trees-and-shade-as-extreme-heat-bakes-nei",
        "headline": "Palm Beach County cities push for more trees and shade as extreme heat bakes neighborhoods",
        "teaser": "Cities are considering more shade as heat intensifies.",
        "body": "The generated article mentions Martin County in a broader regional sentence.",
        "category_key": "business",
        "category_keys": ["business", "martin"],
        "county_keys": ["martin"],
        "source_url": "https://www.wptv.com/news/palm-beach-county/extreme-heat-is-fueling-a-countywide-push-for-more-trees-and-shade-in-palm-beach-county",
        "source_headline": "Extreme heat is fueling a countywide push for more trees and shade in Palm Beach County",
        "article_text": "Palm Beach County municipalities are considering trees and shade as extreme heat grows.",
        "event_identity": {
            "origin": "source_derived",
            "source_headline": "Extreme heat is fueling a countywide push for more trees and shade in Palm Beach County",
            "source_url": "https://www.wptv.com/news/palm-beach-county/extreme-heat-is-fueling-a-countywide-push-for-more-trees-and-shade-in-palm-beach-county",
            "locality": ["lake-worth", "palm-beach-county"],
        },
    }
    archive, report = generate._backfill_archive_category_memberships([bad], tmp_path)
    assert archive[0]["category_keys"] == ["business"]
    assert archive[0]["county_keys"] == []
    assert report["records_repaired"] == 1
    assert report["passed"] is True

    authority = json.loads(
        (tmp_path / "data" / "county-membership-authority-report.json").read_text(encoding="utf-8")
    )
    assert authority["contract_version"] == generate.COUNTY_MEMBERSHIP_AUTHORITY_VERSION
    assert authority["summary"]["archive_rows_repaired"] == 1
    assert authority["archive_repairs"][0]["removed_county_memberships"] == ["martin"]


@pytest.mark.parametrize(
    ("county_key", "headline", "source_text", "url"),
    [
        (
            "martin",
            "Martin County commissioners approve Indiantown road project",
            "Martin County commissioners approved a road project near Indiantown.",
            "https://publisher.example/martin-county/road-project",
        ),
        (
            "st_lucie",
            "Fort Pierce hotel project advances in St. Lucie County",
            "The Fort Pierce project is in St. Lucie County.",
            "https://publisher.example/st-lucie-county/hotel-project",
        ),
        (
            "indian_river",
            "Vero Beach redevelopment proposal heads to review",
            "The project in Vero Beach would redevelop a commercial property in Indian River County.",
            "https://publisher.example/indian-river-county/redevelopment",
        ),
    ],
)
def test_source_evidence_authorizes_each_treasure_coast_county(
    county_key, headline, source_text, url
):
    generate = _load_generate()
    item = _source_entry(headline, source_text, url)
    assessment = generate._county_membership_authority_assessment(item)
    assert county_key in assessment["supported_counties"]


def test_legitimate_multi_county_source_preserves_both_memberships():
    generate = _load_generate()
    item = _source_entry(
        "New employer plans facilities in Martin and St. Lucie counties",
        "The company plans one facility in Martin County and another in St. Lucie County.",
        "https://publisher.example/treasure-coast/two-county-expansion",
        category_keys=["business", "martin", "st_lucie"],
        county_keys=["martin", "st_lucie"],
    )
    memberships = generate._item_category_memberships(item, "business")
    assert memberships == ["business", "martin", "st_lucie"]


def test_classifier_county_label_cannot_bypass_source_authority():
    generate = _load_generate()
    item = _source_entry(
        "Palm Beach County cities consider heat mitigation",
        "Palm Beach County officials discussed tree canopy near West Palm Beach.",
        "https://publisher.example/palm-beach-county/heat",
    )
    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {
            item["source_title"].lower(): {"business", "martin"}
        }
        memberships = generate._item_category_memberships(item, "business")
    finally:
        generate.STORY_CLASSIFICATION = previous
    assert "business" in memberships
    assert "martin" not in memberships


def test_conflicting_outside_county_blocks_dedicated_feed_without_local_evidence():
    generate = _load_generate()
    item = _source_entry(
        "Palm Beach County heat policy expands",
        "Officials in Palm Beach County and West Palm Beach discussed shade.",
        "https://publisher.example/palm-beach-county/heat",
        feed_url="https://www.wptv.com/news/region-martin-county.rss",
        category_keys=["business", "martin"],
        county_keys=["martin"],
    )
    assessment = generate._county_membership_authority_assessment(item)
    assert "martin" not in assessment["supported_counties"]


def test_final_live_county_gate_fails_closed_on_contaminated_placement(tmp_path: Path):
    generate = _load_generate()
    bad = _source_entry(
        "Palm Beach County cities consider heat mitigation",
        "Palm Beach County officials discussed shade near West Palm Beach.",
        "https://publisher.example/palm-beach-county/heat",
        category_key="business",
        category_keys=["business", "martin"],
        county_keys=["martin"],
    )
    categories = [{
        "category_key": "martin",
        "category_label": "Martin County",
        "hero": deepcopy(bad),
        "cards": [],
    }]
    with pytest.raises(RuntimeError, match="County membership authority contract FAILED"):
        generate.validate_live_county_membership_authority(categories, output_root=tmp_path)

    report = json.loads(
        (tmp_path / "data" / "county-membership-authority-report.json").read_text(encoding="utf-8")
    )
    assert report["live_projection"]["passed"] is False
    assert report["live_projection"]["rejected_placements"] >= 1


def test_county_authority_version_invalidates_only_county_cache(monkeypatch):
    generate = _load_generate()
    source = {
        "title": "Martin County project advances",
        "summary": "Martin County officials reviewed a project.",
        "article_text": "Martin County officials reviewed a project.",
        "source_quality": "full",
        "link": "https://publisher.example/martin/project",
    }
    county_before = generate._category_generation_cache_key("martin", [source])
    sports_before = generate._category_generation_cache_key("sports", [source])
    monkeypatch.setattr(
        generate,
        "COUNTY_MEMBERSHIP_AUTHORITY_VERSION",
        generate.COUNTY_MEMBERSHIP_AUTHORITY_VERSION + "-changed",
    )
    county_after = generate._category_generation_cache_key("martin", [source])
    sports_after = generate._category_generation_cache_key("sports", [source])
    assert county_before != county_after
    assert sports_before == sports_after


def test_legacy_archive_county_membership_without_source_provenance_is_preserved(tmp_path: Path):
    generate = _load_generate()
    legacy = {
        "slug": "2026-06-01-fort-pierce-road-project-advances",
        "headline": "Fort Pierce road project advances",
        "teaser": "Officials approved the next phase.",
        "body": "The project will move forward after a public meeting.",
        "category_key": "st_lucie",
        "category_keys": ["st_lucie", "local_gov"],
        "county_keys": ["st_lucie"],
        # Older archive rows did not persist source provenance.
        "source_url": "",
        "source_headline": "",
        "article_text": "",
    }

    archive, report = generate._backfill_archive_category_memberships([legacy], tmp_path)

    assert "st_lucie" in archive[0]["category_keys"]
    assert archive[0]["county_keys"] == ["st_lucie"]
    marker = archive[0]["county_membership_authority"]
    assert marker["origin"] == generate.COUNTY_LEGACY_ARCHIVE_AUTHORITY_ORIGIN
    assert marker["migration_only"] is True
    assert report["records_repaired"] == 0
    authority_report = json.loads(
        (tmp_path / "data" / "county-membership-authority-report.json").read_text(encoding="utf-8")
    )
    assert authority_report["summary"]["legacy_archive_rows_preserved"] == 1


def test_legacy_archive_marker_cannot_override_conflicting_source_evidence():
    generate = _load_generate()
    item = _source_entry(
        "Palm Beach County cities expand heat mitigation program",
        "Palm Beach County and West Palm Beach officials approved the program.",
        "https://publisher.example/palm-beach-county/heat-program",
        category_keys=["business", "martin"],
        county_keys=["martin"],
        county_membership_authority={
            "origin": generate.COUNTY_LEGACY_ARCHIVE_AUTHORITY_ORIGIN,
            "contract_version": generate.COUNTY_MEMBERSHIP_AUTHORITY_VERSION,
            "counties": ["martin"],
            "migration_only": True,
        },
    )

    assessment = generate._county_membership_authority_assessment(item, "business")

    assert "martin" not in assessment["supported_counties"]
    assert any(row["county"] == "palm_beach" for row in assessment["conflicting_counties"])
    assert "martin" not in generate._item_category_memberships(item, "business")


def test_archive_recovery_preserves_legacy_county_authority_marker(tmp_path: Path, monkeypatch):
    """Regression for the Aug. 7 production crash after archive recovery.

    A legacy row can be valid only because archive migration stamped the conservative
    migration-only county marker. Projecting that row back to a live county surface
    must carry the marker with it or the final live gate will reject the recovered row.
    """
    generate = _load_generate()
    marker = {
        "origin": generate.COUNTY_LEGACY_ARCHIVE_AUTHORITY_ORIGIN,
        "contract_version": generate.COUNTY_MEMBERSHIP_AUTHORITY_VERSION,
        "counties": ["indian_river"],
        "migration_only": True,
    }
    legacy = {
        "slug": "2026-06-15-vero-beach-project-advances",
        "headline": "Vero Beach project advances",
        "teaser": "Indian River County officials moved the Vero Beach project forward.",
        "body": "Indian River County officials moved the Vero Beach project forward after reviewing the next phase. The project remains under local review.",
        "category_key": "indian_river",
        "category_keys": ["indian_river"],
        "county_keys": ["indian_river"],
        "source_url": "",
        "source_headline": "",
        "article_text": "",
        "article_word_count": 200,
        "article_paragraph_count": 3,
        "date": "2026-06-15",
        "lastmod": "2026-06-15",
        "county_membership_authority": marker,
        "ranking_eligible": True,
    }
    (tmp_path / "archive.json").write_text(json.dumps([legacy]), encoding="utf-8")
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(generate, "get_fallback_image", lambda *args, **kwargs: ("", ""))
    monkeypatch.setattr(
        generate,
        "_sanitize_authoritative_custom_archive",
        lambda archive, articles_dir: archive,
    )
    monkeypatch.setattr(
        generate,
        "_backfill_archive_editorial_story_ids",
        lambda archive, index, output_root=None: (archive, {}),
    )
    monkeypatch.setattr(generate, "_load_publication_identity_index", lambda: {})

    categories = [{
        "category_key": "indian_river",
        "category_label": "Indian River County",
        "hero": None,
        "cards": [],
    }]
    generate.ensure_all_category_sections(categories, min_cards=0)
    recovered = next(c for c in categories if c["category_key"] == "indian_river")["hero"]

    assert recovered["headline"] == legacy["headline"]
    assert recovered["county_membership_authority"] == marker
    assessment = generate._county_membership_authority_assessment(recovered, "indian_river")
    assert "indian_river" in assessment["supported_counties"]
    result = generate.validate_live_county_membership_authority(
        categories, output_root=tmp_path
    )
    assert result["passed"] is True


def test_canonical_rebind_carries_persisted_county_authority_provenance():
    generate = _load_generate()
    marker = {
        "origin": generate.COUNTY_LEGACY_ARCHIVE_AUTHORITY_ORIGIN,
        "contract_version": generate.COUNTY_MEMBERSHIP_AUTHORITY_VERSION,
        "counties": ["st_lucie"],
        "migration_only": True,
    }
    item = {
        "headline": "Temporary duplicate headline",
        "category_key": "st_lucie",
        "category_keys": ["st_lucie"],
        "county_keys": ["st_lucie"],
        "link": "https://treasurecoast.today/articles/duplicate.html",
    }
    identity = {
        "canonical_slug": "2026-06-01-fort-pierce-project",
        "canonical_permalink": "https://treasurecoast.today/articles/2026-06-01-fort-pierce-project.html",
        "identity_basis": "persistent_story_id",
        "story_id": "story_fixture",
        "canonical_entry": {
            "headline": "Fort Pierce project moves forward",
            "teaser": "The project advanced.",
            "source_url": "",
            "source_headline": "",
            "article_text": "",
            "county_membership_authority": marker,
            "editorial_story_id": "story_fixture",
        },
    }

    changed = generate._apply_final_canonical_surface_identity(item, identity)

    assert changed is True
    assert item["county_membership_authority"] == marker
    assessment = generate._county_membership_authority_assessment(item, "st_lucie")
    assert "st_lucie" in assessment["supported_counties"]
