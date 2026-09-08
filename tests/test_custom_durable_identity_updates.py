from __future__ import annotations

import importlib
import json
import os
import sys
import types


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


OLD_SLUG = "2026-09-07-looking-for-something-to-do-5-treasure-coast-events-for-sept-11-13"
DUP_SLUG = "2026-09-07-looking-for-something-to-do-this-weekend-here-are-the-top-5-treasure-coast-event"
BODY = (
    "Annual 9/11 Memorial Tribute in Palm City. "
    "Family Fun Day and Touch A Truck in Sebastian. "
    "Bite Into History will attempt a 400-foot Cuban sandwich. "
    "Coastal Championship Wrestling is in Port St. Lucie. "
    "A Kenny Chesney tribute is in Fort Pierce this weekend."
)


def _row(g, slug, headline, first_published, story_id):
    return {
        "slug": slug,
        "headline": headline,
        "teaser": "Five Treasure Coast events worth checking out this weekend.",
        "body": BODY,
        "category_key": "things_to_do",
        "date": "2026-09-07",
        "first_published": first_published,
        "is_custom": True,
        "authoritative_custom": True,
        "custom_body_hash": g._custom_body_hash(BODY),
        "custom_edition_key": "sept-11-13" if slug == OLD_SLUG else "sep-11-13",
        "editorial_story_id": story_id,
        "ranking_eligible": True,
        "legacy_identity_status": "identified",
    }


def test_sep_and_sept_weekend_headlines_share_durable_publication_key():
    g = _load_generate()
    a = {
        "headline": "Looking for something to do? 5 Treasure Coast events for Sept. 11-13",
        "teaser": "Five Treasure Coast events this weekend.",
        "body": BODY,
        "category": "things_to_do",
    }
    b = {
        "headline": "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events from Sep. 11-13",
        "teaser": "Five Treasure Coast events this weekend.",
        "body": BODY,
        "category_key": "things_to_do",
    }
    assert g._custom_edition_marker(a) == "sep-11-13"
    assert g._custom_edition_marker(b) == "sep-11-13"
    assert g._custom_series_key(a) == "treasure-coast-weekend-events"
    assert g._custom_series_key(b) == "treasure-coast-weekend-events"
    assert g._custom_publication_key(a) == g._custom_publication_key(b)
    assert g._custom_publication_key(a) == (
        "series:treasure-coast-weekend-events|edition:sep-11-13"
    )


def test_third_headline_edit_resolves_to_original_first_permalink():
    g = _load_generate()
    first = _row(
        g,
        OLD_SLUG,
        "Looking for something to do? 5 Treasure Coast events for Sept. 11-13",
        "Mon, 07 Sep 2026 19:00:51 -0400",
        "custom:first",
    )
    duplicate = _row(
        g,
        DUP_SLUG,
        "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events from Sep. 11-13",
        "Mon, 07 Sep 2026 19:23:29 -0400",
        "custom:duplicate",
    )
    third = {
        "headline": "5 things to do on the Treasure Coast this weekend, Sept. 11-13",
        "teaser": "Five Treasure Coast events this weekend.",
        "body": BODY,
        "category": "things_to_do",
        "is_custom": True,
        "authoritative_custom": True,
        "_custom_active_queue": True,
        "custom_body_hash": g._custom_body_hash(BODY),
    }

    target, forced, story_id = g._resolve_custom_publication_target(
        third, [duplicate, first], duplicate, third["headline"]
    )

    assert target is first
    assert target["slug"] == OLD_SLUG
    assert forced is None
    assert story_id == "custom:first"


