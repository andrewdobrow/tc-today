from __future__ import annotations

import importlib
import os
import sys
import types
from datetime import datetime, timezone

from tct_engine import build_publication_identity_index


def _load_generate_module():
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
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _index():
    return build_publication_identity_index(
        {
            "stories": {
                "story_one": {
                    "canonical_title": "One",
                    "titles": ["One"],
                    "sources": ["https://source.test/one"],
                    "timeline": [{"url": "https://source.test/one"}],
                    "relationship_history": [{"relationship": "new_story"}],
                }
            }
        }
    )


def test_legacy_record_without_a_recent_date_is_not_backfilled_from_source(tmp_path):
    generate = _load_generate_module()
    rows, report = generate._backfill_archive_editorial_story_ids(
        [{"slug": "one", "headline": "One", "source_url": "https://source.test/one"}],
        _index(),
        tmp_path,
        now=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    assert "editorial_story_id" not in rows[0]
    assert rows[0]["legacy_identity_status"] == "legacy_unresolved"
    assert report["resolved"] == 0
    assert report["legacy_unresolved"] == 1


def test_archive_reconciliation_requires_previously_stamped_story_ids():
    generate = _load_generate_module()
    archive = [
        {
            "slug": "one-a",
            "headline": "One",
            "source_url": "https://source.test/one",
        },
        {
            "slug": "one-b",
            "headline": "One rewritten",
            "source_url": "https://source.test/one",
        },
    ]
    cleaned, redirects, report = generate._reconcile_archive_publication_identity(archive, _index())
    assert [entry["slug"] for entry in cleaned] == ["one-a", "one-b"]
    assert redirects == []
    assert report["records_removed"] == 0


def test_archive_reconciliation_keeps_quarantined_drift_outside_canonical_group():
    generate = _load_generate_module()
    identity_index = types.SimpleNamespace(safe_story_ids={"story_one"})
    archive = [
        {
            "slug": "2026-06-12-unrelated-old-event",
            "headline": "Leon County judge to rule Monday on ballot eligibility",
            "editorial_story_id": "story_one",
            "exclude_from_live_recovery": True,
            "identity_quarantine_reason": "headline_slug_event_drift",
        },
        {
            "slug": "2026-07-26-leon-county-judge-to-rule-monday-on-ballot-eligibility",
            "headline": "Leon County judge to rule Monday on ballot eligibility",
            "date": "2026-07-26",
            "lastmod": "2026-07-26",
            "editorial_story_id": "story_one",
        },
    ]

    cleaned, redirects, report = generate._reconcile_archive_publication_identity(
        archive, identity_index
    )

    assert [row["slug"] for row in cleaned] == [row["slug"] for row in archive]
    assert redirects == []
    assert report["records_removed"] == 0


def test_canonical_cleanup_does_not_redirect_repaired_page_back_to_quarantined_source(tmp_path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    old_slug = "2026-06-12-unrelated-old-event"
    repaired_slug = "2026-07-26-current-aligned-story"
    (articles / f"{old_slug}.html").write_text("old", encoding="utf-8")
    (articles / f"{repaired_slug}.html").write_text("new", encoding="utf-8")
    archive = [
        {
            "slug": old_slug,
            "headline": "Current aligned story",
            "source_url": "https://source.test/current-story",
            "exclude_from_live_recovery": True,
            "identity_quarantine_reason": "headline_slug_event_drift",
        },
        {
            "slug": repaired_slug,
            "headline": "Current aligned story",
            "date": "2026-07-26",
            "lastmod": "2026-07-26",
            "source_url": "https://source.test/current-story",
            "editorial_story_id": "story_one",
        },
    ]

    cleaned, redirects = generate.apply_canonical_story_cleanup(
        archive, articles, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [old_slug, repaired_slug]
    assert redirects == []
    assert (articles / f"{repaired_slug}.html").read_text(encoding="utf-8") == "new"
