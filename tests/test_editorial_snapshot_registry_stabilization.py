import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from tct_engine import EditorialEngine
from tct_engine.editorial_snapshot import stabilize_registry_for_snapshot


DEFAULT_TIME = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def _fingerprint(path):
    raw = path.read_bytes()
    return {
        "algorithm": "sha256",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }


def test_final_registry_stabilization_makes_next_preflight_noop_and_snapshot_eligible(
    tmp_path,
):
    registry_path = tmp_path / "editorial_story_registry.json"
    state_path = tmp_path / "editorial_state.json"
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )
    engine.process(
        {
            "id": "story-1",
            "title": "Stuart commission approves waterfront project",
            "link": "https://example.com/story-1",
            "summary": "The Stuart City Commission approved a waterfront project Monday.",
        },
        source="Treasure Coast Test Source",
        county="Martin",
    )

    # Simulate publication-time registry drift after the engine processed its
    # candidate. The normalizer must repair this authoritative index before state
    # fingerprinting.
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    event_key = next(iter(payload["event_to_story"]))
    payload["event_to_story"][event_key] = "story_999999"
    registry_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    first = stabilize_registry_for_snapshot(registry_path)
    assert first["changed"] is True
    stabilized_fingerprint = _fingerprint(registry_path)

    engine.save(state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["registry_fingerprint"] == stabilized_fingerprint

    # Mirrors the next workflow's pre-generation normalization. A clean registry is
    # not rewritten, so .57's byte-exact fingerprint remains valid.
    second = stabilize_registry_for_snapshot(registry_path)
    assert second["changed"] is False
    assert _fingerprint(registry_path) == stabilized_fingerprint

    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )
    assert restored.state_restore_mode == "snapshot"


def test_generator_stabilizes_registry_immediately_before_snapshot_save():
    source_path = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    source = source_path.read_text(encoding="utf-8")
    stabilize_at = source.index("    _stabilize_editorial_registry_before_snapshot()")
    save_at = source.index(
        "    _save_editorial_engine_audit(editorial_engine, editorial_audit_rows)",
        stabilize_at,
    )
    observability_at = source.index("    _write_editorial_observability(", save_at)
    assert stabilize_at < save_at < observability_at


def test_preflight_script_and_generator_share_same_stabilizer():
    root = Path(__file__).resolve().parents[1]
    preflight = (root / "scripts" / "repair_editorial_story_registry.py").read_text(
        encoding="utf-8"
    )
    generator = (root / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert "stabilize_registry_for_snapshot" in preflight
    assert "stabilize_registry_for_snapshot" in generator