def test_loader_headline_edit_reuses_original_slug_and_rewrites_page(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    first = _row(
        g,
        OLD_SLUG,
        "Looking for something to do? 5 Treasure Coast events for Sept. 11-13",
        "Mon, 07 Sep 2026 19:00:51 -0400",
        "custom:first",
    )
    duplicate = _row(
        g,
        DUP_SLUG,
        "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events from Sep. 11-13",
        "Mon, 07 Sep 2026 19:23:29 -0400",
        "custom:duplicate",
    )
    (tmp_path / "archive.json").write_text(json.dumps([duplicate, first]), encoding="utf-8")
    (tmp_path / "custom_articles.json").write_text(json.dumps([{
        "headline": "5 things to do on the Treasure Coast this weekend, Sept. 11-13",
        "teaser": "Five Treasure Coast events this weekend.",
        "body": BODY,
        "category": "things_to_do",
        "expires": "2099-01-01",
    }]), encoding="utf-8")

    loaded = g.load_custom_articles()

    assert len(loaded) == 1
    assert loaded[0]["replace_slug"] == OLD_SLUG
    assert loaded[0]["custom_publication_key"] == (
        "series:treasure-coast-weekend-events|edition:sep-11-13"
    )
    # Same body but changed headline is an editorial change and must rewrite the page.
    assert loaded[0].get("_custom_payload_unchanged") is not True


def test_canonical_ledger_collapses_existing_weekend_duplicates(tmp_path):
    g = _load_generate()
    first = _row(
        g,
        OLD_SLUG,
        "Looking for something to do? 5 Treasure Coast events for Sept. 11-13",
        "Mon, 07 Sep 2026 19:00:51 -0400",
        "custom:first",
    )
    duplicate = _row(
        g,
        DUP_SLUG,
        "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events from Sep. 11-13",
        "Mon, 07 Sep 2026 19:23:29 -0400",
        "custom:duplicate",
    )

    cleaned, redirects, ledger, report = g._reconcile_canonical_publication_ledger(
        [duplicate, first], None, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [OLD_SLUG]
    assert len(redirects) == 1
    assert redirects[0]["source_slug"] == DUP_SLUG
    assert redirects[0]["target_slug"] == OLD_SLUG
    assert report["groups_collapsed"] == 1
    assert ledger["key_conflicts"] == {}


def test_explicit_custom_id_allows_headline_and_body_edits_without_new_slug():
    g = _load_generate()
    old = {
        "slug": "original-custom-permalink",
        "headline": "Original title",
        "body": "old body",
        "category_key": "local_gov",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_id": "city-budget-2026",
        "custom_publication_key": "id:city-budget-2026",
        "editorial_story_id": "custom:budget",
    }
    edited = {
        "headline": "Completely rewritten title",
        "body": "completely rewritten body",
        "category": "local_gov",
        "is_custom": True,
        "authoritative_custom": True,
        "_custom_active_queue": True,
        "custom_id": "city-budget-2026",
    }

    target, forced, story_id = g._resolve_custom_publication_target(
        edited, [old], None, edited["headline"]
    )

    assert target is old
    assert forced is None
    assert story_id == "custom:budget"


def test_different_custom_ids_and_different_sports_recaps_stay_distinct():
    g = _load_generate()
    old = {
        "slug": "old-game",
        "headline": "Cardinals beat St. Lucie Mets",
        "body": "old game body",
        "category_key": "sports",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_id": "mets-game-july-19",
    }
    new = {
        "headline": "Mets fall to Mighty Mussels",
        "body": "different game body",
        "category": "sports",
        "is_custom": True,
        "authoritative_custom": True,
        "_custom_active_queue": True,
        "custom_id": "mets-game-july-25",
    }
    target, forced, _ = g._resolve_custom_publication_target(
        new, [old], old, new["headline"]
    )
    assert target is None
    assert forced is None


def test_live_third_headline_wording_still_binds_to_original_first_permalink():
    g = _load_generate()
    first = _row(
        g,
        OLD_SLUG,
        "Looking for something to do? 5 Treasure Coast events for Sept. 11-13",
        "Mon, 07 Sep 2026 19:00:51 -0400",
        "custom:first",
    )
    duplicate = _row(
        g,
        DUP_SLUG,
        "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events from Sep. 11-13",
        "Mon, 07 Sep 2026 19:23:29 -0400",
        "custom:duplicate",
    )
    live_third = {
        "headline": "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events for Sep. 11-13",
        "teaser": "From a Friday-night 9/11 memorial tribute to a 400-foot Cuban sandwich attempt, live wrestling and a Sunday country show, here are five Treasure Coast events worth checking out this weekend.",
        "body": BODY,
        "category": "things_to_do",
        "is_custom": True,
        "authoritative_custom": True,
        "_custom_active_queue": True,
    }

    assert g._custom_publication_key(live_third) == (
        "series:treasure-coast-weekend-events|edition:sep-11-13"
    )
    target, forced, story_id = g._resolve_custom_publication_target(
        live_third, [duplicate, first], duplicate, live_third["headline"]
    )
    assert target is first
    assert target["slug"] == OLD_SLUG
    assert forced is None
    assert story_id == "custom:first"


def test_stable_weekend_publication_allows_headline_to_add_weekend_without_changing_slug():
    g = _load_generate()
    entry = {
        "slug": OLD_SLUG,
        "headline": "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events for Sep. 11-13",
        "permalink_origin_headline": "Looking for something to do? 5 Treasure Coast events for Sept. 11-13",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_publication_key": "series:treasure-coast-weekend-events|edition:sep-11-13",
        "custom_series_key": "treasure-coast-weekend-events",
        "custom_edition_key": "sep-11-13",
        "lastmod": "2026-09-07",
    }

    # The original permalink predates the word "weekend" in the edited headline.
    # Stable custom identity must preserve that URL as long as the edition still matches.
    assert "weekend" not in OLD_SLUG
    assert g._custom_series_slug_mismatch(entry, OLD_SLUG) is False
    assert g._archive_headline_slug_alignment(entry)["aligned"] is True


def test_stable_custom_identity_still_rejects_wrong_recurring_edition_slug():
    g = _load_generate()
    entry = {
        "slug": "2026-07-10-treasure-coast-traffic-report-july-12-17",
        "headline": "Treasure Coast Traffic Report: I-95 Work Planned July 26-31",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_publication_key": "series:treasure-coast-traffic-report|edition:jul-26-31",
        "custom_series_key": "treasure-coast-traffic-report",
        "custom_edition_key": "jul-26-31",
        "lastmod": "2026-07-25",
    }

    result = g._archive_headline_slug_alignment(entry)
    assert result["aligned"] is False
    assert result["reason"] == "recurring_custom_edition_slug_mismatch"


def test_post_publication_rebind_uses_durable_custom_key_not_current_headline(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS", [])
    publication_key = "series:treasure-coast-weekend-events|edition:sep-11-13"
    archive_entry = {
        "slug": OLD_SLUG,
        "headline": "Looking for something to do? 5 Treasure Coast events for Sept. 11-13",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_publication_key": publication_key,
        "custom_series_key": "treasure-coast-weekend-events",
        "custom_edition_key": "sep-11-13",
        "editorial_story_id": "custom:first",
        "category_key": "things_to_do",
        "ranking_eligible": True,
    }
    (tmp_path / "archive.json").write_text(json.dumps([archive_entry]), encoding="utf-8")
    live = {
        "headline": "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events for Sep. 11-13",
        "body": BODY,
        "category": "things_to_do",
        "category_key": "things_to_do",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_publication_key": publication_key,
        "_current_custom_publication_slug": OLD_SLUG,
        "_archived_slug": OLD_SLUG,
    }
    categories = [{"category_key": "things_to_do", "hero": live, "cards": []}]

    rebound = g._rebind_current_custom_editions_to_archive(categories, categories[0], tmp_path)

    assert rebound
    assert live["_archived_slug"] == OLD_SLUG
    assert live["headline"].startswith("Looking for something to do this weekend?")
    report = json.loads((tmp_path / "data" / "custom-post-publication-rebind.json").read_text())
    assert report["unresolved_count"] == 0
    assert report["identity_contract"].startswith("durable_custom_publication")


def test_forward_live_identity_accepts_edited_weekend_headline_on_original_permalink(tmp_path):
    g = _load_generate()
    (tmp_path / "data").mkdir()
    publication_key = "series:treasure-coast-weekend-events|edition:sep-11-13"
    headline = "Looking for something to do this weekend? Here are the Top 5 Treasure Coast events for Sep. 11-13"
    story_id = "custom:first"
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": OLD_SLUG,
        "headline": headline,
        "permalink_origin_headline": "Looking for something to do? 5 Treasure Coast events for Sept. 11-13",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_publication_key": publication_key,
        "custom_series_key": "treasure-coast-weekend-events",
        "custom_edition_key": "sep-11-13",
        "editorial_story_id": story_id,
        "category_key": "things_to_do",
        "ranking_eligible": True,
        "lastmod": "2026-09-07",
    }]), encoding="utf-8")
    placement = {
        "headline": headline,
        "slug": OLD_SLUG,
        "_archived_slug": OLD_SLUG,
        "link": f"https://treasurecoast.today/articles/{OLD_SLUG}.html",
        "editorial_story_id": story_id,
        "is_custom": True,
        "authoritative_custom": True,
        "custom_publication_key": publication_key,
    }
    categories = [{"category_key": "things_to_do", "hero": placement, "cards": []}]

    report = g.validate_forward_live_identity(categories, categories[0], tmp_path)

    assert report["passed"] is True
    assert report["violation_count"] == 0
