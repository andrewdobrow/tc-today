from __future__ import annotations

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


def test_persistent_story_update_keeps_canonical_despite_headline_slug_drift():
    g = _load_generate()
    target = _legacy_vigil_target()
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
    assert valid is True
    assert reason == "exact_source_url"


def test_exact_source_headline_evolution_keeps_existing_canonical():
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
        assert valid is True
        assert reason == "exact_source_url"


def test_legacy_false_quarantine_is_repaired_and_duplicate_redirected(tmp_path):
    g = _load_generate()
    old = _legacy_vigil_target()
    old["exclude_from_live_recovery"] = True
    old["ranking_eligible"] = False
    old["identity_quarantine_reason"] = "prospective_headline_slug_event_drift"
    old["identity_quarantine_persistent"] = True

    new_slug = "2026-07-27-community-holds-vigil-for-9-year-old-boy-killed-in-dirt-bike-crash"
    new = {
        "slug": new_slug,
        "headline": "Community holds vigil for 9-year-old boy killed in dirt bike crash with FedEx truck",
        "teaser": "The community gathered to remember the child.",
        "category_key": "crime",
        "date": "2026-07-27",
        "lastmod": "2026-07-27",
        "source_url": old["source_url"],
        "editorial_story_id": "story-vigil",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    identity_index = types.SimpleNamespace(safe_story_ids={"story-vigil"})

    cleaned, redirects, ledger, report = g._reconcile_canonical_publication_ledger(
        [old, new], identity_index, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [old["slug"]]
    assert old.get("exclude_from_live_recovery") is None
    assert old.get("identity_quarantine_reason") is None
    assert old["ranking_eligible"] is True
    assert redirects[0]["source_slug"] == new_slug
    assert redirects[0]["target_slug"] == old["slug"]
    assert ledger["key_to_slug"]["story:story-vigil"] == old["slug"]
    assert report["passed"] is True
    assert report["false_quarantines_repaired"] == 1
