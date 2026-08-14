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
                    "identity_anchor_qualified",
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


def test_observability_suppresses_legacy_unanchored_candidate_rows():
    report = build_editorial_observability(
        _FakeEngine(),
        [
            {
                "route": "skip",
                "eligible": True,
                "relationship": "new_story",
                "story_id": "story_000010",
                "headline": "Unrelated death report",
                "event_key": "unknown-event-unrelated",
                "follow_up_candidate_story_id": "story_000001",
                "follow_up_candidate_confidence": 0.91,
                "follow_up_candidate_milestones": ["death"],
                "follow_up_candidate_reason_codes": ["enforced_follow_up"],
                "follow_up_candidate_trace": ["Location match: False"],
            }
        ],
    )

    section = report["follow_up_detection"]
    assert section["candidate_count"] == 0
    assert section["high_confidence_candidate_count"] == 0
    assert section["unanchored_candidate_suppressed_count"] == 1


def test_sparse_milestone_without_identity_anchor_is_not_exported(tmp_path: Path):
    registry = StoryRegistry(tmp_path / "registry.json")
    registry.resolve_article(
        event_key="unknown-event-first",
        title="Unrelated death investigation",
        facts=("death reported",),
        event_types=("death",),
    )

    registry.resolve_article(
        event_key="unknown-event-second",
        title="Another unrelated death investigation",
        facts=("death reported",),
        event_types=("death",),
    )

    assert registry.last_decision["relationship"] == "new_story"
    assert registry.last_decision["follow_up_candidate_story_id"] == ""
    assert registry.last_decision["follow_up_candidate_confidence"] == 0.0
    assert registry.last_decision["follow_up_candidate_milestones"] == []


def test_phrase_aware_advisory_milestones_reject_generic_breaks_and_ending():
    from tct_engine.story_relationship import detect_advisory_follow_up_milestones

    assert detect_advisory_follow_up_milestones(
        "Private racetrack resort breaks ground in St. Lucie County"
    ) == {"opening"}
    assert "opening" not in detect_advisory_follow_up_milestones(
        "Expert breaks down the psychology of animal hoarding"
    )
    assert "closure" not in detect_advisory_follow_up_milestones(
        "A happy ending for families reunited with their pets"
    )
    assert "closure" in detect_advisory_follow_up_milestones(
        "JetBlue cancels the route between Vero Beach and New York"
    )
    assert "death" in detect_advisory_follow_up_milestones(
        "Deadly shooting under investigation in St. Lucie County"
    )
    assert "death" in detect_advisory_follow_up_milestones(
        "Officer investigated after leaving scene of suspected suicide"
    )
    assert "death" not in detect_advisory_follow_up_milestones(
        "School hosts suicide prevention awareness program"
    )


class _TimelineEngine(_FakeEngine):
    def __init__(self, stories):
        self._stories = stories

    def get_top_stories(self, limit=100000):
        return list(self._stories)[:limit]


def _timeline_entry(article_id, published_at, title, *, source="https://www.wptv.com/story"):
    return {
        "event_key": f"unknown-event-{article_id}",
        "article_id": article_id,
        "published_at": published_at,
        "title": title,
        "source": source,
        "url": source,
    }


def test_retrospective_observability_finds_missing_person_recovery():
    story = {
        "story_id": "story_000695",
        "status": "developing",
        "canonical_title": (
            "West Palm Beach police seek public's help finding missing "
            "10-year-old boy traveling with his aunt"
        ),
        "timeline": [
            _timeline_entry(
                "one",
                "2026-07-26T15:40:30+00:00",
                "West Palm Beach police seek public's help finding missing "
                "10-year-old boy traveling with his aunt",
                source="https://www.wptv.com/missing-child-original",
            ),
            _timeline_entry(
                "two",
                "2026-07-26T20:40:28+00:00",
                "Missing 10-Year-Old safely located in Tennessee, "
                "West Palm Beach Police say",
                source="https://www.wpbf.com/missing-child-recovery",
            ),
        ],
    }

    report = build_editorial_observability(_TimelineEngine([story]), [])
    section = report["follow_up_detection"]
    retrospective = section["retrospective"]

    assert section["candidate_count"] == 0
    assert section["retrospective_candidate_count"] == 1
    assert retrospective["candidate_count"] == 1
    assert retrospective["activation_eligible_candidate_count"] == 1
    example = retrospective["examples"][0]
    assert example["milestones"] == ["recovery"]
    assert example["activation_eligible"] is True
    assert example["blocking_conflicts"] == []
    assert example["prior_article"]["article_id"] == "one"
    assert example["newer_article"]["article_id"] == "two"
    assert "safely located" in example["matched_phrases"]["recovery"]
    assert retrospective["publication_behavior_changed"] is False
    assert retrospective["enforcement_ready"] is False


