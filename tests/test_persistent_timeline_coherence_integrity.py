import copy
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

from tct_engine.activation import ActivationConfig, EngineMode, build_activation_preflight
from tct_engine.registry_repair import (
    REPAIR_VERSION,
    quarantine_active_story_contamination,
    repair_registry_payload,
)
from tct_engine.story_relationship import StoryRelationshipEngine, StoryRelationshipType
from tct_engine.timeline_coherence import (
    analyze_story_timeline_coherence,
    registry_timeline_coherence_violations,
)

ROOT = Path(__file__).resolve().parents[1]


def _entry(event_key, title, source, article_id):
    return {
        "event_key": event_key,
        "article_id": article_id,
        "published_at": "2026-08-01T12:00:00+00:00",
        "title": title,
        "source": source,
        "url": source,
        "editorial_action": "1",
        "canonical_article_id": article_id,
    }


def _story(story_id, entries):
    titles = [entry["title"] for entry in entries]
    return {
        "story_id": story_id,
        "events": [entry["event_key"] for entry in entries],
        "status": "developing",
        "lifecycle": {},
        "lifecycle_history": [],
        "titles": titles,
        "title_tokens": [],
        "fact_tokens": [],
        "facts": ["reported"],
        "locations": [],
        "agencies": [],
        "event_types": [],
        "entities": [],
        "local_relevance": {"scope": "unknown", "score": 35, "counties": [], "places": []},
        "resolution_history": [],
        "relationship_history": [],
        "editorial_proximity": {"score": 35, "scope": "unknown", "reason": "test"},
        "editorial_priority": 0,
        "editorial_score": 0,
        "score_breakdown": {},
        "timeline": entries,
        "custom_article_count": 0,
        "sources": [entry["source"] for entry in entries],
        "title_candidates": [
            {
                "title": entry["title"],
                "source": entry["source"],
                "source_class": "local_news",
                "source_trust": 95,
                "is_custom": False,
                "priority": 90,
            }
            for entry in entries
        ],
        "canonical_title": titles[-1],
        "importance": {"score": 0, "level": "low", "reasons": []},
    }


@pytest.mark.parametrize(
    "prior,newer",
    [
        (
            _entry(
                "policy-budget-1",
                "Martin County Fire Rescue could lose $16.5M if property tax reform passes in November",
                "https://example.com/martin-tax",
                "budget",
            ),
            _entry(
                "named-person-death:belle-glade",
                "2 killed, 2 seriously hurt in three-vehicle crash involving semi-truck near Belle Glade",
                "https://example.com/belle-crash",
                "crash",
            ),
        ),
        (
            _entry(
                "animal-rescue-cats",
                "Cat, hamster rescued after house fire in Palm Beach County",
                "https://example.com/cat-rescue",
                "cat",
            ),
            _entry(
                "named-person-death:geoffrey-lang",
                "Indian River County firefighter Geoffrey Lang dies following off-duty tragedy",
                "https://example.com/lang",
                "lang",
            ),
        ),
        (
            _entry(
                "unknown-dui",
                "Riviera Beach police officer arrested on DUI charge in Loxahatchee, PBSO says",
                "https://example.com/dui",
                "dui",
            ),
            _entry(
                "named-person-death:loxahatchee-groves",
                "Man killed in early-morning shooting in Loxahatchee Groves, suspect unknown",
                "https://example.com/shooting",
                "shooting",
            ),
        ),
    ],
)
def test_strong_cross_family_contamination_is_detected(prior, newer):
    analysis = analyze_story_timeline_coherence(
        _story("story_000001", [prior, newer])
    )
    assert analysis.coherent is False
    assert analysis.reason_codes == (
        "timeline_component_split",
        "event_family_conflict",
        "identity_continuity_missing",
    )


@pytest.mark.parametrize(
    "entries",
    [
        [
            _entry(
                "fire-hazing-a",
                "New depositions reveal why a St. Lucie County firefighter turned in alleged hazing videos",
                "https://example.com/hazing-a",
                "hazing-a",
            ),
            _entry(
                "named-person-death:bad-extraction",
                "Videos surface in St. Lucie County firefighter hazing controversy leading to terminations, suspensions",
                "https://example.com/hazing-b",
                "hazing-b",
            ),
        ],
        [
            _entry(
                "unknown-shooting-a",
                "Developing, police investigating shooting in Port St. Lucie neighborhood",
                "https://example.com/oxmoor-a",
                "oxmoor-a",
            ),
            _entry(
                "unknown-shooting-b",
                "Woman killed, man found dead after apparent domestic-related shooting in Port St. Lucie",
                "https://example.com/oxmoor-b",
                "oxmoor-b",
            ),
        ],
        [
            _entry(
                "unknown-execution-a",
                "Florida carries out first double execution in more than 60 years",
                "https://example.com/execution-a",
                "execution-a",
            ),
            _entry(
                "unknown-execution-b",
                "Florida could become first state in decades to carry out 2 executions in 1 day",
                "https://example.com/execution-b",
                "execution-b",
            ),
        ],
    ],
)
def test_legitimate_evolving_timelines_are_preserved(entries):
    assert analyze_story_timeline_coherence(
        _story("story_000001", entries)
    ).coherent is True


