from __future__ import annotations

import importlib
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


def _custom_canonical(g):
    return {
        "slug": g.HOARDING_CANONICAL_SLUG,
        "headline": "More Than 70 Animals Found in Stuart Home During Large-Scale Hoarding Response",
        "teaser": "Authorities rescued dozens of cats and dogs from a Stuart home.",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:hoarding",
    }


def _friday_feed_update():
    return {
        "headline": "100 animals rescued in worst hoarding case Martin County has seen, owners search for missing pets",
        "teaser": "The total reached 100 after 83 cats and 17 dogs were rescued.",
        "body": "On Monday authorities removed 80 cats and 12 dogs. More animals were later rescued.",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/more-animals-rescued-in-martin-county-hoarding-case-as-owners-search-for-missing-pets",
        "enriched": True,
    }


def test_known_event_key_accepts_later_100_animal_count():
    g = _load_generate()
    assert g._known_event_key("100 animals rescued in Martin County's worst hoarding case") == (
        "2026-07-stuart-martin-animal-hoarding"
    )


def test_live_custom_incident_lock_removes_cross_category_copies():
    g = _load_generate()
    custom = _custom_canonical(g)
    crime_copy = _friday_feed_update()
    martin_copy = dict(crime_copy)
    categories = [
        {"category_key": "crime", "hero": crime_copy, "cards": [{"headline": "Other crime story"}]},
        {"category_key": "martin", "hero": {"headline": "Other Martin story"}, "cards": [martin_copy]},
    ]
    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[custom], current_customs=[]
    )
    assert len(removed) == 2
    assert categories[0]["hero"]["headline"] == "Other crime story"
    assert categories[1]["cards"] == []
    assert all(row["canonical_slug"] == g.HOARDING_CANONICAL_SLUG for row in removed)


def test_publication_lock_finds_authoritative_custom_independent_of_stage():
    g = _load_generate()
    custom = _custom_canonical(g)
    match, confidence, basis = g._find_authoritative_custom_incident_match(
        _friday_feed_update(), archived_customs=[custom], current_customs=[]
    )
    assert match["slug"] == g.HOARDING_CANONICAL_SLUG
    assert confidence == 100
    assert basis == "exact_known_event_key"


def test_same_run_canonical_cleanup_redirects_july_25_duplicate(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    duplicate_slug = (
        "2026-07-25-100-animals-rescued-in-worst-hoarding-case-"
        "martin-county-has-seen-owners-search"
    )
    archive = [
        _custom_canonical(g),
        {
            "slug": duplicate_slug,
            **_friday_feed_update(),
            "editorial_story_id": "story-generated-follow-up",
        },
    ]
    cleaned, redirects = g.apply_canonical_story_cleanup(archive, articles, tmp_path)
    assert [row["slug"] for row in cleaned] == [g.HOARDING_CANONICAL_SLUG]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate_slug)
    assert redirect["target_slug"] == g.HOARDING_CANONICAL_SLUG
    assert redirect["canonical_is_custom"] is True


def test_unrelated_animal_story_survives_custom_incident_lock():
    g = _load_generate()
    custom = _custom_canonical(g)
    categories = [{
        "category_key": "crime",
        "hero": {
            "headline": "Three dogs rescued after being abandoned near I-95 in Martin County",
            "body": "The animals were found beside Bridge Road.",
        },
        "cards": [],
    }]
    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[custom], current_customs=[]
    )
    assert removed == []
    assert categories[0]["hero"] is not None


def _debevec_custom_canonical(g):
    return {
        "slug": "2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach",
        "headline": "Martin County Sheriff's Office searches for missing Oklahoma visitor last seen at Chastain Beach",
        "teaser": "Deputies are searching for Michael Anthony Debevec II after he was last seen at Chastain Beach.",
        "body": "Michael Anthony Debevec II was reported missing after visiting Chastain Beach in Martin County.",
        "category_key": "martin",
        "category_keys": ["martin", "crime"],
        "county_keys": ["martin"],
        "date": "2026-08-29",
        "first_published": "Sat, 29 Aug 2026 21:48:09 -0400",
        "is_custom": True,
        "authoritative_custom": True,
        "incident_anchor_key": "missing-person:michael-debevec",
        "durable_custom_identity_key": "missing-person|michael-debevec",
        "editorial_story_id": "custom:debevec",
    }