def test_retrospective_observability_blocks_same_timestamp_order():
    story = {
        "story_id": "story_000010",
        "status": "developing",
        "canonical_title": "Riverland project proposed in Port St. Lucie",
        "timeline": [
            _timeline_entry(
                "one",
                "2026-07-26T15:40:30+00:00",
                "Riverland project proposed in Port St. Lucie",
            ),
            _timeline_entry(
                "two",
                "2026-07-26T15:40:30+00:00",
                "Port St. Lucie approves Riverland project",
            ),
        ],
    }

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]

    assert retrospective["candidate_count"] == 1
    assert retrospective["activation_eligible_candidate_count"] == 0
    assert retrospective["blocking_conflicts"] == {
        "same_timestamp_order_uncertain": 1
    }
    assert retrospective["examples"][0]["activation_eligible"] is False


def test_retrospective_observability_excludes_social_and_low_value_entries():
    story = {
        "story_id": "story_000003",
        "status": "developing",
        "canonical_title": "Deputies rescue animals from Stuart home",
        "timeline": [
            _timeline_entry(
                "one",
                "2026-07-23T10:00:00+00:00",
                "Deputies rescue 92 animals from Stuart home",
            ),
            _timeline_entry(
                "two",
                "2026-07-24T10:00:00+00:00",
                "Expert breaks down the psychology of animal hoarding after arrest",
            ),
            _timeline_entry(
                "three",
                "2026-07-25T10:00:00+00:00",
                "A happy ending as families are reunited with rescued pets - facebook.com",
                source="https://facebook.com/post/123",
            ),
        ],
    }

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]

    assert retrospective["candidate_count"] == 0
    assert retrospective["excluded_entry_count"] == 2
    assert retrospective["exclusion_reasons"] == {
        "low_value_title": 2,
        "social_source": 1,
    }


def test_retrospective_geoffrey_lang_to_unrelated_house_fire_is_incoherent():
    story = {
        "story_id": "story_000793",
        "status": "developing",
        "canonical_title": "Cat, hamster rescued after house fire in Palm Beach County",
        "timeline": [
            _timeline_entry(
                "lang",
                "2026-07-27T05:25:57+00:00",
                "Indian River County Fire Rescue firefighter Geoffrey Lang dies in off-duty incident",
                source="https://news.google.com/rss/articles/geoffrey-lang",
            ),
            _timeline_entry(
                "pets",
                "2026-07-28T03:51:43+00:00",
                "Cat, hamster rescued after house fire in Palm Beach County",
                source="https://www.wptv.com/news/local-news/palm-beach/cat-hamster-rescued-house-fire",
            ),
        ],
    }
    story["timeline"][0]["event_key"] = "fire-f2e4e9d745"
    story["timeline"][1]["event_key"] = "animal-rescue-76e432cbef-cats"

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]

    assert retrospective["candidate_count"] == 1
    assert retrospective["high_confidence_candidate_count"] == 0
    assert retrospective["activation_eligible_candidate_count"] == 0
    assert retrospective["identity_anchor_rejected_count"] == 1
    assert retrospective["incoherent_transition_count"] == 1
    assert retrospective["incoherent_story_count"] == 1
    example = retrospective["examples"][0]
    assert example["timeline_incoherent"] is True
    assert example["identity_anchor_qualified"] is False
    assert example["confidence"] < 0.80
    assert "timeline_identity_unanchored" in example["blocking_conflicts"]
    assert "timeline_incoherent" in example["reason_codes"]
    assert retrospective["incoherent_stories"][0]["story_id"] == "story_000793"


