from __future__ import annotations

import importlib
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


def _archived_custom():
    return {
        "slug": "2026-07-28-st-lucie-mets-pitcher-conner-ware-named-fsl-pitcher-of-the-week",
        "headline": "St. Lucie Mets pitcher Conner Ware named FSL Pitcher of the Week",
        "teaser": (
            "The 22-year-old left-hander struck out 12 batters over seven scoreless "
            "innings in two appearances against Fort Myers."
        ),
        "category_key": "sports",
        "date": "2026-07-28",
        "first_published": "Mon, 27 Jul 2026 23:15:28 -0400",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:ware-award",
    }


def _rss_copy():
    return {
        "slug": "2026-07-29-st-lucie-mets-pitcher-conner-ware-named-florida-state-league-pitcher-of-the-week",
        "headline": (
            "St. Lucie Mets pitcher Conner Ware named Florida State League "
            "Pitcher of the Week"
        ),
        "teaser": (
            "Ware struck out 12 batters over seven scoreless innings in two "
            "appearances against Fort Myers."
        ),
        "body": (
            "Minor League Baseball announced that St. Lucie Mets pitcher Conner Ware "
            "has been named the Florida State League Pitcher of the Week for the week "
            "of July 20-26, 2026. The Mets won both games in which Ware appeared."
        ),
        "category_key": "sports",
        "date": "2026-07-29",
        "source_url": "https://www.milb.com/st-lucie/news/ware-named-fsl-pitcher-of-the-week",
        "editorial_story_id": "story:rss-ware-award",
        "enriched": True,
    }


def test_exact_ware_custom_and_rss_urls_share_durable_award_identity():
    g = _load_generate()
    matched, key = g._durable_custom_identity_match(_rss_copy(), _archived_custom())
    assert matched is True
    assert key.startswith("sports-award|st-lucie-mets|ware|fsl-pitcher-of-week|")


def test_archived_custom_remains_authoritative_after_queue_entry_is_replaced():
    g = _load_generate()
    match, confidence, basis = g._find_authoritative_custom_incident_match(
        _rss_copy(), archived_customs=[_archived_custom()], current_customs=[]
    )
    assert match["slug"].endswith("conner-ware-named-fsl-pitcher-of-the-week")
    assert confidence == 100
    assert basis == "durable_custom_sports_award_identity"


def test_live_rss_copy_is_removed_when_only_archived_custom_remains():
    g = _load_generate()
    category = {
        "category_key": "sports",
        "hero": _rss_copy(),
        "cards": [{"headline": "Different St. Lucie Mets game recap"}],
    }
    removed = g.suppress_authoritative_custom_incidents_from_live(
        [category], archived_customs=[_archived_custom()], current_customs=[]
    )
    assert len(removed) == 1
    assert removed[0]["basis"] == "durable_custom_sports_award_identity"
    assert category["hero"]["headline"] == "Different St. Lucie Mets game recap"


def test_same_run_archive_cleanup_redirects_escaped_rss_copy_to_custom(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    custom = _archived_custom()
    duplicate = _rss_copy()
    cleaned, redirects = g.apply_canonical_story_cleanup(
        [custom, duplicate], articles, tmp_path
    )
    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate["slug"])
    assert redirect["target_slug"] == custom["slug"]
    assert redirect["match_confidence"] == 100
    assert redirect["canonical_is_custom"] is True


def test_same_player_same_award_in_later_week_is_a_new_story():
    g = _load_generate()
    later = _rss_copy()
    later.update({
        "date": "2026-08-10",
        "headline": "St. Lucie Mets pitcher Conner Ware named FSL Pitcher of the Week again",
        "body": (
            "St. Lucie Mets pitcher Conner Ware was named Florida State League "
            "Pitcher of the Week for the week of August 3-9, 2026."
        ),
    })
    assert g._durable_custom_identity_match(later, _archived_custom())[0] is False


def test_different_player_award_is_not_collapsed_into_conner_ware_custom():
    g = _load_generate()
    other = _rss_copy()
    other["headline"] = "St. Lucie Mets pitcher Ethan Lanthier named FSL Pitcher of the Week"
    other["body"] = (
        "St. Lucie Mets pitcher Ethan Lanthier was named Florida State League "
        "Pitcher of the Week for the week of July 20-26, 2026."
    )
    assert g._durable_custom_identity_match(other, _archived_custom())[0] is False


