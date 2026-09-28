from datetime import datetime, timezone

from tct_engine import EditorialEngine
from tct_engine.story_registry import StoryRegistry


DEFAULT_TIME = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def _entry(index: int) -> dict:
    return {
        "id": f"story-{index}",
        "title": f"Treasure Coast public meeting update number {index}",
        "link": f"https://example.com/story-{index}",
        "summary": (
            f"Local officials published public meeting update number {index} "
            "for Treasure Coast residents."
        ),
    }


def _saved_state(tmp_path, *, count: int = 6):
    registry_path = tmp_path / "source-registry.json"
    state_path = tmp_path / "editorial-state.json"
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )
    for index in range(count):
        engine.process(
            _entry(index),
            source="Treasure Coast Test Source",
            county="Martin",
        )
    engine.save(state_path)
    return state_path, registry_path


def test_existing_registry_snapshot_restore_performs_no_registry_writes(tmp_path, monkeypatch):
    state_path, registry_path = _saved_state(tmp_path)
    writes = []
    original_write = StoryRegistry._write

    def counted_write(self):
        writes.append(self.path)
        return original_write(self)

    monkeypatch.setattr(StoryRegistry, "_write", counted_write)

    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )

    assert len(restored._history) == 6
    assert writes == []


def test_missing_registry_replay_coalesces_to_one_write(tmp_path, monkeypatch):
    state_path, source_registry_path = _saved_state(tmp_path)
    source_registry_path.unlink()
    writes = []
    original_write = StoryRegistry._write

    def counted_write(self):
        writes.append(self.path)
        return original_write(self)

    monkeypatch.setattr(StoryRegistry, "_write", counted_write)

    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=source_registry_path,
    )

    assert len(restored._history) == 6
    assert writes == [source_registry_path]
    assert source_registry_path.exists()


def test_deferred_registry_save_does_not_commit_after_exception(tmp_path, monkeypatch):
    registry_path = tmp_path / "registry.json"
    registry = StoryRegistry(registry_path)
    writes = []
    original_write = StoryRegistry._write

    def counted_write(self):
        writes.append(self.path)
        return original_write(self)

    monkeypatch.setattr(StoryRegistry, "_write", counted_write)

    try:
        with registry.defer_saves():
            registry.save()
            raise RuntimeError("stop replay")
    except RuntimeError:
        pass

    assert writes == []
    assert not registry_path.exists()


def test_matching_registry_snapshot_bypasses_historical_replay(tmp_path, monkeypatch, capsys):
    state_path, registry_path = _saved_state(tmp_path, count=12)
    calls = []
    original_process = EditorialEngine._process

    def counted_process(self, *args, **kwargs):
        calls.append(1)
        return original_process(self, *args, **kwargs)

    monkeypatch.setattr(EditorialEngine, "_process", counted_process)

    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )

    output = capsys.readouterr().out
    assert restored.state_restore_mode == "snapshot"
    assert len(calls) == 0
    assert len(restored._history) == 12
    assert "Timing detail: editorial state read+parse" in output
    assert "Timing detail: editorial history compact+validate" in output
    assert "Timing detail: editorial pipeline snapshot restore" in output
    assert "bypassed by verified snapshot" in output
    assert "Timing detail: editorial state restore total" in output


def test_registry_fingerprint_mismatch_falls_back_to_full_replay(tmp_path, monkeypatch):
    state_path, registry_path = _saved_state(tmp_path, count=5)
    payload = registry_path.read_text(encoding="utf-8")
    # A byte-level mismatch must disable the derived-state fast path even when the
    # JSON is still valid.  This is the safety boundary that keeps quality/identity
    # behavior identical after artifact restores or partial failed runs.
    registry_path.write_text(payload + "\n", encoding="utf-8")

    calls = []
    original_process = EditorialEngine._process

    def counted_process(self, *args, **kwargs):
        calls.append(1)
        return original_process(self, *args, **kwargs)

    monkeypatch.setattr(EditorialEngine, "_process", counted_process)

    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )

    assert restored.state_restore_mode == "replay"
    assert len(calls) == 5


