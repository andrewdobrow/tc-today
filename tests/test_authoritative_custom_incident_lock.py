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


def _custom_canonical(g):
    return {
        "slug": g.HOARDING_CANONICAL_SLUG,
        "headline": "More Than 70 Animals Found in Stuart Home During Large-Scale Hoarding Response",
        "teaser": "Authorities rescued dozens of cats and dogs from a Stuart home.",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:hoarding",
    }


def _friday_feed_update():
    return {
        "headline": "100 animals rescued in worst hoarding case Martin County has seen, owners search for missing pets",
        "teaser": "The total reached 100 after 83 cats and 17 dogs were rescued.",
        "body": "On Monday authorities removed 80 cats and 12 dogs. More animals were later rescued.",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/more-animals-rescued-in-martin-county-hoarding-case-as-owners-search-for-missing-pets",
        "enriched": True,
    }


def test_known_event_key_accepts_later_100_animal_count():
    g = _load_generate()
    assert g._known_event_key("100 animals rescued in Martin County's worst hoarding case") == (
        "2026-07-stuart-martin-animal-hoarding"
    )


def test_live_custom_incident_lock_removes_cross_category_copies():
    g = _load_generate()
    custom = _custom_canonical(g)
    crime_copy = _friday_feed_update()
    martin_copy = dict(crime_copy)
    categories = [
        {"category_key": "crime", "hero": crime_copy, "cards": [{"headline": "Other crime story"}]},
        {"category_key": "martin", "hero": {"headline": "Other Martin story"}, "cards": [martin_copy]},
    ]
    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[custom], current_customs=[]
    )
    assert len(removed) == 2
    assert categories[0]["hero"]["headline"] == "Other crime story"
    assert categories[1]["cards"] == []
    assert all(row["canonical_slug"] == g.HOARDING_CANONICAL_SLUG for row in removed)


def test_publication_lock_finds_authoritative_custom_independent_of_stage():
    g = _load_generate()
    custom = _custom_canonical(g)
    match, confidence, basis = g._find_authoritative_custom_incident_match(
        _friday_feed_update(), archived_customs=[custom], current_customs=[]
    )
    assert match["slug"] == g.HOARDING_CANONICAL_SLUG
    assert confidence == 100
    assert basis == "exact_known_event_key"


def test_same_run_canonical_cleanup_redirects_july_25_duplicate(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    duplicate_slug = (
        "2026-07-25-100-animals-rescued-in-worst-hoarding-case-"
        "martin-county-has-seen-owners-search"
    )
    archive = [
        _custom_canonical(g),
        {
            "slug": duplicate_slug,
            **_friday_feed_update(),
            "editorial_story_id": "story-generated-follow-up",
        },
    ]
    cleaned, redirects = g.apply_canonical_story_cleanup(archive, articles, tmp_path)
    assert [row["slug"] for row in cleaned] == [g.HOARDING_CANONICAL_SLUG]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate_slug)
    assert redirect["target_slug"] == g.HOARDING_CANONICAL_SLUG
    assert redirect["canonical_is_custom"] is True


def test_unrelated_animal_story_survives_custom_incident_lock():
    g = _load_generate()
    custom = _custom_canonical(g)
    categories = [{
        "category_key": "crime",
        "hero": {
            "headline": "Three dogs rescued after being abandoned near I-95 in Martin County",
            "body": "The animals were found beside Bridge Road.",
        },
        "cards": [],
    }]
    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[custom], current_customs=[]
    )
    assert removed == []
    assert categories[0]["hero"] is not None
