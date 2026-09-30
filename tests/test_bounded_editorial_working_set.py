from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import tct_engine.story_registry as story_registry_module
from scripts.repair_editorial_story_registry import normalize_registry
from tct_engine.registry_repair import REPAIR_VERSION
from tct_engine.story_registry import StoryRegistry
from tct_engine.working_set import (
    compact_editorial_state_working_set,
    compact_registry_working_set,
    file_fingerprint,
    preflight_receipt_path,
)

NOW = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)


def _story(story_id: str, *, published: str | None, status: str = "active") -> dict:
    timeline = []
    if published:
        timeline.append(
            {
                "event_key": f"event-{story_id}",
                "article_id": f"article-{story_id}",
                "canonical_article_id": f"article-{story_id}",
                "published_at": published,
                "title": f"Story {story_id}",
                "source": f"https://example.com/{story_id}",
                "url": f"https://example.com/{story_id}",
            }
        )
    return {
        "story_id": story_id,
        "events": [f"event-{story_id}"],
        "status": status,
        "titles": [f"Story {story_id}"],
        "facts": [],
        "locations": [],
        "agencies": [],
        "event_types": [],
        "entities": [],
        "local_relevance": {"scope": "local", "score": 90},
        "custom_article_count": 0,
        "sources": [f"https://example.com/{story_id}"],
        "title_candidates": [],
        "canonical_title": f"Story {story_id}",
        "timeline": timeline,
    }


def test_registry_working_set_retires_only_old_nonongoing_stories(tmp_path):
    registry_path = tmp_path / "editorial_story_registry.json"
    history_path = tmp_path / "editorial_story_history.jsonl"
    registry_path.write_text(
        json.dumps(
            {
                "schema": 10,
                "next_story_id": 5,
                "stories": {
                    "story_000001": _story(
                        "story_000001", published="2026-09-25T12:00:00Z"
                    ),
                    "story_000002": _story(
                        "story_000002", published="2026-07-01T12:00:00Z", status="archived"
                    ),
                    "story_000003": _story(
                        "story_000003", published="2026-07-01T12:00:00Z", status="ongoing"
                    ),
                    "story_000004": _story("story_000004", published=None, status="archived"),
                },
                "event_to_story": {
                    "event-story_000001": "story_000001",
                    "event-story_000002": "story_000002",
                    "event-story_000003": "story_000003",
                    "event-story_000004": "story_000004",
                },
                "story_aliases": {
                    "old-live": "story_000001",
                    "old-cold": "story_000002",
                },
                "quarantined_stories": {},
                "registry_repair": {},
            }
        ),
        encoding="utf-8",
    )

    result = compact_registry_working_set(
        registry_path, history_path=history_path, now=NOW, hot_days=21
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))

    assert result["retired"] == 1
    assert set(payload["stories"]) == {
        "story_000001",
        "story_000003",
        "story_000004",
    }
    assert "event-story_000002" not in payload["event_to_story"]
    assert payload["story_aliases"] == {"old-live": "story_000001"}
    retired = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
    assert retired[0]["story_id"] == "story_000002"
    assert retired[0]["story"]["canonical_title"] == "Story story_000002"


def test_registry_working_set_is_noop_after_cold_story_is_retired(tmp_path):
    registry_path = tmp_path / "editorial_story_registry.json"
    history_path = tmp_path / "editorial_story_history.jsonl"
    registry_path.write_text(
        json.dumps(
            {
                "schema": 10,
                "next_story_id": 2,
                "stories": {
                    "story_000001": _story(
                        "story_000001", published="2026-07-01T12:00:00Z", status="archived"
                    )
                },
                "event_to_story": {"event-story_000001": "story_000001"},
                "story_aliases": {},
                "quarantined_stories": {},
                "registry_repair": {},
            }
        ),
        encoding="utf-8",
    )
    first = compact_registry_working_set(
        registry_path, history_path=history_path, now=NOW, hot_days=21
    )
    history_after_first = history_path.read_text(encoding="utf-8")
    second = compact_registry_working_set(
        registry_path, history_path=history_path, now=NOW, hot_days=21
    )
    assert first["changed"] is True
    assert second["changed"] is False
    assert history_path.read_text(encoding="utf-8") == history_after_first


