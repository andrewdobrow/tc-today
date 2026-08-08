import json
from pathlib import Path

from tct_engine.story_registry import StoryRegistry


def _minimal_story(story_id: str, history: list[dict]) -> dict:
    return {
        "story_id": story_id,
        "events": ["event-1"],
        "status": "developing",
        "titles": ["Port St. Lucie council approves a public project"],
        "title_tokens": [],
        "fact_tokens": [],
        "facts": [],
        "locations": ["Port St. Lucie"],
        "agencies": ["Port St. Lucie City Council"],
        "event_types": ["approval"],
        "entities": [],
        "timeline": [],
        "resolution_history": history,
    }


def _entry(event_key: str = "event-1") -> dict:
    return {
        "event_key": event_key,
        "confidence": 1.0,
        "reason": "Exact event key already belongs to this story",
        "decision_trace": ["Relationship: same_event", "Confidence: 1.00"],
        "resolver_version": "2.1",
        "matched_existing": True,
        "relationship": "same_event",
    }


def test_loading_registry_compacts_exact_replay_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "editorial_story_registry.json"
    repeated = _entry()
    payload = {
        "schema": 10,
        "next_story_id": 2,
        "stories": {
            "story_000001": _minimal_story(
                "story_000001", [dict(repeated) for _ in range(1000)]
            )
        },
        "event_to_story": {"event-1": "story_000001"},
        "story_aliases": {},
        "quarantined_stories": {},
        "registry_repair": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    registry = StoryRegistry(path)

    history = registry.data["stories"]["story_000001"]["resolution_history"]
    assert history == [repeated]
    report = registry.data["history_compaction"]["last_load"]
    assert report["entries_before"] == 1000
    assert report["entries_after"] == 1
    assert report["duplicates_removed"] == 999


def test_append_resolution_history_does_not_repeat_existing_evidence(tmp_path: Path) -> None:
    registry = StoryRegistry(tmp_path / "editorial_story_registry.json")
    story = _minimal_story("story_000001", [_entry()])

    appended = registry._append_resolution_history(story, _entry())

    assert appended is False
    assert len(story["resolution_history"]) == 1


def test_registry_write_stays_below_safety_limit_after_compaction(tmp_path: Path) -> None:
    path = tmp_path / "editorial_story_registry.json"
    registry = StoryRegistry(path)
    registry.data["stories"] = {
        f"story_{index:06d}": _minimal_story(
            f"story_{index:06d}", [_entry(f"event-{index}") for _ in range(500)]
        )
        for index in range(1, 40)
    }

    registry.save()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.stat().st_size < StoryRegistry.REGISTRY_MAX_BYTES
    assert all(
        len(story["resolution_history"]) == 1
        for story in payload["stories"].values()
    )
    assert payload["history_compaction"]["last_write"]["duplicates_removed"] > 0


def test_workflow_removes_python_cache_and_guards_large_files() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/update.yml").read_text(encoding="utf-8")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert "PYTHONDONTWRITEBYTECODE" in workflow
    assert "Remove transient Python artifacts" in workflow
    assert "Guard generated repository size" in workflow
    assert "-size +90M" in workflow
    assert "__pycache__/" in gitignore
    assert "*.py[cod]" in gitignore


def _incident_evidence(index: int) -> dict:
    return {
        "incident_family": "traffic_crash",
        "incident_key": f"traffic-crash-port-st-lucie-{index:04d}",
        "title": f"Traffic crash update {index}",
        "locations": ["Port St. Lucie", "St. Lucie County"],
        "entities": [f"Vehicle {index}", "Port St. Lucie Police Department"],
        "facts": [
            f"Candidate relationship evidence row {index} with diagnostic context "
            "that is intentionally non-authoritative."
        ],
        "reason_codes": ["location_overlap", "incident_family_match"],
        "confidence": 0.5,
    }


def test_registry_write_compacts_old_unified_incident_candidate_evidence(tmp_path: Path) -> None:
    path = tmp_path / "editorial_story_registry.json"
    registry = StoryRegistry(path)
    story = _minimal_story("story_000001", [])
    story["unified_incident_evidence"] = [_incident_evidence(i) for i in range(30)]
    registry.data["stories"] = {"story_000001": story}

    registry.save()

    payload = json.loads(path.read_text(encoding="utf-8"))
    retained = payload["stories"]["story_000001"]["unified_incident_evidence"]
    assert len(retained) == StoryRegistry.UNIFIED_INCIDENT_EVIDENCE_LIMIT
    assert [row["incident_key"] for row in retained] == [
        f"traffic-crash-port-st-lucie-{i:04d}" for i in range(22, 30)
    ]
    report = payload["history_compaction"]["last_unified_incident_evidence_write"]
    assert report["unique_entries_truncated"] == 22
    assert report["stories_compacted"] == 1


def test_registry_pressure_mode_compacts_candidate_evidence_without_identity_loss(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "editorial_story_registry.json"
    registry = StoryRegistry(path)
    story = _minimal_story("story_000001", [])
    story["canonical_title"] = "Port St. Lucie council approves a public project"
    story["sources"] = ["https://example.com/authoritative-source"]
    story["unified_incident_evidence"] = [_incident_evidence(i) for i in range(20)]
    registry.data["stories"] = {"story_000001": story}
    registry.data["event_to_story"] = {"event-1": "story_000001"}

    monkeypatch.setattr(StoryRegistry, "REGISTRY_PRESSURE_BYTES", 1)
    monkeypatch.setattr(StoryRegistry, "REGISTRY_MAX_BYTES", 10 * 1024 * 1024)

    registry.save()

    payload = json.loads(path.read_text(encoding="utf-8"))
    saved_story = payload["stories"]["story_000001"]
    assert len(saved_story["unified_incident_evidence"]) == StoryRegistry.UNIFIED_INCIDENT_EVIDENCE_PRESSURE_LIMIT
    assert saved_story["story_id"] == "story_000001"
    assert saved_story["canonical_title"] == story["canonical_title"]
    assert saved_story["sources"] == story["sources"]
    assert payload["event_to_story"] == {"event-1": "story_000001"}
    assert payload["history_compaction"]["last_pressure_mode"] == "pressure"
