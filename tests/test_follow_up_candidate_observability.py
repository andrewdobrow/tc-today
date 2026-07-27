from pathlib import Path

from tct_engine.observability import build_editorial_observability
from tct_engine.story_registry import StoryRegistry
from tct_engine.story_relationship import (
    StoryRelationshipEngine,
    StoryRelationshipType,
)


def _story(**overrides):
    base = {
        "story_id": "story_000001",
        "status": "active",
        "facts": [],
        "locations": ["Port St. Lucie"],
        "agencies": ["Port St. Lucie City Council"],
        "event_types": [],
        "entities": ["Riverland Project"],
        "canonical_title": "Riverland project proposed in Port St. Lucie",
        "titles": ["Riverland project proposed in Port St. Lucie"],
        "title_tokens": [],
        "events": ["unknown-event-original"],
    }
    base.update(overrides)
    return base


def test_sparse_government_approval_is_observe_only_candidate():
    result = StoryRelationshipEngine().classify(
        event_key="unknown-event-approval",
        title="Port St. Lucie approves Riverland project",
        facts=(),
        locations=("Port St. Lucie",),
        agencies=("Port St. Lucie City Council",),
        entities=("Riverland Project",),
        stories=(_story(),),
    )

    assert result.relationship is StoryRelationshipType.NEW_STORY
    assert result.story_id is None
    assert result.candidate_story_id == "story_000001"
    assert result.candidate_confidence >= 0.75
    assert result.candidate_milestones == ("approval",)
    assert "novel_milestone" in result.candidate_reason_codes
    assert "Follow-up candidate mode: observe_only" in result.candidate_trace


def test_sparse_registry_decision_exports_observe_only_candidate(tmp_path: Path):
    registry = StoryRegistry(tmp_path / "registry.json")
    first_story = registry.resolve_article(
        event_key="unknown-event-proposal",
        title="Riverland project proposed in Port St. Lucie",
        facts=(),
        locations=("Port St. Lucie",),
        agencies=("Port St. Lucie City Council",),
        entities=("Riverland Project",),
    )

    second_story = registry.resolve_article(
        event_key="unknown-event-approval",
        title="Port St. Lucie approves Riverland project",
        facts=(),
        locations=("Port St. Lucie",),
        agencies=("Port St. Lucie City Council",),
        entities=("Riverland Project",),
    )

    assert second_story != first_story
    assert registry.last_decision["relationship"] == "new_story"
    assert registry.last_decision["matched_existing"] is False
    assert registry.last_decision["follow_up_candidate_story_id"] == first_story
    assert registry.last_decision["follow_up_candidate_confidence"] >= 0.75
    assert registry.last_decision["follow_up_candidate_milestones"] == ["approval"]



def test_duplicate_approval_is_not_reported_as_new_candidate():
    result = StoryRelationshipEngine().classify(
        event_key="unknown-event-second-approval-story",
        title="Port St. Lucie approves Riverland project",
        facts=(),
        locations=("Port St. Lucie",),
        agencies=("Port St. Lucie City Council",),
        entities=("Riverland Project",),
        stories=(
            _story(
                canonical_title="Port St. Lucie approves Riverland project",
                titles=["Port St. Lucie approves Riverland project"],
            ),
        ),
    )

    assert result.relationship is StoryRelationshipType.NEW_STORY
    assert result.candidate_story_id is None
    assert result.candidate_milestones == ()


def test_location_conflict_blocks_follow_up_candidate():
    result = StoryRelationshipEngine().classify(
        event_key="unknown-event-approval",
        title="Vero Beach approves Riverland project",
        facts=(),
        locations=("Vero Beach",),
        agencies=("Port St. Lucie City Council",),
        entities=("Riverland Project",),
        stories=(_story(),),
    )

    assert result.candidate_story_id is None


def test_same_event_cross_type_milestone_is_observed_without_changing_grouping(
    tmp_path: Path,
):
    registry = StoryRegistry(tmp_path / "registry.json")
    event_key = "animal-rescue-stuart-cats"
    first_story = registry.resolve_article(
        event_key=event_key,
        title="Deputies rescue 80 cats from Stuart home",
        facts=("80 cats", "cats rescued", "animal cruelty"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
        entities=("Gail Giustino",),
    )

    second_story = registry.resolve_article(
        event_key=event_key,
        title="Woman charged after 80 cats rescued from Stuart home",
        facts=("80 cats", "animal cruelty", "arrest made"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("criminal case",),
        entities=("Gail Giustino",),
    )

    assert second_story == first_story
    assert registry.last_decision["relationship"] == "same_event"
    assert registry.last_decision["follow_up_candidate_mode"] == "observe_only"
    assert registry.last_decision["follow_up_candidate_story_id"] == first_story
    assert registry.last_decision["follow_up_candidate_confidence"] >= 0.75
    assert registry.last_decision["follow_up_candidate_milestones"] == ["arrest"]
    assert "event_type_conflict" in registry.last_decision[
        "follow_up_candidate_reason_codes"
    ]


class _FakeEngine:
    def get_top_stories(self, limit=100000):
        return []

    def get_registry_health(self):
        return {"status": "healthy"}


def test_observability_exports_follow_up_candidate_readiness():
    report = build_editorial_observability(
        _FakeEngine(),
        [
            {
                "route": "skip",
                "eligible": True,
                "relationship": "same_event",
                "story_id": "story_000001",
                "headline": "Port St. Lucie approves Riverland project",
                "event_key": "unknown-event-approval",
                "follow_up_candidate_story_id": "story_000001",
                "follow_up_candidate_confidence": 0.81,
                "follow_up_candidate_milestones": ["approval"],
                "follow_up_candidate_reason_codes": [
                    "novel_milestone",
                    "title_continuity",
                ],
                "follow_up_candidate_trace": [
                    "Follow-up candidate mode: observe_only"
                ],
            }
        ],
    )

    section = report["follow_up_detection"]
    assert section["mode"] == "observe_only"
    assert section["publication_behavior_changed"] is False
    assert section["candidate_count"] == 1
    assert section["high_confidence_candidate_count"] == 1
    assert section["milestones"] == {"approval": 1}
    assert section["current_relationships"] == {"same_event": 1}
    assert section["enforcement_ready"] is False
