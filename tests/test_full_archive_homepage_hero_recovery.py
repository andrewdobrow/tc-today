"""The hero must consider published stories beyond the category deck.

No network calls: the canonical archive and article file are local fixtures.
"""
import importlib.util
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _load_generator():
    if "feedparser" not in sys.modules and importlib.util.find_spec("feedparser") is None:
        parser = types.ModuleType("feedparser")
        parser.parse = lambda *a, **k: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = parser
    if "anthropic" not in sys.modules and importlib.util.find_spec("anthropic") is None:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *a, **k: None
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("archive_hero_pool_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stamp(now, h):
    return (now - timedelta(hours=h)).isoformat(timespec="seconds")


def _row(now, *, age=3, slug="2026-10-18-fort-pierce-verified-crash-news", **kwargs):
    value = {
        "slug": slug, "canonical_slug": slug,
        "headline": "Fort Pierce investigators release major new crash findings",
        "teaser": "Fort Pierce police provided a detailed update on a serious local crash.",
        "category_keys": ["crime", "st_lucie"],
        "county_keys": ["st_lucie"],
        "first_published": _stamp(now, age),
        "canonical_first_published_at": _stamp(now, age),
        "date": (now - timedelta(hours=age)).date().isoformat(),
        "lastmod": (now - timedelta(hours=age)).date().isoformat(),
        "ranking_eligible": True,
        "article_word_count": 350,
        "article_paragraph_count": 4,
        "editorial_story_id": "story_12345",
        "source_url": "https://example.org/local/fort-pierce-crash",
    }
    value.update(kwargs)
    return value


def _published(root, row):
    path = root / "articles" / (row["slug"] + ".html")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<html><div class="article-body"><p>Fort Pierce police released details about '
        'the crash and continuing traffic investigation.</p><p>More information '
        'was confirmed by investigators and local officials.</p></div>'
        '<div class="article-share"></div></html>',
        encoding="utf-8",
    )


def _mock_qualities(monkeypatch, g):
    # Production's existing publication/identity/framing checks are used by the
    # new selector; these test fixtures bypass unrelated news-prose heuristics.
    monkeypatch.setattr(g, "_archive_entry_live_identity_safe", lambda entry: True)
    monkeypatch.setattr(g, "_archive_entry_publishable", lambda entry: True)
    monkeypatch.setattr(g, "_archive_entry_has_contextless_update_lead", lambda entry: False)
    monkeypatch.setattr(g, "_archive_entry_has_article_framing_failure", lambda entry: False)
    monkeypatch.setattr(g, "_county_membership_authority_assessment", lambda e, c: {"supported_counties": [c]})
    monkeypatch.setattr(g, "_category_eligibility_contract_assessment", lambda c, e: {"mode": "enforce", "eligible": True})


def _category_old(now):
    old = {
        "headline": "Assisted living proposal drawn from old reporting",
        "teaser": "Port St. Lucie officials discussed a proposal earlier this month.",
        "body": "Port St. Lucie officials discussed a proposal earlier this month.",
        "canonical_slug": "old-assisted-living-proposal",
        "canonical_first_published_at": _stamp(now, 250),
        "ranking_eligible": True,
        "urgency_score": 10,
    }
    return {"category_key": "business", "category_label": "Business & Development", "hero": old, "cards": []}


def test_full_archive_rescues_fresh_story_missing_from_every_category(monkeypatch, tmp_path):
    g = _load_generator()
    _mock_qualities(monkeypatch, g)
    now = datetime.now(timezone.utc)
    recent = _row(now, age=4)
    old = _category_old(now)
    _published(tmp_path, recent)
    (tmp_path / "archive.json").write_text(json.dumps([recent]))
    g.CANONICAL_HERO_FRESHNESS_REPORT_PATH = tmp_path / "data" / "freshness.json"
    result = g.enforce_final_canonical_hero_freshness([old], old, tmp_path)
    assert result["hero"]["headline"] == recent["headline"]
    assert result["hero"]["_archived_slug"] == recent["slug"]
    assert result["hero"]["link"].endswith(recent["slug"] + ".html")
    assert g.FRONT_PAGE_HERO_AUDIT["selection_reason"] == "recovered_newer_verified_article_from_full_archive"


def test_noncanonical_unpublished_ineligible_and_old_records_never_compete(monkeypatch, tmp_path):
    g = _load_generator()
    _mock_qualities(monkeypatch, g)
    now = datetime.now(timezone.utc)
    alias = _row(now, slug="alias", canonical_slug="owner")
    hidden = _row(now, slug="hidden", ranking_eligible=False)
    missing = _row(now, slug="missing")
    outdated = _row(now, slug="expired", age=190)
    for r in (alias, hidden, outdated):
        _published(tmp_path, r)
    selected, report = g._recent_canonical_archive_homepage_hero(
        [alias, hidden, missing, outdated], tmp_path, now=now
    )
    assert selected is None
    assert report["eligible"] == 0


def test_lastmod_does_not_refresh_old_article(monkeypatch, tmp_path):
    g = _load_generator()
    _mock_qualities(monkeypatch, g)
    now = datetime.now(timezone.utc)
    r = _row(now, age=190, lastmod=now.isoformat())
    _published(tmp_path, r)
    result, _ = g._recent_canonical_archive_homepage_hero([r], tmp_path, now=now)
    assert result is None


def test_only_validated_meaningful_update_can_revive_old_story(monkeypatch, tmp_path):
    g = _load_generator()
    _mock_qualities(monkeypatch, g)
    now = datetime.now(timezone.utc)
    r = _row(now, age=190, canonical_last_material_update_at=_stamp(now, 2))
    _published(tmp_path, r)
    none, _ = g._recent_canonical_archive_homepage_hero([r], tmp_path, now=now)
    assert none is None
    r["meaningful_update_validated"] = True
    candidate, report = g._recent_canonical_archive_homepage_hero([r], tmp_path, now=now)
    assert candidate["hero"]["slug"] == r["slug"]
    assert report["selected_age_hours"] < 3


def test_preserves_fresh_existing_hero(monkeypatch, tmp_path):
    g = _load_generator()
    _mock_qualities(monkeypatch, g)
    now = datetime.now(timezone.utc)
    recent = _row(now, age=1)
    _published(tmp_path, recent)
    (tmp_path / "archive.json").write_text(json.dumps([recent]))
    g.CANONICAL_HERO_FRESHNESS_REPORT_PATH = tmp_path / "data" / "freshness.json"
    old = _category_old(now)
    old["hero"]["headline"] = "Fresh existing lead"
    old["hero"]["canonical_first_published_at"] = _stamp(now, 3)
    result = g.enforce_final_canonical_hero_freshness([old], old, tmp_path)
    assert result["hero"]["headline"] == "Fresh existing lead"


def test_no_eligible_canonical_article_still_blocks_stale_homepage(monkeypatch, tmp_path):
    g = _load_generator()
    _mock_qualities(monkeypatch, g)
    (tmp_path / "archive.json").write_text("[]")
    old = _category_old(datetime.now(timezone.utc))
    with pytest.raises(RuntimeError, match="72 hours"):
        g.enforce_final_canonical_hero_freshness([old], old, tmp_path)
