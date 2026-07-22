import pytest

from tct_engine import (
    EditorialAction,
    EditorialDecisionInput,
    UpdateClassification,
    decide_editorial_action,
)


def make_input(
    *,
    has_existing_story: bool = True,
    existing_is_custom: bool = False,
    incoming_is_custom: bool = False,
    update_classification: UpdateClassification = (
        UpdateClassification.NO_CHANGE
    ),
    event_match_confirmed: bool = True,
) -> EditorialDecisionInput:
    return EditorialDecisionInput(
        has_existing_story=has_existing_story,
        existing_is_custom=existing_is_custom,
        incoming_is_custom=incoming_is_custom,
        update_classification=update_classification,
        event_match_confirmed=event_match_confirmed,
    )


def test_first_story_for_event_is_published():
    decision = decide_editorial_action(
        make_input(
            has_existing_story=False,
            event_match_confirmed=True,
        )
    )

    assert decision.action is EditorialAction.PUBLISH_NEW
    assert decision.reason == "No existing story covers this event."


def test_uncertain_event_match_is_held_for_review():
    decision = decide_editorial_action(
        make_input(
            has_existing_story=True,
            event_match_confirmed=False,
        )
    )

    assert decision.action is EditorialAction.HOLD_FOR_REVIEW


def test_custom_story_replaces_external_canonical_story():
    decision = decide_editorial_action(
        make_input(
            existing_is_custom=False,
            incoming_is_custom=True,
            update_classification=UpdateClassification.UPDATE,
        )
    )

    assert decision.action is EditorialAction.REPLACE_CANONICAL
    assert decision.canonical_should_change is True


def test_external_duplicate_is_ignored_when_custom_story_exists():
    decision = decide_editorial_action(
        make_input(
            existing_is_custom=True,
            incoming_is_custom=False,
            update_classification=UpdateClassification.NO_CHANGE,
        )
    )

    assert decision.action is EditorialAction.IGNORE
    assert decision.canonical_should_change is False


@pytest.mark.parametrize(
    "classification",
    [
        UpdateClassification.UPDATE,
        UpdateClassification.MAJOR_UPDATE,
        UpdateClassification.CORRECTION,
    ],
)
def test_external_new_information_updates_existing_custom_story(
    classification,
):
    decision = decide_editorial_action(
        make_input(
            existing_is_custom=True,
            incoming_is_custom=False,
            update_classification=classification,
        )
    )

    assert decision.action is EditorialAction.UPDATE_EXISTING
    assert decision.canonical_should_change is False


def test_external_duplicate_is_ignored_when_external_story_exists():
    decision = decide_editorial_action(
        make_input(
            existing_is_custom=False,
            incoming_is_custom=False,
            update_classification=UpdateClassification.NO_CHANGE,
        )
    )

    assert decision.action is EditorialAction.IGNORE


def test_external_new_information_updates_existing_external_story():
    decision = decide_editorial_action(
        make_input(
            existing_is_custom=False,
            incoming_is_custom=False,
            update_classification=UpdateClassification.UPDATE,
        )
    )

    assert decision.action is EditorialAction.UPDATE_EXISTING
    assert decision.canonical_should_change is False


def test_new_custom_story_is_published_when_event_has_no_story():
    decision = decide_editorial_action(
        make_input(
            has_existing_story=False,
            incoming_is_custom=True,
        )
    )

    assert decision.action is EditorialAction.PUBLISH_NEW


def test_existing_custom_story_is_not_replaced_by_another_custom_duplicate():
    decision = decide_editorial_action(
        make_input(
            existing_is_custom=True,
            incoming_is_custom=True,
            update_classification=UpdateClassification.NO_CHANGE,
        )
    )

    assert decision.action is EditorialAction.IGNORE
    assert decision.canonical_should_change is False