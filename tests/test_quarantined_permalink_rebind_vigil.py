from __future__ import annotations

import importlib.util
import json
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
    spec = importlib.util.spec_from_file_location("generate_vigil_permalink_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _legacy_vigil_target():
    return {
        "slug": "2026-07-20-child-killed-another-injured-in-bicycle-crash-with-fedex-truck-in-fort-pierce",
        "headline": "Community gathers to honor 9-year-old boy killed in dirt bike crash with FedEx truck in St. Lucie County",
        "teaser": "Family members, friends and neighbors gathered Tuesday evening to honor the child.",
        "category_key": "crime",
        "date": "2026-07-20",
        "lastmod": "2026-07-22",
        "source_url": "https://www.wptv.com/news/local-news/our-community/fort-pierce/community-gathers-to-honor-9-year-old-boy-killed-in-dirt-bike-and-fedex-truck-crash-in-st-lucie-county",
        "editorial_story_id": "story-vigil",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }


def test_prospective_update_rejects_vigil_target_before_lastmod_exposes_drift():
    g = _load_generate()
    target = _legacy_vigil_target()
    assert g._archive_entry_live_identity_safe(target) is True

    incoming = {
        "headline": target["headline"],
        "teaser": "The community held a vigil as relatives remembered the 9-year-old boy.",
        "source_url": target["source_url"],
        "editorial_story_id": "story-vigil",
        "_editorial_route": "update_existing",
    }
    valid, reason = g._forward_publication_target_valid(
        incoming,
        target,
        "story-vigil",
        "persistent_story_id",
        now=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    assert valid is False
    assert reason == "prospective_headline_slug_event_drift"


def test_both_production_vigil_headlines_trigger_prospective_quarantine():
    g = _load_generate()
    for headline in (
        "Community gathers to honor 9-year-old boy killed in dirt bike crash with FedEx truck in St. Lucie County",
        "Community holds vigil for 9-year-old boy killed in dirt bike crash with FedEx truck",
    ):
        target = _legacy_vigil_target()
        incoming = {
            "headline": headline,
            "teaser": "A new current-run vigil article with substantially refreshed coverage.",
            "source_url": target["source_url"],
            "editorial_story_id": "story-vigil",
        }
        valid, reason = g._forward_publication_target_valid(
            incoming,
            target,
            "story-vigil",
            "exact_source_url",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )
        assert valid is False
        assert reason == "prospective_headline_slug_event_drift"


def test_quarantined_old_target_cannot_become_canonical_or_live_binding(tmp_path):
    g = _load_generate()
    old = _legacy_vigil_target()
    incoming = {
        "headline": "Community holds vigil for 9-year-old boy killed in dirt bike crash with FedEx truck",
        "source_url": old["source_url"],
    }
    assert g._quarantine_archive_publication_target(
        old,
        "prospective_headline_slug_event_drift",
        incoming,
        now=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    assert old["exclude_from_live_recovery"] is True
    assert old["ranking_eligible"] is False
    assert old["identity_quarantine_reason"] == "prospective_headline_slug_event_drift"
    assert old["identity_quarantine_persistent"] is True

    # The normal post-write archive backfill must not erase a prospective quarantine.
    rows, report = g._backfill_archive_editorial_story_ids(
        [old], None, tmp_path, now=datetime(2026, 7, 27, tzinfo=timezone.utc)
    )
    old = rows[0]
    assert old["exclude_from_live_recovery"] is True
    assert old["identity_quarantine_reason"] == "prospective_headline_slug_event_drift"
    assert report["quarantined_live_mismatches"] == 1

    new_slug = "2026-07-27-community-holds-vigil-for-9-year-old-boy-killed-in-dirt-bike-crash"
    new = {
        "slug": new_slug,
        "headline": incoming["headline"],
        "teaser": "The community gathered to remember the child.",
        "category_key": "crime",
        "date": "2026-07-27",
        "lastmod": "2026-07-27",
        "source_url": old["source_url"],
        "editorial_story_id": "story-vigil",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / f"{old['slug']}.html").write_text("<html>old preserved page</html>", encoding="utf-8")
    (articles / f"{new_slug}.html").write_text("<html>new canonical page</html>", encoding="utf-8")

    cleaned, redirects = g.apply_canonical_story_cleanup([old, new], articles, tmp_path)
    assert {row["slug"] for row in cleaned} == {old["slug"], new_slug}
    assert redirects == []

    categories = [
        {
            "category_key": "crime",
            "hero": {
                "headline": "Community gathers to honor 9-year-old boy killed",
                "_archived_slug": old["slug"],
                "link": f"https://treasurecoast.today/articles/{old['slug']}.html",
                "editorial_story_id": "story-vigil",
                "_editorial_story_id": "story-vigil",
            },
            "cards": [],
        },
        {
            "category_key": "st_lucie",
            "hero": {
                "headline": "Community holds vigil for 9-year-old boy killed",
                "_archived_slug": old["slug"],
                "link": f"https://treasurecoast.today/articles/{old['slug']}.html",
                "editorial_story_id": "story-vigil",
                "_editorial_story_id": "story-vigil",
            },
            "cards": [],
        },
    ]
    rebound = g._rebind_live_items_to_published_archive(
        categories, [old, new], articles_dir=articles
    )
    assert rebound == 2
    assert all(cat["hero"]["_archived_slug"] == new_slug for cat in categories)
    assert all(cat["hero"]["link"].endswith(f"/{new_slug}.html") for cat in categories)

    (tmp_path / "archive.json").write_text(
        json.dumps([old, new]), encoding="utf-8"
    )
    (tmp_path / "data").mkdir(exist_ok=True)
    report = g.validate_forward_live_identity(categories, categories[0], tmp_path)
    assert report["passed"] is True
    assert report["violation_count"] == 0
