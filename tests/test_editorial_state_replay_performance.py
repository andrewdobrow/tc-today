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


def test_existing_registry_replay_performs_no_registry_writes(tmp_path, monkeypatch):
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
