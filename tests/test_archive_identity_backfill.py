import importlib.util
import sys
import types
from datetime import datetime, timezone
from pathlib import Path


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_backfill_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Index:
    safe_story_ids = {"story-1", "story-2"}
    all_story_ids = {"story-1", "story-2"}

    def resolve_source(self, item):
        return {
            "https://source.test/one": "story-1",
            "https://source.test/two": "story-2",
        }.get(item.get("source_url"), "")


def test_backfill_persists_recent_exact_source_identity(tmp_path):
    g = _load_generate()
    now = datetime(2026, 7, 25, tzinfo=timezone.utc)
    rows, report = g._backfill_archive_editorial_story_ids(
        [
            {
                "slug": "2026-07-24-one",
                "headline": "One",
                "date": "2026-07-24",
                "source_url": "https://source.test/one",
            },
            {
                "slug": "2026-07-24-unknown",
                "headline": "Unknown",
                "date": "2026-07-24",
                "source_url": "https://source.test/unknown",
            },
        ],
        Index(),
        tmp_path,
        now=now,
    )
    assert rows[0]["editorial_story_id"] == "story-1"
    assert rows[0]["identity_origin"] == "recent_exact_source_backfill"
    assert report["resolved"] == 1
    assert report["recent_unmatched"] == 1
    assert (tmp_path / "data" / "archive-identity-backfill.json").exists()


def test_backfill_never_collapses_custom_recurring_reports(tmp_path):
    g = _load_generate()
    rows, report = g._backfill_archive_editorial_story_ids(
        [
            {
                "slug": "2026-07-25-treasure-coast-traffic-report-july-26-31",
                "headline": "Treasure Coast Traffic Report: Road Work July 26-31",
                "date": "2026-07-25",
                "is_custom": True,
            }
        ],
        Index(),
        tmp_path,
        now=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    assert "editorial_story_id" not in rows[0]
    assert report["custom_isolated"] == 1


def test_existing_safe_identity_is_preserved(tmp_path):
    g = _load_generate()
    rows, report = g._backfill_archive_editorial_story_ids(
        [
            {
                "slug": "2026-07-24-one",
                "headline": "One",
                "date": "2026-07-24",
                "editorial_story_id": "story-1",
            }
        ],
        Index(),
        tmp_path,
        now=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    assert rows[0]["editorial_story_id"] == "story-1"
    assert rows[0]["legacy_identity_status"] == "identified"
    assert report["already_identified"] == 1


def test_old_unresolved_archive_record_is_not_guessed(tmp_path):
    g = _load_generate()
    rows, report = g._backfill_archive_editorial_story_ids(
        [
            {
                "slug": "2025-01-01-one",
                "headline": "One",
                "date": "2025-01-01",
                "source_url": "https://source.test/one",
            }
        ],
        Index(),
        tmp_path,
        now=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    assert "editorial_story_id" not in rows[0]
    assert rows[0]["legacy_identity_status"] == "legacy_unresolved"
    assert rows[0]["ranking_eligible"] is False
    assert report["legacy_unresolved"] == 1


def test_headline_slug_drift_is_quarantined_from_live_recovery(tmp_path):
    g = _load_generate()
    rows, report = g._backfill_archive_editorial_story_ids(
        [
            {
                "slug": "2026-06-12-police-union-backs-paul-renner-and-byron-donalds",
                "headline": "Leon County judge to rule Monday on ballot eligibility",
                "date": "2026-06-12",
                "lastmod": "2026-07-25",
            }
        ],
        Index(),
        tmp_path,
        now=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    assert rows[0]["exclude_from_live_recovery"] is True
    assert rows[0]["legacy_identity_status"] == "quarantined_live_mismatch"
    assert report["quarantined_live_mismatches"] == 1
