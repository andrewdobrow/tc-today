"""Homepage and native Top News must share the final canonical archive eligibility.

Reproduces the Nov. 3, 2026 production incident where Port St. Lucie flooding
was selected as hero despite its archive row having ranking_eligible=False.
The native feed correctly failed closed, but only after expensive generation.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FLOOD_SLUG = (
    "2026-11-02-port-st-lucie-flooding-strands-vehicles-as-police-"
    "urge-residents-to-avoid-travel"
)


def _generator():
    if "feedparser" not in sys.modules and importlib.util.find_spec("feedparser") is None:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules and importlib.util.find_spec("anthropic") is None:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: None
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    spec = importlib.util.spec_from_file_location(
        "generate_hero_feed_parity_recovery", ROOT / "scripts" / "generate.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _archive_row(slug, headline, *, eligible=True, hours_ago=2, **changes):
    now = datetime.now(timezone.utc)
    first_published = (now - timedelta(hours=hours_ago)).isoformat()
    row = {
        "slug": slug,
        "canonical_slug": slug,
        "headline": headline,
        "teaser": headline + " Officials confirmed developments to the public.",
        "date": now.date().isoformat(),
        "first_published": first_published,
        "canonical_first_published_at": first_published,
        "ranking_eligible": eligible,
        "legacy_identity_status": "identified",
        "canonical_publication_id": "publication:" + slug,
        "editorial_story_id": "story:" + slug,
        "article_word_count": 320,
        "article_paragraph_count": 4,
        "source_url": "https://example.org/verified-local-news",
        "category_key": "st_lucie",
        "category_keys": ["st_lucie", "local_gov"],
        "county_keys": ["st_lucie"],
        "urgency_score": 6,
    }
    row.update(changes)
    return row


def _setup(tmp_path, rows):
    (tmp_path / "articles").mkdir()
    (tmp_path / "archive.json").write_text(json.dumps(rows), encoding="utf-8")
    for row in rows:
        (tmp_path / "articles" / (row["slug"] + ".html")).write_text(
            '<html><body><article><p>Confirmed local news reporting.</p>'
            '<p>The source reported updated details.</p></article></body></html>',
            encoding="utf-8",
        )


def _homepage(row):
    hero = dict(row)
    hero.update({
        "_archived_slug": row["slug"],
        "_canonical_freshness_bound": True,
        "link": f"https://treasurecoast.today/articles/{row['slug']}.html",
        "body": row["teaser"],
    })
    return {
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "hero": hero,
        "cards": [],
    }


def _mock_quality_checks(g, monkeypatch):
    # Keep the genuine app-feed canonical/ranking checks. Stub only unrelated
    # prose/category heuristics so these fixtures isolate the failure at hand.
    monkeypatch.setattr(g, "_archive_entry_live_identity_safe", lambda row: True)
    monkeypatch.setattr(g, "_archive_entry_publishable", lambda row: True)
    monkeypatch.setattr(g, "_county_membership_authority_assessment",
                        lambda row, county: {"supported_counties": [county]})
    monkeypatch.setattr(g, "_category_eligibility_contract_assessment",
                        lambda category, row: {"mode": "enforce", "eligible": True})
    monkeypatch.setattr(g, "_archive_entry_has_contextless_update_lead", lambda row: False)
    monkeypatch.setattr(g, "_archive_entry_has_article_framing_failure", lambda row: False)


def test_exact_flood_hero_with_ranking_false_recovers_other_published_news(tmp_path, monkeypatch):
    g = _generator()
    _mock_quality_checks(g, monkeypatch)
    flood = _archive_row(
        FLOOD_SLUG,
        "Flooding closes Port St. Lucie roads, suspends St. Lucie County ART service",
        eligible=False,
    )
    replacement = _archive_row(
        "2026-11-03-fort-pierce-new-crash-investigation",
        "Fort Pierce police release new information about a crash",
        hours_ago=1,
    )
    _setup(tmp_path, [flood, replacement])
    selected = g.enforce_final_homepage_hero_feed_parity(_homepage(flood), tmp_path)
    assert selected["hero"]["_archived_slug"] == replacement["slug"]
    assert selected["hero"]["headline"] == replacement["headline"]
    assert selected["hero"]["link"].endswith(replacement["slug"] + ".html")
    assert g.FRONT_PAGE_HERO_AUDIT["selection_reason"] == "recovered_after_final_feed_parity_rejection"
    assert "ranking_eligible=False" in g.FRONT_PAGE_HERO_AUDIT["rejected_hero"]["reason"]


def test_verified_homepage_hero_remains_unchanged(tmp_path, monkeypatch):
    g = _generator()
    _mock_quality_checks(g, monkeypatch)
    good = _archive_row("2026-11-03-new-stuart-local-government-story",
                        "Stuart council approves updated local plans")
    _setup(tmp_path, [good])
    original = _homepage(good)
    assert g.enforce_final_homepage_hero_feed_parity(original, tmp_path) is original


def test_quarantined_or_noncanonical_row_is_not_promoted(tmp_path, monkeypatch):
    g = _generator()
    _mock_quality_checks(g, monkeypatch)
    flood = _archive_row(FLOOD_SLUG, "Port St. Lucie flooding updates", eligible=False)
    alias = _archive_row(
        "alias-from-redirect", "Port St. Lucie road closure update",
        canonical_slug="another-owner",
    )
    quarantined = _archive_row(
        "recent-quarantined", "Port St. Lucie emergency information",
        eligible=False,
    )
    _setup(tmp_path, [flood, alias, quarantined])
    with pytest.raises(RuntimeError, match="Final homepage hero/feed parity FAILED"):
        g.enforce_final_homepage_hero_feed_parity(_homepage(flood), tmp_path)


def test_published_short_breaking_brief_is_not_falsely_rejected(tmp_path, monkeypatch):
    g = _generator()
    monkeypatch.setattr(g, "_archive_entry_live_identity_safe", lambda row: True)
    brief = _archive_row(
        "2026-11-03-st-lucie-short-breaking-brief",
        "Port St. Lucie officials confirm brief emergency update",
        article_word_count=90,
        article_paragraph_count=2,
    )
    _setup(tmp_path, [brief])
    original = _homepage(brief)
    assert g.enforce_final_homepage_hero_feed_parity(original, tmp_path) is original


def test_writer_is_called_only_after_canonical_homepage_parity_gate():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    fn = source.split("def main(", 1)[1]
    after_reconcile = fn.index("reconcile_homepage_hero_headline_permalink(")
    after_gate = fn.index("top_cat = enforce_final_homepage_hero_feed_parity(top_cat, OUTPUT_DIR)")
    after_render = fn.index("index_html = render_index(all_categories, top_cat)")
    assert after_reconcile < after_gate < after_render
    assert "write_top_news_app_feed(" in source