def test_preflight_receipt_skips_duplicate_story_registry_repair(tmp_path, monkeypatch):
    registry_path = tmp_path / "editorial_story_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema": 10,
                "next_story_id": 1,
                "stories": {},
                "event_to_story": {},
                "story_aliases": {},
                "quarantined_stories": {},
                "registry_repair": {},
            }
        ),
        encoding="utf-8",
    )
    normalize_registry(registry_path)
    receipt = json.loads(preflight_receipt_path(registry_path).read_text(encoding="utf-8"))
    assert receipt["repair_version"] == REPAIR_VERSION
    assert receipt["registry_fingerprint"] == file_fingerprint(registry_path)

    def duplicate_repair_should_not_run(_payload):
        raise AssertionError("duplicate repair ran despite verified preflight receipt")

    monkeypatch.setattr(story_registry_module, "repair_registry_payload", duplicate_repair_should_not_run)
    StoryRegistry(registry_path)


def test_editorial_state_compaction_drops_old_replay_and_filters_snapshot(tmp_path):
    registry_path = tmp_path / "editorial_story_registry.json"
    state_path = tmp_path / "editorial_state.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema": 10,
                "next_story_id": 2,
                "stories": {
                    "story_000001": _story(
                        "story_000001", published="2026-09-25T12:00:00Z"
                    )
                },
                "event_to_story": {"event-story_000001": "story_000001"},
                "story_aliases": {},
                "quarantined_stories": {},
                "registry_repair": {},
            }
        ),
        encoding="utf-8",
    )
    preflight = normalize_registry(registry_path)
    assert preflight["changed"] is False

    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "articles": [
                    {
                        "entry": {"title": "Recent", "published": "Fri, 25 Sep 2026 12:00:00 GMT"},
                        "source": "Example",
                    },
                    {
                        "entry": {"title": "Old", "published": "Wed, 01 Jul 2026 12:00:00 GMT"},
                        "source": "Example",
                    },
                ],
                "pipeline_state": {
                    "version": 1,
                    "candidates": [
                        {
                            "article_id": "recent",
                            "event_key": "event-story_000001",
                            "title": "Recent",
                            "source": "Example",
                            "url": "https://example.com/recent",
                            "is_custom": False,
                            "published_at": "2026-09-25T12:00:00+00:00",
                        },
                        {
                            "article_id": "old",
                            "event_key": "event-old",
                            "title": "Old",
                            "source": "Example",
                            "url": "https://example.com/old",
                            "is_custom": False,
                            "published_at": "2026-07-01T12:00:00+00:00",
                        },
                    ],
                    "snapshots": [
                        {"event_key": "event-story_000001", "facts": [], "status": "developing"},
                        {"event_key": "event-old", "facts": [], "status": "developing"},
                    ],
                },
                "registry_fingerprint": {"algorithm": "sha256", "sha256": "old", "size": 1},
            }
        ),
        encoding="utf-8",
    )

    result = compact_editorial_state_working_set(
        state_path,
        registry_path=registry_path,
        now=NOW,
        hot_days=21,
        repair_version=REPAIR_VERSION,
    )
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert result["articles_dropped"] == 1
    assert len(payload["articles"]) == 1
    assert [row["event_key"] for row in payload["pipeline_state"]["candidates"]] == ["event-story_000001"]
    assert [row["event_key"] for row in payload["pipeline_state"]["snapshots"]] == ["event-story_000001"]
    assert result["registry_fingerprint_rebound"] is True
    assert payload["registry_fingerprint"] == file_fingerprint(registry_path)


def test_production_workflow_bounds_working_set_before_normalize_and_generation():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
    compact_registry = workflow.index("compact_editorial_working_set.py --phase registry")
    normalize = workflow.index("repair_editorial_story_registry.py")
    compact_state = workflow.index("compact_editorial_working_set.py --phase state")
    pytest = workflow.index("python -m pytest tests -v")
    generate = workflow.index("python -u scripts/generate.py")
    assert compact_registry < normalize < compact_state < pytest < generate
    assert 'TCT_STORY_HOT_DAYS: "14"' in workflow


def test_push_step_no_longer_uses_unhandled_git_pull_rebase():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
    helper = (root / "scripts" / "push_generated_update.sh").read_text(encoding="utf-8")
    assert "git pull --rebase" not in workflow
    assert "scripts/push_generated_update.sh" in workflow
    assert "git checkout --theirs" in helper
    assert "sitemap.xml" in helper
    assert "data/custom_articles.json" in helper
    assert "return 1" in helper  # custom/manual source data is never auto-resolved.
