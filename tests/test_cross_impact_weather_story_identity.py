"""Regression: a common flood is not one story across distinct consequences.

The Nov. 4 incident updated a school-closure / polling-place permalink
with a separate Jensen Beach residential-flooding story. The model reported
0.88 same-event confidence despite only 0.295 headline similarity.
"""
from __future__ import annotations

from tct_engine.semantic_publication_gate import (
    ACTION_NEW,
    ACTION_UPDATE,
    _is_cross_impact_weather_takeover,
    validate_model_decision,
)

SCHOOL = {
    "slug": "2026-11-03-martin-county-district-schools-closed-tuesday-after-school-activities-canceled",
    "headline": "Martin County flooding forces Election Day precinct move after school closures",
}
HOMES = {
    "headline": "Water rises in Jensen Beach homes as Martin County cannot pump out neighborhood",
}
CANDIDATE = {"slug": SCHOOL["slug"], "headline": SCHOOL["headline"], "article": SCHOOL}


def _model_vote():
    return {
        "selected_candidate_slug": SCHOOL["slug"],
        "same_real_world_event": True,
        "material_new_update": True,
        "independently_newsworthy_followup": False,
        "confidence": 0.88,
        "recommended_action": ACTION_UPDATE,
        "shared_anchors": ["Martin County flooding after the same storm"],
        "novel_facts": ["Neighborhood homes have standing water"],
        "reason": "Same storm and municipality",
    }


def test_school_closure_polling_place_article_cannot_be_taken_over_by_jensen_beach_homes():
    assert _is_cross_impact_weather_takeover(HOMES, SCHOOL)
    outcome = validate_model_decision(
        _model_vote(), [CANDIDATE], incoming=HOMES,
    )
    assert outcome["status"] == "validated"
    assert outcome["action"] == ACTION_NEW
    assert outcome["selected_candidate_slug"] == ""
    assert outcome["same_real_world_event"] is False
    assert "distinct_weather_impact_requires_independent_story" in outcome["consistency_repairs"]


def test_weather_impact_followup_for_same_school_closure_stays_updatable():
    incoming = {
        "headline": "Martin County schools to remain closed Wednesday as flooding continues"
    }
    assert not _is_cross_impact_weather_takeover(incoming, SCHOOL)
    outcome = validate_model_decision(_model_vote(), [CANDIDATE], incoming=incoming)
    assert outcome["action"] == ACTION_UPDATE


def test_residential_flooding_update_can_update_same_residential_story():
    original = {
        "slug": "jensen-beach-floods-homes",
        "headline": "Floodwaters enter Jensen Beach homes after heavy rain",
    }
    incoming = {"headline": "Water rises further inside Jensen Beach homes Wednesday"}
    assert not _is_cross_impact_weather_takeover(incoming, original)


def test_new_road_closure_is_not_folded_into_school_story():
    incoming = {"headline": "Flooded Martin County roads remain impassable"}
    assert _is_cross_impact_weather_takeover(incoming, SCHOOL)


def test_unrelated_storm_reports_without_distinct_recognized_subjects_are_not_forced():
    assert not _is_cross_impact_weather_takeover(
        {"headline": "Flash flood watch continues into Friday"},
        SCHOOL,
    )


def test_different_incident_families_outside_storm_context_still_use_existing_policy():
    election = {"headline": "Martin County moves Election Day polling place"}
    homes = {"headline": "Jensen Beach homes receive new property tax bills"}
    assert not _is_cross_impact_weather_takeover(homes, election)


def test_candidate_validation_without_incoming_remains_backwards_compatible():
    outcome = validate_model_decision(_model_vote(), [CANDIDATE])
    assert outcome["action"] == ACTION_UPDATE