def _validated_debevec_generated_update(g, canonical, headline):
    decision = {
        "status": "validated",
        "action": g.SEMANTIC_ACTION_UPDATE,
        "recommended_action": g.SEMANTIC_ACTION_UPDATE,
        "selected_candidate_slug": canonical["slug"],
        "same_real_world_event": True,
        "material_new_update": True,
        "confidence": 0.99,
        "shared_anchors": ["Michael Anthony Debevec II", "Chastain Beach"],
        "novel_facts": ["A body believed to be Debevec was recovered near the House of Refuge"],
        "reason": "The body recovery is a major development in the existing missing-person case.",
        "validation_errors": [],
    }
    item = {
        "headline": headline,
        "source_headline": "Martin County Sheriff's Office investigates body found in Hutchinson Island mangroves",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/martin-county-sheriffs-office-investigates-body-found-in-hutchinson-island-mangroves",
        "body": (
            "A body was recovered in mangroves near the House of Refuge during the search for "
            "Michael Anthony Debevec II. Investigators said the clothing matched what Debevec "
            "was believed to be wearing, while formal identification remained pending."
        ),
        "editorial_story_id": canonical["editorial_story_id"],
        "_editorial_story_id": canonical["editorial_story_id"],
        "_editorial_route": "update_existing",
        "editorial_route": "update_existing",
        "story_form": "update",
        "_semantic_material_update": True,
        "_semantic_material_update_decision": decision,
        "_pre_generation_material_update_promotion": True,
        "_pre_generation_material_update_canonical_slug": canonical["slug"],
        "canonical_slug": canonical["slug"],
        "_protected_material_update": True,
    }
    g._stamp_canonical_write_authorization(
        item,
        canonical,
        {
            "outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "identity_outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "evidence_tier": "known_canonical_plus_semantic_materiality",
            "write_authorized": True,
            "proof_type": "published_skip_canonical_plus_semantic_materiality",
            "reason": "Major body-recovery development.",
            "reason_codes": ["semantic_material_update_validated"],
        },
        basis="pre_generation_material_update_promotion",
    )
    return item


def test_authoritative_custom_incident_lock_preserves_target_bound_debevec_material_update():
    """2026-09-01 regression: custom lock must not erase a pending canonical update transaction."""
    g = _load_generate()
    canonical = _debevec_custom_canonical(g)
    crime = _validated_debevec_generated_update(
        g, canonical,
        "Body found in Hutchinson Island mangroves believed to be missing Port St. Lucie man",
    )
    martin = _validated_debevec_generated_update(
        g, canonical,
        "Martin County Sheriff's Office finds body believed to be missing Michael Debevec",
    )
    categories = [
        {"category_key": "crime", "hero": crime, "cards": []},
        {"category_key": "martin", "hero": martin, "cards": []},
    ]

    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[canonical], current_customs=[]
    )

    assert removed == []
    assert categories[0]["hero"] is crime
    assert categories[1]["hero"] is martin
    assert g._has_target_bound_pre_generation_material_update_authority(crime, canonical)
    assert g._has_target_bound_pre_generation_material_update_authority(martin, canonical)


def test_authoritative_custom_incident_lock_still_removes_unapproved_debevec_reprint():
    g = _load_generate()
    canonical = _debevec_custom_canonical(g)
    ordinary = {
        "headline": "Body found in Hutchinson Island mangroves believed to be missing Michael Debevec",
        "body": "Deputies found a body during the search for Michael Anthony Debevec II near Chastain Beach.",
        "source_url": "https://example.com/unapproved-reprint",
        "incident_anchor_key": "missing-person:michael-debevec",
    }
    categories = [{"category_key": "martin", "hero": ordinary, "cards": []}]

    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[canonical], current_customs=[]
    )

    assert len(removed) == 1
    assert categories[0]["hero"] is None