def test_retrospective_sebastian_shooting_to_firefighter_death_is_incoherent():
    story = {
        "story_id": "story_000549",
        "status": "developing",
        "canonical_title": (
            "Indian River County firefighter/paramedic dies following "
            "off-duty personal tragedy"
        ),
        "timeline": [
            _timeline_entry(
                "shooting",
                "2026-07-25T00:38:10+00:00",
                "Shots fired at Orchard Grove apartments; no injuries reported",
                source="https://news.google.com/rss/articles/sebastian-shooting",
            ),
            _timeline_entry(
                "death",
                "2026-07-26T20:40:28+00:00",
                "Indian River County firefighter/paramedic dies following off-duty personal tragedy",
                source="https://news.google.com/rss/articles/geoffrey-lang-death",
            ),
        ],
    }
    story["timeline"][0]["event_key"] = "fire-sebastian"
    story["timeline"][1]["event_key"] = "fire-f43e781d70"

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]

    assert retrospective["candidate_count"] == 1
    assert retrospective["high_confidence_candidate_count"] == 0
    assert retrospective["activation_eligible_candidate_count"] == 0
    example = retrospective["examples"][0]
    assert example["milestones"] == ["death"]
    assert example["timeline_incoherent"] is True
    assert example["identity_anchor_codes"][-1] == "identity_anchor_missing"
    assert "timeline_identity_unanchored" in example["blocking_conflicts"]


def test_retrospective_same_source_article_evolution_is_not_follow_up_candidate():
    story = {
        "story_id": "story_000695",
        "status": "developing",
        "canonical_title": (
            "West Palm Beach police seek public's help finding missing "
            "10-year-old boy traveling with his aunt"
        ),
        "timeline": [
            _timeline_entry(
                "missing",
                "2026-07-26T15:40:30+00:00",
                "West Palm Beach police seek public's help finding missing 10-year-old boy traveling with his aunt",
                source="https://www.wptv.com/news/west-palm-beach/missing-10-year-old",
            ),
            _timeline_entry(
                "located",
                "2026-07-26T20:40:28+00:00",
                "Missing 10-Year-Old safely located in Tennessee, West Palm Beach Police say",
                source="https://www.wptv.com/news/west-palm-beach/missing-10-year-old",
            ),
        ],
    }
    story["timeline"][0]["event_key"] = "missing-person-a6668511e1"
    story["timeline"][1]["event_key"] = "missing-person-ffed96853f"

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]

    assert retrospective["candidate_scope"] == "distinct_article_transitions"
    assert retrospective["candidate_count"] == 0
    assert retrospective["high_confidence_candidate_count"] == 0
    assert retrospective["activation_eligible_candidate_count"] == 0
    assert retrospective["same_source_evolution_count"] == 1
    assert retrospective["same_source_evolution_milestones"] == {"recovery": 1}
    example = retrospective["same_source_evolution_examples"][0]
    assert example["classification"] == "same_source_article_evolution"
    assert example["milestones"] == ["recovery"]
    assert "exact_source_article_identity" in example["identity_anchor_codes"]


def test_retrospective_known_event_family_conflict_blocks_activation():
    story = {
        "story_id": "story_conflict",
        "status": "developing",
        "canonical_title": "Fort Pierce police investigate crash involving 2 children in crosswalk",
        "timeline": [
            _timeline_entry(
                "prior",
                "2026-08-09T12:00:00+00:00",
                "Fort Pierce police investigate crash involving 2 children in crosswalk",
                source="https://www.wptv.com/fort-pierce-crash",
            ),
            _timeline_entry(
                "newer",
                "2026-08-10T12:00:00+00:00",
                "Driver identified in Fort Pierce crash involving 2 children in crosswalk",
                source="https://cbs12.com/fort-pierce-crash-driver",
            ),
        ],
    }
    story["timeline"][0]["event_key"] = "traffic-crash-fort-pierce-9af536fb39"
    story["timeline"][1]["event_key"] = "fire-fort-pierce-1a2b3c4d"

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]

    assert retrospective["candidate_count"] == 1
    assert retrospective["activation_eligible_candidate_count"] == 0
    example = retrospective["examples"][0]
    assert example["milestones"] == ["identified"]
    assert example["identity_anchor_qualified"] is True
    assert "event_family_conflict" in example["blocking_conflicts"]
    assert "activation_blocked_event_family_conflict" in example["reason_codes"]


