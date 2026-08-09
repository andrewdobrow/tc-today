from __future__ import annotations

import json
from pathlib import Path

import tct_engine.registry_repair as registry_repair
import scripts.repair_editorial_story_registry as registry_preflight
from scripts.repair_editorial_story_registry import normalize_registry


ROOT = Path(__file__).resolve().parents[1]


def _story(story_id: str, title: str, event_key: str) -> dict:
    source = f"https://example.com/articles/{story_id}"
    return {
        "story_id": story_id,
        "events": [event_key],
        "status": "active",
        "lifecycle": {},
        "lifecycle_history": [],
        "titles": [title],
        "title_tokens": [],
        "fact_tokens": [],
        "facts": [],
        "locations": [],
        "agencies": [],
        "event_types": [],
        "entities": [],
        "unified_incident_evidence": [],
        "local_relevance": {"scope": "local", "score": 90},
        "resolution_history": [],
        "relationship_history": [],
        "editorial_proximity": {},
        "editorial_priority": 0,
        "editorial_score": 0,
        "score_breakdown": {},
        "custom_article_count": 0,
        "sources": [source],
        "title_candidates": [
            {
                "title": title,
                "source": source,
                "source_class": "publisher",
                "source_trust": 80,
                "is_custom": False,
                "priority": 60,
            }
        ],
        "canonical_title": title,
        "timeline": [
            {
                "event_key": event_key,
                "article_id": f"article-{story_id}",
                "canonical_article_id": f"article-{story_id}",
                "published_at": "2026-08-05T12:00:00Z",
                "title": title,
                "source": source,
                "url": source,
            }
        ],
    }


def test_late_identity_component_is_resolved_in_same_repair_call(monkeypatch):
    payload = {
        "stories": {
            "story_000001": _story("story_000001", "Primary incident article", "event-a"),
            "story_000002": _story("story_000002", "Unified incident fragment", "event-b"),
            "story_000003": _story("story_000003", "Late source identity fragment", "event-c"),
        },
        "event_to_story": {},
        "story_aliases": {},
    }

    monkeypatch.setattr(registry_repair, "_duplicate_components", lambda stories: [])
    monkeypatch.setattr(registry_repair, "_incident_components", lambda stories: [])

    def unified_components(stories):
        if "story_000002" in stories:
            return [{"story_000001", "story_000002"}]
        return []

    def source_components(stories):
        if "story_000002" not in stories and "story_000003" in stories:
            return [{"story_000001", "story_000003"}]
        return []

    monkeypatch.setattr(registry_repair, "unified_incident_components", unified_components)
    monkeypatch.setattr(registry_repair, "_source_identity_components", source_components)

    first = registry_repair.repair_registry_payload(payload)
    second = registry_repair.repair_registry_payload(payload)

    assert first.changed is True
    assert set(payload["stories"]) == {"story_000001"}
    assert first.unified_incident_story_records_removed == 1
    assert first.source_story_records_removed == 1
    assert second.changed is False


def test_registry_preflight_writes_repair_and_verifies_clean_second_pass(tmp_path):
    title = "First National Bank establishes Treasure Coast team for local businesses"
    payload = {
        "stories": {
            "story_000001": _story("story_000001", title, "event-a"),
            "story_000002": _story("story_000002", title, "event-b"),
        },
        "event_to_story": {},
        "story_aliases": {},
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    first = normalize_registry(path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    second = normalize_registry(path)

    assert first["changed"] is True
    assert first["verification_clean"] is True
    assert len(persisted["stories"]) == 1
    assert second["changed"] is False


def test_workflows_normalize_registry_before_validation_and_pytest():
    for relative in (
        ".github/workflows/test-editorial-engine.yml",
        ".github/workflows/update.yml",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        preflight = text.index("Normalize persistent story registry")
        validation = text.index("Validate editorial package")
        tests = text.index("Run editorial engine tests")
        assert preflight < validation < tests
        assert "python scripts/repair_editorial_story_registry.py" in text


def test_registry_preflight_converges_when_second_top_level_pass_exposes_merge(tmp_path, monkeypatch):
    """Regression for production pair story_002776/story_002777.

    A first deterministic pass can legitimately expose another component that is
    only visible on the next top-level pass.  Preflight must keep applying the
    same deterministic authority rules until verification is clean instead of
    failing simply because convergence required two passes.
    """
    payload = {
        "stories": {
            "story_002776": _story("story_002776", "Canonical local incident", "event-a"),
            "story_002777": _story("story_002777", "Cross-source incident fragment", "event-b"),
        },
        "event_to_story": {},
        "story_aliases": {},
        "repair_stage": 0,
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    from types import SimpleNamespace

    def report(changed, merged=None):
        return SimpleNamespace(
            changed=changed,
            merged_story_ids=merged or {},
            duplicate_story_records_removed=1 if changed else 0,
            source_story_records_removed=0,
            unified_incident_story_records_removed=0,
            incident_story_records_removed=0,
            remaining_source_identity_groups=0,
            remaining_unified_incident_groups=0,
            remaining_incident_identity_groups=0,
            remaining_timeline_coherence_violations=0,
        )

    def staged_repair(current):
        stage = int(current.get("repair_stage", 0))
        if stage == 0:
            # First pass changes evidence but does not yet merge the escaped pair.
            current["repair_stage"] = 1
            current["stories"]["story_002776"]["facts"] = ["new-evidence"]
            return report(True)
        if stage == 1:
            # The next top-level pass now sees the deterministic merge that caused
            # the Aug. 8 preflight failure.
            current["repair_stage"] = 2
            current["stories"]["story_002776"]["sources"].extend(
                current["stories"]["story_002777"]["sources"]
            )
            del current["stories"]["story_002777"]
            current["story_aliases"]["story_002777"] = "story_002776"
            return report(True, {"story_002776": ("story_002777",)})
        return report(False)

    monkeypatch.setattr(registry_preflight, "repair_registry_payload", staged_repair)

    result = registry_preflight.normalize_registry(path)
    persisted = json.loads(path.read_text(encoding="utf-8"))

    assert result["changed"] is True
    assert result["repair_passes"] == 3
    assert result["verification_clean"] is True
    assert set(persisted["stories"]) == {"story_002776"}
    assert persisted["story_aliases"]["story_002777"] == "story_002776"
