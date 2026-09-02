import importlib.util
import os
import sys
import types
from pathlib import Path


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
        )
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path("scripts/generate.py")
    spec = importlib.util.spec_from_file_location("scripts.generate_story_registry_compaction_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _revision(run_id, revision, slug="story-a", stage="investigation", article_count=1):
    return {
        "run_id": run_id,
        "revision": revision,
        "article_count": article_count,
        "latest_stage": stage,
        "latest_date": "2026-09-01",
        "canonical_slug": slug,
    }


def _confidence(run_id, slug="article-a", confidence=100, matched="", basis="exact"):
    return {
        "run_id": run_id,
        "slug": slug,
        "confidence": confidence,
        "matched_prior_slug": matched,
        "attachment_basis": basis,
    }


def test_revision_history_collapses_noop_runs_but_preserves_state_transitions():
    g = _load_generate()
    entries = [
        _revision("r1", 1),
        _revision("r2", 2),
        _revision("r3", 3, stage="body-recovery"),
        _revision("r4", 4, stage="body-recovery"),
        _revision("r5", 5, stage="investigation"),
    ]

    compacted = g._compact_revision_history(entries)

    assert [row["run_id"] for row in compacted] == ["r1", "r3", "r5"]
    assert [row["latest_stage"] for row in compacted] == ["investigation", "body-recovery", "investigation"]


def test_confidence_history_dedupes_per_slug_without_losing_later_reversion():
    g = _load_generate()
    entries = [
        _confidence("r1", slug="a", confidence=100),
        _confidence("r1", slug="b", confidence=95),
        _confidence("r2", slug="a", confidence=100),
        _confidence("r2", slug="b", confidence=95),
        _confidence("r3", slug="a", confidence=90, matched="prior-a", basis="semantic"),
        _confidence("r4", slug="a", confidence=90, matched="prior-a", basis="semantic"),
        _confidence("r5", slug="a", confidence=100),
    ]

    compacted = g._compact_confidence_history(entries)

    assert [(row["run_id"], row["slug"], row["confidence"]) for row in compacted] == [
        ("r1", "a", 100),
        ("r1", "b", 95),
        ("r3", "a", 90),
        ("r5", "a", 100),
    ]


def test_merge_does_not_append_history_for_unchanged_story_state():
    g = _load_generate()
    previous = {
        "stories": [
            {
                "story_id": "story-a",
                "title": "Story A",
                "canonical_headline": "Story A",
                "canonical_slug": "story-a",
                "articles": [{"slug": "story-a"}],
                "historical_slugs": ["story-a"],
                "revision_history": [_revision("r1", 1), _revision("r2", 2)],
                "confidence_history": [_confidence("r1"), _confidence("r2")],
                "registry_revision": 2,
            }
        ],
        "retired_story_ids": {},
    }
    computed = [
        {
            "story_id": "story-a",
            "title": "Story A",
            "status": "active",
            "latest_stage": "investigation",
            "latest_date": "2026-09-01",
            "canonical_slug": "story-a",
            "canonical_headline": "Story A",
            "canonical_is_custom": False,
            "article_count": 1,
            "entities": {},
            "timeline": [],
            "stages": [],
            "articles": [
                {
                    "slug": "article-a",
                    "attachment_confidence": 100,
                    "matched_prior_slug": "",
                    "attachment_basis": "exact",
                }
            ],
        }
    ]

    merged = g._merge_persistent_story_registry(previous, computed, "r3")
    story = merged["stories"][0]

    assert len(story["revision_history"]) == 1
    assert len(story["confidence_history"]) == 1
    assert merged["history_compaction"]["revision_entries_before"] == 2
    assert merged["history_compaction"]["revision_entries_after"] == 1
    assert merged["history_compaction"]["confidence_entries_before"] == 2
    assert merged["history_compaction"]["confidence_entries_after"] == 1


def test_inactive_preserved_story_history_is_compacted_too():
    g = _load_generate()
    previous = {
        "stories": [
            {
                "story_id": "inactive-a",
                "title": "Inactive A",
                "historical_slugs": ["inactive-a"],
                "revision_history": [_revision("r1", 1), _revision("r2", 2)],
                "confidence_history": [_confidence("r1"), _confidence("r2")],
            }
        ],
        "retired_story_ids": {},
    }

    merged = g._merge_persistent_story_registry(previous, [], "r3")
    story = merged["stories"][0]

    assert story["status"] == "inactive"
    assert len(story["revision_history"]) == 1
    assert len(story["confidence_history"]) == 1