def test_retrospective_unknown_event_family_does_not_create_false_conflict():
    story = {
        "story_id": "story_unknown",
        "status": "developing",
        "canonical_title": "19-year-old Boynton Beach man dies following Saturday shooting",
        "timeline": [
            _timeline_entry(
                "prior",
                "2026-08-09T12:00:00+00:00",
                "19-year-old Boynton Beach man dies following Saturday shooting",
                source="https://www.wptv.com/boynton-shooting",
            ),
            _timeline_entry(
                "newer",
                "2026-08-10T12:00:00+00:00",
                "19-year-old identified as victim in deadly Boynton Beach shooting - WPEC",
                source="https://cbs12.com/boynton-shooting-victim",
            ),
        ],
    }
    story["timeline"][0]["event_key"] = "named-person-death:nigel-beckford"
    story["timeline"][1]["event_key"] = "unknown-event-ab8ddbfa94"

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]
    example = retrospective["examples"][0]

    assert "event_family_conflict" not in example["blocking_conflicts"]
    assert "event_family_conflict" not in example["identity_anchor_codes"]


def test_retrospective_true_cross_source_arrest_follow_up_stays_activation_evidence():
    story = {
        "story_id": "story_002380",
        "status": "developing",
        "canonical_title": "Fort Pierce police investigate hit-and-run crash involving 2 children in crosswalk",
        "timeline": [
            _timeline_entry(
                "prior",
                "2026-08-05T12:00:00+00:00",
                "Fort Pierce police investigate hit-and-run crash involving 2 children in crosswalk",
                source="https://www.wptv.com/fort-pierce-hit-run",
            ),
            _timeline_entry(
                "newer",
                "2026-08-06T12:00:00+00:00",
                "Driver arrested in Fort Pierce hit-and-run that injured 7-year-old",
                source="https://www.wpbf.com/fort-pierce-hit-run-arrest",
            ),
        ],
    }
    story["timeline"][0]["event_key"] = "traffic-crash-fort-pierce-9af536fb39"
    story["timeline"][1]["event_key"] = "traffic-crash-fort-pierce-e3adde596e"

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]

    assert retrospective["candidate_count"] == 1
    assert retrospective["activation_eligible_candidate_count"] == 1
    example = retrospective["examples"][0]
    assert example["milestones"] == ["arrest"]
    assert example["activation_eligible"] is True
    assert example["blocking_conflicts"] == []
    assert "event_family_match" in example["identity_anchor_codes"]


def test_retrospective_canonical_title_cannot_self_validate_unrelated_transition():
    story = {
        "story_id": "story_corrupt",
        "status": "developing",
        "canonical_title": "Indian River County firefighter Geoffrey Lang dies",
        "timeline": [
            _timeline_entry(
                "prior",
                "2026-07-25T00:00:00+00:00",
                "Shots fired at Sebastian apartments with no injuries",
                source="https://example.com/news/sebastian-shooting",
            ),
            _timeline_entry(
                "newer",
                "2026-07-26T00:00:00+00:00",
                "Indian River County firefighter Geoffrey Lang dies",
                source="https://example.com/news/geoffrey-lang",
            ),
        ],
    }

    retrospective = build_editorial_observability(
        _TimelineEngine([story]), []
    )["follow_up_detection"]["retrospective"]
    example = retrospective["examples"][0]

    assert example["canonical_title_overlap"] == 1.0
    assert example["identity_anchor_qualified"] is False
    assert example["activation_eligible"] is False
    assert retrospective["high_confidence_candidate_count"] == 0