def test_registry_repair_splits_only_incompatible_component_and_is_idempotent():
    budget = _entry(
        "policy-budget-1",
        "Martin County Fire Rescue could lose $16.5M if property tax reform passes in November",
        "https://example.com/news/martin-tax",
        "budget",
    )
    duplicate_budget = dict(budget, article_id="budget-2")
    crash = _entry(
        "named-person-death:belle-glade",
        "2 killed, 2 seriously hurt in three-vehicle crash involving semi-truck near Belle Glade",
        "https://example.com/news/belle-crash",
        "crash",
    )
    payload = {
        "schema": 10,
        "next_story_id": 2,
        "stories": {"story_000001": _story("story_000001", [budget, duplicate_budget, crash])},
        "event_to_story": {},
        "story_aliases": {},
        "quarantined_stories": {},
        "registry_repair": {},
    }

    first = repair_registry_payload(payload)
    assert first.repair_version == REPAIR_VERSION == 13
    assert first.timeline_coherence_story_records_repaired == 1
    assert first.timeline_coherence_entries_detached == 1
    assert first.remaining_timeline_coherence_violations == 0
    assert len(payload["stories"]) == 2
    assert payload["stories"]["story_000001"]["canonical_title"].startswith(
        "Martin County Fire Rescue"
    )
    detached_id = first.timeline_coherence_new_story_ids[0]
    assert payload["stories"][detached_id]["canonical_title"].startswith("2 killed")
    assert payload["event_to_story"]["policy-budget-1"] == "story_000001"
    assert payload["event_to_story"]["named-person-death:belle-glade"] == detached_id
    assert detached_id not in payload["story_aliases"]

    snapshot = copy.deepcopy(payload)
    second = repair_registry_payload(payload)
    assert second.changed is False
    assert second.timeline_coherence_story_records_repaired == 0
    # Ignore repair history timestamps; the story graph itself must be stable.
    assert payload["stories"] == snapshot["stories"]
    assert payload["event_to_story"] == snapshot["event_to_story"]


def test_current_run_containment_splits_animal_cruelty_from_unrelated_fire():
    dog = _entry(
        "named-person-death:patricia-brennan",
        "Port St. Lucie man arrested after video shows him allegedly abusing small dog",
        "https://example.com/dog-abuse",
        "dog",
    )
    fire = _entry(
        "named-person-death:fort-myers",
        "Costco reopens following electrical fire at Martin County location",
        "https://example.com/costco-fire",
        "fire",
    )
    payload = {
        "schema": 10,
        "next_story_id": 2,
        "stories": {"story_000001": _story("story_000001", [dog, fire])},
        "event_to_story": {
            dog["event_key"]: "story_000001",
            fire["event_key"]: "story_000001",
        },
        "story_aliases": {},
        "quarantined_stories": {},
        "registry_repair": {},
        "incident_anchor_to_story": {},
    }

    contained = quarantine_active_story_contamination(payload)

    assert contained == {
        "story_000001": (
            "unsupported_structured_event_key_revoked",
            "timeline_coherence_repaired_split",
        )
    }
    assert "story_000001" in payload["stories"]
    assert len(payload["stories"]) == 2
    assert registry_timeline_coherence_violations(payload["stories"]) == []
    assert not payload["quarantined_stories"]
    assert all(
        not str(event_key).startswith("named-person-death:")
        for story in payload["stories"].values()
        for event_key in story.get("events", ())
    )
    titles = sorted(story["canonical_title"] for story in payload["stories"].values())
    assert any("small dog" in title for title in titles)
    assert any("Costco reopens" in title for title in titles)


