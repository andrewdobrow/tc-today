import pytest

from tct_engine import (
    IncomingStoryUpdate,
    StorySnapshot,
    UpdateClassification,
    evaluate_story_update,
)


EVENT_KEY = "us-1-fatal-crash"


def test_identical_information_produces_no_change():
    current = StorySnapshot(
        event_key=EVENT_KEY,
        facts=(
            "A crash occurred on U.S. 1.",
            "Two northbound lanes are closed.",
        ),
        status="developing",
    )

    incoming = IncomingStoryUpdate(
        event_key=EVENT_KEY,
        facts=(
            "A crash occurred on U.S. 1.",
            "Two northbound lanes are closed.",
        ),
        status="developing",
    )

    result = evaluate_story_update(current, incoming)

    assert result.classification is UpdateClassification.NO_CHANGE
    assert result.new_facts == ()
    assert result.status_changed is False


def test_new_fact_produces_standard_update():
    current = StorySnapshot(
        event_key=EVENT_KEY,
        facts=("A crash occurred on U.S. 1.",),
        status="developing",
    )

    incoming = IncomingStoryUpdate(
        event_key=EVENT_KEY,
        facts=(
            "A crash occurred on U.S. 1.",
            "One person was taken to the hospital.",
        ),
    )

    result = evaluate_story_update(current, incoming)

    assert result.classification is UpdateClassification.UPDATE
    assert result.new_facts == (
        "One person was taken to the hospital.",
    )


def test_fact_comparison_ignores_whitespace_and_case():
    current = StorySnapshot(
        event_key=EVENT_KEY,
        facts=("The Road Is Closed.",),
    )

    incoming = IncomingStoryUpdate(
        event_key=EVENT_KEY,
        facts=("  the road is closed.  ",),
    )

    result = evaluate_story_update(current, incoming)

    assert result.classification is UpdateClassification.NO_CHANGE
    assert result.new_facts == ()


def test_status_change_produces_update_without_new_facts():
    current = StorySnapshot(
        event_key=EVENT_KEY,
        facts=("The road is closed.",),
        status="developing",
    )

    incoming = IncomingStoryUpdate(
        event_key=EVENT_KEY,
        facts=("The road is closed.",),
        status="resolved",
    )

    result = evaluate_story_update(current, incoming)

    assert result.classification is UpdateClassification.UPDATE
    assert result.new_facts == ()
    assert result.status_changed is True
    assert result.previous_status == "developing"
    assert result.new_status == "resolved"


def test_major_update_is_preserved_in_decision():
    current = StorySnapshot(
        event_key=EVENT_KEY,
        facts=("One person was injured.",),
    )

    incoming = IncomingStoryUpdate(
        event_key=EVENT_KEY,
        facts=(
            "One person was injured.",
            "The victim later died at the hospital.",
        ),
        is_major=True,
    )

    result = evaluate_story_update(current, incoming)

    assert result.classification is UpdateClassification.MAJOR_UPDATE
    assert result.new_facts == (
        "The victim later died at the hospital.",
    )


def test_correction_outranks_major_update():
    current = StorySnapshot(
        event_key=EVENT_KEY,
        facts=("Three vehicles were involved.",),
    )

    incoming = IncomingStoryUpdate(
        event_key=EVENT_KEY,
        facts=("Two vehicles were involved.",),
        is_major=True,
        is_correction=True,
    )

    result = evaluate_story_update(current, incoming)

    assert result.classification is UpdateClassification.CORRECTION
    assert result.new_facts == ("Two vehicles were involved.",)


def test_updates_from_different_events_are_rejected():
    current = StorySnapshot(
        event_key=EVENT_KEY,
        facts=("The road is closed.",),
    )

    incoming = IncomingStoryUpdate(
        event_key="martin-county-cat-hoarding",
        facts=("Deputies removed dozens of cats.",),
    )

    with pytest.raises(ValueError, match="same event"):
        evaluate_story_update(current, incoming)