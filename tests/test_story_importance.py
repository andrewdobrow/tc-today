from __future__ import annotations

import json
from datetime import datetime, timezone

from tct_engine.story_importance import ImportanceLevel, StoryImportanceEngine
from tct_engine.story_registry import StoryRegistry
from tct_engine.story_timeline import TimelineEntry


def test_fatal_public_safety_story_is_high_priority():
    result = StoryImportanceEngine().score(
        {
            "titles": ["One killed in Stuart crash"],
            "facts": ["The fatal crash closed the road"],
            "locations": ["Stuart"],
            "agencies": ["Stuart Police Department"],
            "event_types": ["crash"],
            "timeline": [],
            "status": "developing",
        }
    )
    assert result.score == 65
    assert result.level is ImportanceLevel.HIGH
    assert {reason.code for reason in result.reasons} == {"fatality", "public_safety"}


def test_breaking_score_is_capped_at_100():
    result = StoryImportanceEngine().score(
        {
            "titles": ["Fatal hurricane emergency closes schools after crash"],
            "facts": ["A person was killed and schools closed after a shooting"],
            "locations": ["Martin County", "St. Lucie County"],
            "agencies": ["MCSO", "SLCFD"],
            "event_types": ["hurricane", "public safety"],
            "timeline": [{}, {}],
            "custom_article_count": 1,
            "status": "developing",
        }
    )
    assert result.score == 100
    assert result.level is ImportanceLevel.BREAKING


def test_routine_story_remains_low():
    result = StoryImportanceEngine().score(
        {
            "titles": ["Library announces summer reading program"],
            "facts": ["Registration opens Monday"],
            "locations": ["Stuart"],
            "agencies": [],
            "event_types": ["community event"],
            "timeline": [],
            "status": "developing",
        }
    )
    assert result.score == 0
    assert result.level is ImportanceLevel.LOW
    assert result.reasons == ()


def test_archived_story_is_archived_regardless_of_signals():
    result = StoryImportanceEngine().score(
        {
            "titles": ["Fatal hurricane emergency"],
            "facts": ["One person was killed"],
            "status": "archived",
        }
    )
    assert result.score == 0
    assert result.level is ImportanceLevel.ARCHIVED
    assert result.reasons[0].code == "archived"


def test_registry_persists_importance_and_migrates_schema_3(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "schema": 3,
                "next_story_id": 2,
                "stories": {
                    "story_000001": {
                        "story_id": "story_000001",
                        "events": ["event-a"],
                        "status": "developing",
                        "titles": ["One killed in Fort Pierce shooting"],
                        "facts": [],
                        "locations": ["Fort Pierce"],
                        "agencies": ["Fort Pierce Police Department"],
                        "event_types": ["shooting"],
                        "timeline": [],
                    }
                },
                "event_to_story": {"event-a": "story_000001"},
                "story_aliases": {},
            }
        ),
        encoding="utf-8",
    )

    registry = StoryRegistry(path)
    story = registry.get_story("story_000001")
    assert registry.data["schema"] == 5
    assert story["importance"]["score"] == 65
    assert story["importance"]["level"] == "high"


def test_follow_up_recalculates_importance(tmp_path):
    registry = StoryRegistry(tmp_path / "registry.json")
    story_id = registry.resolve_article(
        event_key="event-a",
        title="City council reviews proposal",
        facts=("The city council reviewed the proposal",),
        locations=("Stuart",),
        event_types=("government",),
    )
    assert registry.get_importance(story_id).score == 15

    first = TimelineEntry(
        event_key="event-a",
        article_id="a1",
        published_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        title="Initial report",
        source="TCT",
        url="https://example.com/a1",
        editorial_action="publish",
        canonical_article_id="a1",
    )
    second = TimelineEntry(
        event_key="event-b",
        article_id="a2",
        published_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        title="Follow-up",
        source="TCT",
        url="https://example.com/a2",
        editorial_action="update",
        canonical_article_id="a2",
    )
    registry.add_timeline_entry(story_id, first)
    registry.add_timeline_entry(story_id, second)
    assert registry.get_importance(story_id).score == 25
    assert registry.get_importance(story_id).level is ImportanceLevel.NORMAL


def test_top_and_breaking_story_queries(tmp_path):
    registry = StoryRegistry(tmp_path / "registry.json")
    low = registry.resolve_article(
        event_key="low",
        title="Library reading program opens",
        facts=("Registration opens",),
    )
    high = registry.resolve_article(
        event_key="high",
        title="One killed in crash",
        facts=("Fatal crash",),
        event_types=("crash",),
    )
    breaking = registry.resolve_article(
        event_key="breaking",
        title="Fatal hurricane prompts school closures",
        facts=("One person killed and schools closed",),
        locations=("Martin County", "St. Lucie County"),
        agencies=("MCSO", "SLCFD"),
        event_types=("hurricane", "crash"),
        is_custom=True,
        source="Treasure Coast Today",
    )

    top = registry.get_top_stories(limit=2)
    assert [story["story_id"] for story in top] == [breaking, high]
    assert registry.get_breaking_stories()[0]["story_id"] == breaking
    assert low not in [story["story_id"] for story in top]


def test_merge_recalculates_combined_importance(tmp_path):
    registry = StoryRegistry(tmp_path / "registry.json")
    first = registry.resolve_article(
        event_key="event-a",
        title="City council approves budget",
        facts=("The city council approved the budget",),
        locations=("Stuart",),
    )
    second = registry.resolve_article(
        event_key="event-b",
        title="Court hearing scheduled",
        facts=("A court hearing is scheduled",),
        locations=("Fort Pierce",),
    )
    merged = registry.merge_events("event-a", "event-b")
    importance = registry.get_importance(merged)
    assert merged == first
    assert second != merged
    assert importance.score == 25
    assert {reason.code for reason in importance.reasons} == {"government_action", "court_action"}