def test_relationship_engine_rejects_hard_timeline_conflict():
    story = _story(
        "story_000014",
        [
            _entry(
                "policy-budget-1",
                "Martin County Fire Rescue could lose $16.5M if property tax reform passes in November",
                "https://example.com/martin-tax",
                "budget",
            )
        ],
    )
    relationship = StoryRelationshipEngine().classify(
        event_key="named-person-death:belle-glade",
        title="2 killed, 2 seriously hurt in three-vehicle crash involving semi-truck near Belle Glade",
        facts=["fire reported"],
        locations=(),
        agencies=(),
        event_types=["fire"],
        entities=["Martin County"],
        stories=[story],
    )
    assert relationship.relationship is StoryRelationshipType.NEW_STORY
    assert relationship.story_id is None
    assert "Timeline coherence hard conflict: true" in relationship.decision_trace


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    spec = importlib.util.spec_from_file_location(
        "tct_generate_timeline_integrity", ROOT / "scripts" / "generate.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_persistent_identity_report_fails_closed_on_timeline_violation():
    generate = _load_generate_module()
    bad_story = _story(
        "story_bad",
        [
            _entry(
                "policy-budget-1",
                "Martin County Fire Rescue could lose $16.5M if property tax reform passes in November",
                "https://example.com/martin-tax",
                "budget",
            ),
            _entry(
                "named-person-death:belle-glade",
                "2 killed, 2 seriously hurt in three-vehicle crash involving semi-truck near Belle Glade",
                "https://example.com/belle-crash",
                "crash",
            ),
        ],
    )
    report = generate._build_persistent_story_identity_integrity_report(
        [],
        {
            "stories": {"story_bad": bad_story},
            "event_to_story": {},
            "quarantined_stories": {},
        },
    )
    assert report["passed"] is False
    assert report["summary"]["timeline_coherence_violation_count"] == 1
    assert report["timeline_coherence_violations"][0]["story_id"] == "story_bad"


def test_final_integrity_validator_self_heals_repairable_timeline_drift(tmp_path):
    generate = _load_generate_module()
    budget = _entry(
        "policy-budget-1",
        "Martin County Fire Rescue could lose $16.5M if property tax reform passes in November",
        "https://example.com/news/martin-tax",
        "budget",
    )
    crash = _entry(
        "named-person-death:belle-glade",
        "2 killed, 2 seriously hurt in three-vehicle crash involving semi-truck near Belle Glade",
        "https://example.com/news/belle-crash",
        "crash",
    )
    bad_story = _story("story_bad", [budget, crash])
    registry = {
        "schema": 10,
        "next_story_id": 1,
        "stories": {"story_bad": bad_story},
        "event_to_story": {
            "policy-budget-1": "story_bad",
            "named-person-death:belle-glade": "story_bad",
        },
        "story_aliases": {},
        "quarantined_stories": {},
        "registry_repair": {},
        "incident_anchor_to_story": {},
    }
    archive = [
        {
            "slug": "budget-story",
            "headline": budget["title"],
            "source_url": budget["source"],
            "editorial_story_id": "story_bad",
        },
        {
            "slug": "crash-story",
            "headline": crash["title"],
            "source_url": crash["source"],
            "editorial_story_id": "story_bad",
        },
    ]
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "editorial_story_registry.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")

    report = generate._validate_persistent_story_identity_integrity(archive, tmp_path)

    assert report["passed"] is True
    assert report["self_heal"]["attempted"] is True
    assert report["self_heal"]["converged"] is True
    repaired_registry = json.loads(
        (tmp_path / "data" / "editorial_story_registry.json").read_text(encoding="utf-8")
    )
    assert len(repaired_registry["stories"]) == 2
    assert registry_timeline_coherence_violations(repaired_registry["stories"]) == []
    repaired_archive = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert repaired_archive[0]["editorial_story_id"] == "story_bad"
    assert repaired_archive[1]["editorial_story_id"] != "story_bad"


def test_published_story_guard_cannot_suppress_unresolved_timeline_violation():
    generate = _load_generate_module()
    generate.CURRENT_RUN_TIMELINE_INCOHERENT_STORY_IDS = {"story_000014"}
    item = {
        "title": "2 killed, 2 seriously hurt in three-vehicle crash involving semi-truck near Belle Glade",
        "link": "https://example.com/belle-crash",
        "editorial_story_id": "story_000014",
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }
    archive = [
        {
            "slug": "2026-07-23-martin-tax",
            "headline": "Martin County Fire Rescue faces $16.5M loss",
            "editorial_story_id": "story_000014",
            "source_url": "https://example.com/martin-tax",
            "legacy_identity_status": "identified",
            "ranking_eligible": True,
        }
    ]
    assert generate._published_skip_canonical(item, archive) == (None, "")


def test_activation_preflight_blocks_unresolved_timeline_integrity():
    config = ActivationConfig(requested_mode=EngineMode.ENFORCE)
    preflight = build_activation_preflight(
        config,
        previous_regression_report={"production_gate_passed": True},
        registry_health={
            "status": "clean",
            "remaining_exact_duplicate_title_groups": 0,
            "remaining_publisher_title_duplicate_groups": 0,
            "remaining_source_identity_groups": 0,
            "remaining_incident_identity_groups": 0,
            "remaining_timeline_coherence_violations": 1,
            "quarantined_story_count": 0,
        },
    )
    assert preflight.effective_mode is EngineMode.SHADOW
    assert "remaining_timeline_coherence_violations=1" in preflight.reasons