def test_corrupt_pipeline_snapshot_falls_back_to_replay(tmp_path, monkeypatch):
    state_path, registry_path = _saved_state(tmp_path, count=4)
    import json

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["pipeline_state"]["snapshots"] = "not-a-list"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    calls = []
    original_process = EditorialEngine._process

    def counted_process(self, *args, **kwargs):
        calls.append(1)
        return original_process(self, *args, **kwargs)

    monkeypatch.setattr(EditorialEngine, "_process", counted_process)
    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )

    assert restored.state_restore_mode == "replay"
    assert len(calls) == 4


def test_snapshot_restore_matches_replay_for_next_editorial_decision(tmp_path):
    import json

    registry_path = tmp_path / "registry.json"
    state_path = tmp_path / "state.json"
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )

    historical = [
        {
            "id": "storm-1",
            "title": "Tropical Storm Alpha approaches the Treasure Coast",
            "link": "https://example.com/storm-1",
            "summary": "Tropical Storm Alpha may bring wind and rain to Martin County.",
        },
        {
            "id": "storm-2",
            "title": "Martin County prepares shelters as Tropical Storm Alpha approaches",
            "link": "https://example.com/storm-2",
            "summary": "Officials opened shelters as Tropical Storm Alpha nears the Treasure Coast.",
        },
        {
            "id": "meeting-1",
            "title": "Stuart commission approves waterfront project",
            "link": "https://example.com/meeting-1",
            "summary": "The Stuart City Commission approved a waterfront project Monday.",
        },
    ]
    for row in historical:
        engine.process(row, source="Treasure Coast Test Source", county="Martin")
    engine.save(state_path)

    replay_state_path = tmp_path / "state-force-replay.json"
    replay_payload = json.loads(state_path.read_text(encoding="utf-8"))
    replay_payload["registry_fingerprint"] = {
        "algorithm": "sha256",
        "sha256": "0" * 64,
        "size": 0,
    }
    replay_state_path.write_text(json.dumps(replay_payload), encoding="utf-8")

    snapshot_engine = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )
    replay_engine = EditorialEngine.load(
        replay_state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )

    assert snapshot_engine.state_restore_mode == "snapshot"
    assert replay_engine.state_restore_mode == "replay"
    assert snapshot_engine._pipeline.export_replay_state() == replay_engine._pipeline.export_replay_state()

    incoming = {
        "id": "storm-3",
        "title": "Tropical Storm Alpha strengthens near Treasure Coast",
        "link": "https://example.com/storm-3",
        "summary": "Tropical Storm Alpha strengthened while approaching Martin County.",
    }
    snapshot_result = snapshot_engine.process(
        incoming, source="Treasure Coast Test Source", county="Martin"
    )
    replay_result = replay_engine.process(
        incoming, source="Treasure Coast Test Source", county="Martin"
    )

    comparable_fields = (
        "action",
        "canonical_article_id",
        "event_key",
        "new_facts",
        "story_id",
        "relationship",
        "relationship_confidence",
        "relationship_reason",
        "follow_up_candidate_story_id",
        "canonical_title",
        "canonical_source",
        "canonical_url",
    )
    for field in comparable_fields:
        assert getattr(snapshot_result, field) == getattr(replay_result, field)


def test_snapshot_restore_preserves_existing_event_canonical_and_snapshot(tmp_path):
    state_path, registry_path = _saved_state(tmp_path, count=8)
    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
        registry_path=registry_path,
    )

    assert restored.state_restore_mode == "snapshot"
    pipeline_state = restored._pipeline.export_replay_state()
    assert len(pipeline_state["candidates"]) == 8
    assert len(pipeline_state["snapshots"]) == 8
    assert {row["article_id"] for row in pipeline_state["candidates"]} == {
        f"story-{index}" for index in range(8)
    }