def test_conner_ware_game_recap_is_not_treated_as_award_duplicate():
    g = _load_generate()
    recap = {
        "headline": "Conner Ware strikes out eight as St. Lucie Mets rally past Fort Myers",
        "body": "Ware threw four scoreless innings in an 11-8 Mets victory.",
        "date": "2026-07-27",
        "category_key": "sports",
    }
    assert g._durable_custom_identity_match(recap, _archived_custom())[0] is False


def test_custom_award_publication_receives_durable_event_key():
    g = _load_generate()
    current = {
        **_archived_custom(),
        "body": (
            "St. Lucie Mets pitcher Conner Ware has been named the Florida State "
            "League Pitcher of the Week for July 20-26, 2026."
        ),
    }
    key = g._custom_event_identity_key(current)
    assert key == "sports-award|st-lucie-mets|ware|fsl-pitcher-of-week|2026-07-26"


def test_known_ware_duplicate_url_is_permanently_redirected_even_when_archive_row_is_gone(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()

    cleaned, redirects = g.apply_canonical_story_cleanup(
        [_archived_custom()], articles, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [g.WARE_AWARD_CANONICAL_SLUG]
    redirect = next(
        row for row in redirects
        if row["source_slug"] in g.WARE_AWARD_REDIRECT_SOURCE_SLUGS
    )
    assert redirect["target_slug"] == g.WARE_AWARD_CANONICAL_SLUG
    assert redirect["canonical_is_custom"] is True
    assert redirect["match_confidence"] == 100


def test_story_regression_gate_covers_known_ware_duplicate(tmp_path):
    import json

    g = _load_generate()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    hoarding_story = {
        "story_id": "story-hoarding",
        "canonical_is_custom": True,
        "canonical_slug": g.HOARDING_CANONICAL_SLUG,
        "articles": [{
            "headline": "Martin County deputies rescue 80 cats from Stuart hoarding home",
            "teaser": "The same large-scale animal-hoarding response.",
        }],
    }
    (data_dir / "stories.json").write_text(
        json.dumps({"stories": [hoarding_story]}), encoding="utf-8"
    )

    redirects = [
        {
            "source_slug": source,
            "target_slug": g.HOARDING_CANONICAL_SLUG,
            "canonical_is_custom": True,
            "reason": "Permanent regression migration to the authoritative TCT hoarding story.",
        }
        for source in g.HOARDING_REDIRECT_SOURCE_SLUGS
    ]
    redirects.extend({
        "source_slug": source,
        "target_slug": g.WARE_AWARD_CANONICAL_SLUG,
        "canonical_is_custom": True,
        "reason": "Permanent regression migration to the authoritative TCT Conner Ware award story.",
    } for source in g.WARE_AWARD_REDIRECT_SOURCE_SLUGS)
    (data_dir / "canonical-redirects.json").write_text(
        json.dumps({"redirects": redirects}), encoding="utf-8"
    )

    hoarding_canonical = {
        "slug": g.HOARDING_CANONICAL_SLUG,
        "headline": "More than 70 animals found in Stuart home during large-scale hoarding response",
        "teaser": "Authorities removed cats and dogs during the hoarding response.",
        "is_custom": True,
        "authoritative_custom": True,
    }
    verification = [
        {
            "source_slug": row["source_slug"],
            "target_slug": row["target_slug"],
            "passed": True,
        }
        for row in redirects
    ]
    report = g.write_story_regression_report(
        tmp_path, [hoarding_canonical, _archived_custom()], verification
    )

    assert report["production_gate_passed"] is True
    assert report["checks"]["ware_custom_article_remains_canonical"] is True
    assert report["checks"]["ware_duplicate_redirect_exists"] is True
    assert report["checks"]["ware_duplicate_targets_custom"] is True
    assert report["checks"]["ware_duplicate_removed_from_archive"] is True
    assert report["checks"]["ware_redirect_html_verified"] is True
