from datetime import datetime, timezone

import pytest

from tct_engine import (
    CanonicalStoryManager,
    StoryCandidate,
    select_canonical_story,
)


EVENT_KEY = "martin-county-cat-hoarding"


def make_candidate(
    article_id: str,
    *,
    source: str,
    hour: int,
    is_custom: bool = False,
    event_key: str = EVENT_KEY,
) -> StoryCandidate:
    return StoryCandidate(
        article_id=article_id,
        event_key=event_key,
        title="Deputies rescue cats from Martin County home",
        source=source,
        url=f"https://example.com/{article_id}",
        is_custom=is_custom,
        published_at=datetime(
            2026,
            7,
            20,
            hour,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_custom_tct_story_beats_earlier_external_story():
    external = make_candidate(
        "wptv-1",
        source="WPTV",
        hour=8,
    )

    custom = make_candidate(
        "tct-custom-1",
        source="Treasure Coast Today",
        hour=10,
        is_custom=True,
    )

    result = select_canonical_story([external, custom])

    assert result.canonical.article_id == "tct-custom-1"
    assert result.supporting == (external,)


def test_earliest_external_story_wins_without_custom_story():
    first = make_candidate(
        "wptv-1",
        source="WPTV",
        hour=8,
    )

    second = make_candidate(
        "tcpalm-1",
        source="TCPalm",
        hour=9,
    )

    result = select_canonical_story([second, first])

    assert result.canonical.article_id == "wptv-1"
    assert result.supporting == (second,)


def test_later_custom_story_replaces_external_canonical():
    manager = CanonicalStoryManager()

    first_result = manager.add(
        make_candidate(
            "external-1",
            source="WPTV",
            hour=8,
        )
    )

    assert first_result.canonical.article_id == "external-1"

    second_result = manager.add(
        make_candidate(
            "custom-1",
            source="Treasure Coast Today",
            hour=10,
            is_custom=True,
        )
    )

    assert second_result.canonical.article_id == "custom-1"
    assert second_result.supporting[0].article_id == "external-1"


def test_external_update_does_not_replace_custom_story():
    manager = CanonicalStoryManager()

    manager.add(
        make_candidate(
            "custom-1",
            source="Treasure Coast Today",
            hour=8,
            is_custom=True,
        )
    )

    result = manager.add(
        make_candidate(
            "sheriff-update",
            source="Martin County Sheriff's Office",
            hour=11,
        )
    )

    assert result.canonical.article_id == "custom-1"
    assert result.supporting[0].article_id == "sheriff-update"


def test_candidates_from_different_events_are_rejected():
    first = make_candidate(
        "story-1",
        source="WPTV",
        hour=8,
    )

    second = make_candidate(
        "story-2",
        source="TCPalm",
        hour=9,
        event_key="unrelated-event",
    )

    with pytest.raises(
        ValueError,
        match="same event",
    ):
        select_canonical_story([first, second])


def test_empty_candidate_collection_is_rejected():
    with pytest.raises(
        ValueError,
        match="At least one",
    ):
        select_canonical_story([])


def test_manager_keeps_different_events_separate():
    manager = CanonicalStoryManager()

    manager.add(
        make_candidate(
            "cat-story",
            source="WPTV",
            hour=8,
        )
    )

    manager.add(
        make_candidate(
            "crash-story",
            source="TCPalm",
            hour=9,
            event_key="us-1-fatal-crash",
        )
    )

    assert len(manager.all()) == 2
    assert manager.get(EVENT_KEY).canonical.article_id == "cat-story"
    assert (
        manager.get("us-1-fatal-crash").canonical.article_id
        == "crash-story"
    )