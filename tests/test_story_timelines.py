"""Regression tests for persistent story timelines."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from tct_engine.story_registry import StoryRegistry
from tct_engine.story_timeline import StoryTimeline, TimelineEntry


def _entry(
    *,
    event_key: str,
    article_id: str,
    day: int,
    title: str = "Story update",
) -> TimelineEntry:
    return TimelineEntry(
        event_key=event_key,
        article_id=article_id,
        published_at=datetime(2026, 7, day, 12, tzinfo=timezone.utc),
        title=title,
        source="Treasure Coast Today",
        url=f"https://example.com/{article_id}",
        editorial_action="publish_new",
        canonical_article_id=article_id,
    )


def test_timeline_orders_entries_chronologically():
    timeline = StoryTimeline()
    timeline.add(_entry(event_key="later", article_id="a2", day=22))
    timeline.add(_entry(event_key="earlier", article_id="a1", day=20))

    assert [entry.article_id for entry in timeline.entries] == ["a1", "a2"]


def test_duplicate_article_or_event_is_rejected():
    timeline = StoryTimeline()
    assert timeline.add(_entry(event_key="rescue", article_id="a1", day=20))
    assert not timeline.add(_entry(event_key="arrest", article_id="a1", day=21))
    assert not timeline.add(_entry(event_key="rescue", article_id="a2", day=21))
    assert len(timeline.entries) == 1


def test_related_events_share_one_persistent_timeline(tmp_path):
    path = tmp_path / "story-registry.json"
    registry = StoryRegistry(path)

    first_story = registry.resolve_story("animal-rescue-stuart")
    registry.add_timeline_entry(
        first_story,
        _entry(event_key="animal-rescue-stuart", article_id="a1", day=20),
    )

    second_story = registry.resolve_story("animal-cruelty-arrest-stuart")
    registry.add_timeline_entry(
        second_story,
        _entry(
            event_key="animal-cruelty-arrest-stuart",
            article_id="a2",
            day=21,
        ),
    )

    merged_story = registry.merge_events(
        "animal-rescue-stuart",
        "animal-cruelty-arrest-stuart",
    )
    timeline = registry.get_timeline(merged_story)

    assert timeline is not None
    assert [entry.article_id for entry in timeline.entries] == ["a1", "a2"]


def test_unrelated_stories_keep_separate_timelines(tmp_path):
    registry = StoryRegistry(tmp_path / "story-registry.json")
    rescue = registry.resolve_story("animal-rescue-stuart")
    crash = registry.resolve_story("traffic-crash-fort-pierce")

    registry.add_timeline_entry(
        rescue,
        _entry(event_key="animal-rescue-stuart", article_id="a1", day=20),
    )
    registry.add_timeline_entry(
        crash,
        _entry(event_key="traffic-crash-fort-pierce", article_id="b1", day=20),
    )

    assert [entry.article_id for entry in registry.get_timeline(rescue).entries] == ["a1"]
    assert [entry.article_id for entry in registry.get_timeline(crash).entries] == ["b1"]


def test_timeline_survives_registry_reload(tmp_path):
    path = tmp_path / "story-registry.json"
    registry = StoryRegistry(path)
    story_id = registry.resolve_story("animal-rescue-stuart")
    registry.add_timeline_entry(
        story_id,
        _entry(event_key="animal-rescue-stuart", article_id="a1", day=20),
    )

    reloaded = StoryRegistry(path)
    timeline = reloaded.get_timeline(story_id)

    assert timeline is not None
    assert timeline.entries[0].article_id == "a1"
    assert timeline.entries[0].published_at == datetime(
        2026, 7, 20, 12, tzinfo=timezone.utc
    )


def test_older_registry_migrates_with_empty_timeline(tmp_path):
    path = tmp_path / "story-registry.json"
    path.write_text(
        json.dumps(
            {
                "schema": 2,
                "next_story_id": 2,
                "stories": {
                    "story_000001": {
                        "story_id": "story_000001",
                        "events": ["animal-rescue-stuart"],
                    }
                },
                "event_to_story": {
                    "animal-rescue-stuart": "story_000001"
                },
                "story_aliases": {},
            }
        ),
        encoding="utf-8",
    )

    registry = StoryRegistry(path)
    story = registry.get_story("story_000001")

    assert story is not None
    assert story["timeline"] == []
    assert registry.data["schema"] == StoryRegistry.SCHEMA_VERSION
