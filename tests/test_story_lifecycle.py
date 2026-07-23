from datetime import datetime, timedelta, timezone

from tct_engine.story_lifecycle import StoryLifecycleState, classify_story_lifecycle


NOW = datetime(2026, 7, 23, 18, 0, tzinfo=timezone.utc)


def _timeline(hours_ago: int, event_key: str = "evt-1") -> list[dict]:
    return [{
        "event_key": event_key,
        "article_id": event_key,
        "published_at": (NOW - timedelta(hours=hours_ago)).isoformat(),
        "title": "Update",
        "source": "WPTV",
    }]


def test_breaking_story_is_breaking_while_current():
    result = classify_story_lifecycle(
        {"events": ["evt-1"], "timeline": _timeline(2), "importance": {"level": "breaking"}},
        reference_time=NOW,
    )
    assert result.state is StoryLifecycleState.BREAKING
    assert result.hours_since_update == 2.0


def test_multi_event_story_is_developing():
    result = classify_story_lifecycle(
        {"events": ["evt-1", "evt-2"], "timeline": _timeline(8), "importance": {"level": "high"}},
        reference_time=NOW,
    )
    assert result.state is StoryLifecycleState.DEVELOPING


def test_follow_up_relationship_marks_story_developing():
    result = classify_story_lifecycle(
        {
            "events": ["evt-1"],
            "timeline": _timeline(12),
            "relationship_history": [{"relationship": "follow_up"}],
            "importance": {"level": "normal"},
        },
        reference_time=NOW,
    )
    assert result.state is StoryLifecycleState.DEVELOPING


def test_explicit_resolution_language_marks_story_resolved():
    result = classify_story_lifecycle(
        {
            "events": ["evt-1", "evt-2"],
            "timeline": _timeline(4),
            "canonical_title": "Evacuations lifted after brush fire fully contained",
            "importance": {"level": "high"},
        },
        reference_time=NOW,
    )
    assert result.state is StoryLifecycleState.RESOLVED


def test_story_archives_after_thirty_days_without_update():
    result = classify_story_lifecycle(
        {"events": ["evt-1"], "timeline": _timeline(24 * 31), "importance": {"level": "normal"}},
        reference_time=NOW,
    )
    assert result.state is StoryLifecycleState.ARCHIVED


def test_recent_single_event_story_is_active():
    result = classify_story_lifecycle(
        {"events": ["evt-1"], "timeline": _timeline(24), "importance": {"level": "normal"}},
        reference_time=NOW,
    )
    assert result.state is StoryLifecycleState.ACTIVE
