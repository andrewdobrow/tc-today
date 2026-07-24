from __future__ import annotations

from pathlib import Path

from tct_engine.incident_identity import (
    build_incident_signature,
    compare_incident_signatures,
)
from tct_engine.registry_repair import repair_registry_payload
from tct_engine.story_registry import StoryRegistry


def _signature(title: str, *, location: str = "", published_at: str = "2026-07-23T12:00:00Z"):
    return build_incident_signature(
        titles=(title,),
        locations=(location,) if location else (),
        published_at=(published_at,),
    )


def _story(story_id: str, title: str, event_key: str, *, custom: bool = False):
    return {
        "story_id": story_id,
        "events": [event_key],
        "status": "active",
        "titles": [title],
        "title_tokens": [],
        "fact_tokens": [],
        "facts": [],
        "locations": [],
        "agencies": [],
        "event_types": [],
        "entities": [],
        "resolution_history": [],
        "relationship_history": [],
        "timeline": [
            {
                "event_key": event_key,
                "article_id": f"article-{story_id}",
                "published_at": "2026-07-23T12:00:00Z",
                "title": title,
                "source": "Treasure Coast Today" if custom else "source",
                "url": f"https://example.com/{story_id}",
            }
        ],
        "custom_article_count": int(custom),
        "sources": ["Treasure Coast Today" if custom else "source"],
        "title_candidates": [
            {
                "title": title,
                "source": "Treasure Coast Today" if custom else "source",
                "source_class": "custom" if custom else "aggregator",
                "source_trust": 100 if custom else 45,
                "is_custom": custom,
                "priority": 100 if custom else 40,
            }
        ],
        "canonical_title": title,
        "local_relevance": {"scope": "local", "score": 90},
        "lifecycle": {},
        "lifecycle_history": [],
        "editorial_proximity": {},
        "editorial_priority": 0,
        "editorial_score": 0,
        "score_breakdown": {},
        "importance": {},
    }


def test_mass_animal_hoarding_paraphrases_share_incident_identity() -> None:
    martin_case = _signature(
        "More than 70 animals found in Stuart home during large-scale hoarding response",
        location="Stuart",
    )
    syndicated = _signature(
        "Nearly 100 animals removed from home of mail carrier suspected of taking cats near her routes"
    )

    match = compare_incident_signatures(martin_case, syndicated)

    assert match.matched is True
    assert match.confidence >= 0.74
    assert "Quantity compatible: True" in match.decision_trace


def test_different_counties_do_not_share_incident_identity() -> None:
    martin_case = _signature(
        "92 cats and dogs rescued from hoarding case in Stuart",
        location="Stuart",
    )
    st_lucie_case = _signature(
        "Nearly 100 cats and dogs rescued from hoarding case in Port St. Lucie",
        location="Port St. Lucie",
    )

    match = compare_incident_signatures(martin_case, st_lucie_case)

    assert match.matched is False
    assert "Conflicting local areas" in match.reason


def test_animal_cruelty_topic_without_mass_rescue_is_not_supported() -> None:
    trainer_trial = _signature(
        "Tempers flare in Martin County courtroom as accused dog trainer trial delayed"
    )
    hoarding_case = _signature(
        "Florida woman charged after nearly 100 animals rescued from hoarding home"
    )

    match = compare_incident_signatures(trainer_trial, hoarding_case)

    assert match.matched is False
    assert trainer_trial.supported is False


def test_registry_repair_consolidates_paraphrased_incident_and_keeps_custom_primary() -> None:
    custom_title = "More than 70 animals found in Stuart home during large-scale hoarding response"
    payload = {
        "stories": {
            "story_000001": _story(
                "story_000001",
                custom_title,
                "animal-rescue-stuart-cats",
                custom=True,
            ),
            "story_000002": _story(
                "story_000002",
                "Nearly 100 animals removed from home of mail carrier suspected of taking cats near her routes",
                "unknown-event-1111111111",
            ),
            "story_000003": _story(
                "story_000003",
                "Florida mail carrier charged with animal cruelty after rescue of 92 pets",
                "unknown-event-2222222222",
            ),
        },
        "event_to_story": {},
        "story_aliases": {},
    }

    report = repair_registry_payload(payload)

    assert list(payload["stories"]) == ["story_000001"]
    assert payload["stories"]["story_000001"]["canonical_title"] == custom_title
    assert payload["stories"]["story_000001"]["custom_article_count"] == 1
    assert report.incident_identity_groups_resolved == 1
    assert report.incident_story_records_removed == 2
    assert report.remaining_incident_identity_groups == 0


def test_sparse_live_article_matches_existing_incident_before_sparse_guard(tmp_path: Path) -> None:
    registry = StoryRegistry(tmp_path / "registry.json")
    first = registry.resolve_article(
        event_key="animal-rescue-stuart-cats",
        title="More than 70 animals found in Stuart home during large-scale hoarding response",
        facts=("80 cats", "cats rescued"),
        locations=("Stuart",),
        event_types=("animal rescue",),
        published_at="2026-07-23T12:00:00Z",
        source="Treasure Coast Today",
        is_custom=True,
        source_class="custom",
        source_trust=100,
    )
    second = registry.resolve_article(
        event_key="unknown-event-1111111111",
        title="Nearly 100 animals removed from home of mail carrier suspected of taking cats near her routes",
        facts=(),
        published_at="2026-07-24T01:00:00Z",
        source="aggregator",
        source_class="aggregator",
        source_trust=45,
    )

    assert second == first
    assert registry.last_decision["relationship"] == "same_event"
    assert "Deterministic incident identity: true" in registry.last_decision["decision_trace"]
    assert registry.get_story(first)["canonical_title"].startswith("More than 70 animals")
