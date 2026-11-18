"""Different school-day operations deserve distinct canonical news stories.

Regression: Nov. 17, 2026 Indian River Wednesday normal operations were
incorrectly folded into the Nov. 16 Tuesday shortened-school-day story.
These cases also protect St. Lucie's early dismissal/next-day closure.
"""
from __future__ import annotations

import pytest

from tct_engine.semantic_material_update import validate_material_update
from tct_engine.semantic_publication_gate import (
    ACTION_DUPLICATE,
    ACTION_NEW,
    ACTION_UPDATE,
    _is_distinct_school_day_decision,
    _primary_school_operating_day,
    _prompt,
    _resolution_prompt,
    validate_model_decision,
)


TUESDAY = {
    "slug": "2026-11-16-indian-river-county-schools-modify-tuesday-schedule-ahead-of-heavy-rain-threat",
    "headline": "Indian River County schools modify Tuesday schedule ahead of heavy rain threat",
    "body": "The School District of Indian River County shortened the schedule Tuesday, Nov. 17.",
}
WEDNESDAY = {
    "headline": "Indian River County schools confirm normal Wednesday schedules after Tuesday rain changes",
    "teaser": "The school district confirmed that classes and Extended Day will follow regular hours Wednesday.",
    "body": "The School District of Indian River County will operate on regular schedules Wednesday, Nov. 18.",
}
CANDIDATES = [{"slug": TUESDAY["slug"], "article": TUESDAY}]


def vote(*, material=True, action=ACTION_UPDATE):
    return {
        "selected_candidate_slug": TUESDAY["slug"],
        "same_real_world_event": True,
        "material_new_update": material,
        "independently_newsworthy_followup": False,
        "confidence": 0.97,
        "recommended_action": action,
        "novel_facts": ["District confirmed its operating decision after assessing conditions"],
        "shared_anchors": ["Same school district and rain system"],
    }


def test_indian_river_tuesday_schedule_and_wednesday_normal_operations_are_separate():
    assert _primary_school_operating_day(TUESDAY) == "tuesday"
    assert _primary_school_operating_day(WEDNESDAY) == "wednesday"
    assert _is_distinct_school_day_decision(WEDNESDAY, TUESDAY)
    result = validate_model_decision(vote(), CANDIDATES, incoming=WEDNESDAY)
    assert result["status"] == "validated"
    assert result["action"] == ACTION_NEW
    assert result["same_real_world_event"] is False
    assert result["selected_candidate_slug"] == ""
    assert "different_school_operating_day_requires_independent_story" in result["consistency_repairs"]


def test_st_lucie_tuesday_dismissal_and_wednesday_closure_are_separate():
    tuesday = {
        "slug": "st-lucie-tuesday-early-dismissal",
        "headline": "St. Lucie Public Schools to dismiss early Tuesday ahead of rain",
    }
    wednesday = {
        "headline": "St. Lucie County public schools and offices to close Wednesday",
    }
    assert _is_distinct_school_day_decision(wednesday, tuesday)


@pytest.mark.parametrize("headline", [
    "Indian River County schools confirm normal Wednesday schedules after Tuesday rain changes",
    "St. Lucie County schools to close Wednesday after Tuesday early dismissal",
    "After Tuesday early dismissal, St. Lucie schools will close Wednesday",
])
def test_previous_day_in_background_does_not_override_primary_operating_day(headline):
    assert _primary_school_operating_day({"headline": headline}) == "wednesday"


def test_same_school_day_further_details_can_update_existing_story():
    wednesday = dict(WEDNESDAY, slug="indian-river-wednesday-normal")
    clarification = {
        "headline": "Indian River County schools confirm Wednesday Extended Day will operate normally",
    }
    assert not _is_distinct_school_day_decision(clarification, wednesday)
    result = validate_model_decision(
        dict(vote(), selected_candidate_slug=wednesday["slug"]),
        [{"slug": wednesday["slug"], "article": wednesday}],
        incoming=clarification,
    )
    assert result["action"] == ACTION_UPDATE


def test_repeat_announcement_about_tuesday_remains_duplicate():
    repeated = {"headline": "Indian River schools modify Tuesday schedule as heavy rain approaches"}
    assert not _is_distinct_school_day_decision(repeated, TUESDAY)
    result = validate_model_decision(
        vote(material=False, action=ACTION_DUPLICATE),
        CANDIDATES,
        incoming=repeated,
    )
    assert result["action"] == ACTION_DUPLICATE


def test_school_headline_without_weekday_can_use_unambiguous_lead():
    original = {
        "headline": "St. Lucie schools release students early",
        "teaser": "St. Lucie schools are dismissing students two hours early Tuesday.",
    }
    assert _primary_school_operating_day(original) == "tuesday"
    assert _is_distinct_school_day_decision(
        {"headline": "St. Lucie schools close Wednesday"}, original
    )


def test_ambiguous_school_day_or_non_school_story_is_not_force_split():
    ambiguous = {
        "headline": "Martin County schools change Tuesday and Wednesday schedules because of storms"
    }
    non_school = {"headline": "Fort Pierce roads closed Tuesday due to flooding"}
    assert _primary_school_operating_day(ambiguous) == ""
    assert not _is_distinct_school_day_decision(WEDNESDAY, ambiguous)
    assert not _is_distinct_school_day_decision(
        {"headline": "Fort Pierce roads remain closed Wednesday"}, non_school
    )


def test_material_update_composer_cannot_overwrite_tuesday_story_with_wednesday():
    payload = {
        "headline": WEDNESDAY["headline"],
        "teaser": WEDNESDAY["teaser"],
        "body": WEDNESDAY["body"],
    }
    result = validate_material_update(
        payload, canonical=TUESDAY, incoming=WEDNESDAY, decision=vote(),
    )
    assert "different_school_operating_day_not_same_canonical_event" in result["validation_errors"]


def test_semantic_prompts_explicitly_protect_distinct_school_days():
    initial = _prompt(WEDNESDAY, CANDIDATES)
    second = _resolution_prompt(WEDNESDAY, CANDIDATES, vote())
    assert "DIFFERENT SCHOOL DAY" in initial
    assert "distinct operating days" in second
