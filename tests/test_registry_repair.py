from __future__ import annotations

import json
from pathlib import Path

from tct_engine.registry_repair import repair_registry_payload
from tct_engine.story_registry import StoryRegistry


def _story(story_id: str, *, events, titles, facts=(), locations=(), event_types=(), custom=False):
    title = titles[0] if titles else ""
    return {
        "story_id": story_id,
        "events": list(events),
        "status": "active",
        "titles": list(titles),
        "title_tokens": [],
        "fact_tokens": [],
        "facts": list(facts),
        "locations": list(locations),
        "agencies": [],
        "event_types": list(event_types),
        "entities": [],
        "resolution_history": [],
        "relationship_history": [],
        "timeline": [
            {
                "event_key": event,
                "article_id": f"article-{index}",
                "title": titles[min(index, len(titles) - 1)] if titles else "",
                "source": "source",
                "url": f"https://example.com/{index}",
            }
            for index, event in enumerate(events)
        ],
        "custom_article_count": int(custom),
        "sources": ["Treasure Coast Today" if custom else "source"],
        "title_candidates": [
            {
                "title": title,
                "source": "Treasure Coast Today" if custom else "source",
                "source_class": "custom" if custom else "local_news",
                "source_trust": 100 if custom else 90,
                "is_custom": custom,
                "priority": 100 if custom else 90,
            }
        ] if title else [],
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


def test_repair_quarantines_legacy_generic_story_and_removes_active_mapping() -> None:
    payload = {
        "stories": {
            "story_000001": _story(
                "story_000001",
                events=["unknown-event", "unknown-event-1234567890"],
                titles=[
                    "School district expands early learning program",
                    "Deputies arrest suspect after boat theft investigation",
                    "Restaurant opens in downtown Stuart this weekend",
                    "Firefighters discuss property tax proposal",
                    "County commission approves road construction contract",
                    "Police release body camera footage after arrest",
                    "Baseball team wins extra innings game",
                    "Animal shelter rescues dozens of cats",
                ],
            )
        },
        "event_to_story": {"unknown-event": "story_000001"},
        "story_aliases": {},
    }

    report = repair_registry_payload(payload)

    assert report.changed is True
    assert report.quarantined_story_ids == ("story_000001",)
    assert payload["stories"] == {}
    assert payload["event_to_story"] == {}
    assert "story_000001" in payload["quarantined_stories"]


def test_repair_merges_exact_title_duplicates_and_keeps_custom_primary() -> None:
    title = "Martin County deputies rescue 80 cats from hoarding case"
    payload = {
        "stories": {
            "story_000001": _story(
                "story_000001",
                events=["animal-rescue-stuart-cats"],
                titles=[title],
            ),
            "story_000002": _story(
                "story_000002",
                events=["animal-rescue-hobe-sound-cats"],
                titles=[title],
                custom=True,
            ),
        },
        "event_to_story": {},
        "story_aliases": {},
    }

    report = repair_registry_payload(payload)

    assert report.duplicate_groups_merged == 1
    assert report.duplicate_story_records_removed == 1
    assert list(payload["stories"]) == ["story_000002"]
    merged = payload["stories"]["story_000002"]
    assert merged["canonical_title"] == title
    assert merged["custom_article_count"] == 1
    assert payload["story_aliases"]["story_000001"] == "story_000002"
    assert payload["event_to_story"]["animal-rescue-stuart-cats"] == "story_000002"
    assert payload["event_to_story"]["animal-rescue-hobe-sound-cats"] == "story_000002"


def test_repair_preserves_coherent_sparse_story_but_quarantines_incoherent_one() -> None:
    payload = {
        "stories": {
            "story_000001": _story(
                "story_000001",
                events=["traffic-crash-1111111111", "traffic-crash-2222222222"],
                titles=[
                    "Sheriff calls fatal dirt bike crash a stark reminder",
                    "Community honors child killed in dirt bike crash",
                ],
                facts=["9-year-old"],
                event_types=["traffic crash"],
            ),
            "story_000002": _story(
                "story_000002",
                events=["unknown-event-3333333333", "unknown-event-4444444444"],
                titles=[
                    "Fort Pierce police release body camera footage",
                    "Fort Pierce man arrested in child exploitation case",
                ],
                facts=["arrest made"],
                locations=["Fort Pierce"],
            ),
        },
        "event_to_story": {},
        "story_aliases": {},
    }

    report = repair_registry_payload(payload)

    assert "story_000001" in payload["stories"]
    assert "story_000002" not in payload["stories"]
    assert report.quarantined_story_ids == ("story_000002",)


def test_sparse_event_keys_do_not_use_resolver_same_event_merge(tmp_path: Path) -> None:
    registry = StoryRegistry(tmp_path / "registry.json")

    first = registry.resolve_article(
        event_key="unknown-event-1111111111",
        title="Lake Worth bakery owner faces illegal reentry charge",
        facts=("arrest made",),
        entities=("ABC News",),
    )
    second = registry.resolve_article(
        event_key="unknown-event-2222222222",
        title="Fort Pierce man arrested in child exploitation investigation",
        facts=("arrest made",),
        locations=("Fort Pierce",),
        entities=("ABC News",),
    )

    assert first != second
    assert registry.last_decision["relationship"] == "new_story"
    assert "Sparse event-key resolver guard" in " ".join(registry.last_decision["decision_trace"])


def test_exact_title_match_merges_sparse_cross_feed_duplicates(tmp_path: Path) -> None:
    registry = StoryRegistry(tmp_path / "registry.json")
    title = "P1 Motor Club bringing private racetrack resort to St. Lucie County"

    first = registry.resolve_article(
        event_key="unknown-event-1111111111",
        title=title,
        facts=(),
        source="feed-a",
    )
    second = registry.resolve_article(
        event_key="unknown-event-2222222222",
        title=title,
        facts=(),
        source="feed-b",
    )

    assert first == second
    assert registry.last_decision["relationship"] == "same_event"
    assert registry.last_decision["reason"] == "Exact normalized title already belongs to this story"
    assert len(registry.get_story(first)["events"]) == 2


def test_story_registry_persists_repair_report_on_load(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    payload = {
        "schema": 7,
        "next_story_id": 2,
        "stories": {
            "story_000001": _story(
                "story_000001",
                events=["unknown-event"],
                titles=["Unrelated legacy story container"],
            )
        },
        "event_to_story": {"unknown-event": "story_000001"},
        "story_aliases": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    registry = StoryRegistry(path)
    persisted = json.loads(path.read_text(encoding="utf-8"))

    assert registry.get_registry_health()["status"] == "repaired"
    assert persisted["schema"] == 8
    assert persisted["registry_repair"]["last_run"]["quarantined_story_count"] == 1
