from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser
if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")
    anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda *a, **k: None)
    )
    sys.modules["anthropic"] = anthropic

from scripts import generate

ROOT = Path(__file__).resolve().parents[1]


def _row(*, slug: str, headline: str, source_headline: str, categories: list[str], date: str = "2026-09-04"):
    primary = categories[0]
    return {
        "slug": slug,
        "headline": headline,
        "source_headline": source_headline,
        "source_title": source_headline,
        "category_key": primary,
        "category_label": generate.CATEGORIES[primary]["label"],
        "category_keys": list(categories),
        "county_keys": [],
        "date": date,
        "lastmod": date,
        "ranking_eligible": True,
        "article_word_count": 220,
        "article_paragraph_count": 4,
    }


def test_recent_source_supported_local_story_is_projected_to_county_surface(tmp_path):
    row = _row(
        slug="psl-budget",
        headline="Port St. Lucie council approves budget change",
        source_headline="Port St. Lucie council approves budget change",
        categories=["local_gov"],
    )
    archive, _ = generate._backfill_archive_category_memberships([row], tmp_path)
    assert "st_lucie" in archive[0]["category_keys"]
    report = generate._audit_geographic_navigation_coverage(archive, tmp_path)
    assert report["passed"] is True
    assert report["geographically_covered"] == 1
    assert report["violations"] == 0


def test_true_treasure_coast_wide_story_is_explicit_regional_exception_not_guessed_into_counties(tmp_path):
    row = _row(
        slug="regional-water",
        headline="Treasure Coast water managers prepare for seasonal flooding",
        source_headline="Treasure Coast water managers prepare for seasonal flooding",
        categories=["local_gov"],
    )
    archive, _ = generate._backfill_archive_category_memberships([row], tmp_path)
    assert not set(archive[0]["category_keys"]) & generate.COUNTY_KEYS
    report = generate._audit_geographic_navigation_coverage(archive, tmp_path)
    assert report["passed"] is True
    assert report["regional_exceptions"] == 1
    assert report["violations"] == 0
    saved = json.loads((tmp_path / "data" / "geographic-navigation-coverage-report.json").read_text())
    assert saved["regional_exception_rows"][0]["slug"] == "regional-water"


def test_sports_can_remain_topic_only_when_no_county_is_provable(tmp_path):
    row = _row(
        slug="mets-recap",
        headline="St. Lucie Mets rally for walk-off win",
        source_headline="Mets rally for walk-off win",
        categories=["sports"],
    )
    report = generate._audit_geographic_navigation_coverage([row], tmp_path)
    assert report["passed"] is True
    assert report["topic_exceptions"] == 1
    assert report["violations"] == 0


def test_recent_ordinary_local_story_without_any_geographic_authority_fails_closed(tmp_path):
    row = _row(
        slug="unlocated-government-story",
        headline="Council approves new ordinance",
        source_headline="Council approves new ordinance",
        categories=["local_gov"],
    )
    with pytest.raises(RuntimeError, match="Geographic navigation coverage contract FAILED"):
        generate._audit_geographic_navigation_coverage([row], tmp_path)
    saved = json.loads((tmp_path / "data" / "geographic-navigation-coverage-report.json").read_text())
    assert saved["passed"] is False
    assert saved["violations"] == 1
    assert saved["violation_rows"][0]["reason"] == "ordinary_local_story_has_no_county_florida_or_regional_authority"


def test_current_archive_recent_window_has_no_hidden_ordinary_local_news(tmp_path):
    archive = json.loads((ROOT / "archive.json").read_text(encoding="utf-8"))
    report = generate._audit_geographic_navigation_coverage(archive, tmp_path)
    assert report["passed"] is True
    assert report["violations"] == 0
