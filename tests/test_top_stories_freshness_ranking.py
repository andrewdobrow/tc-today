import importlib.util
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
        )
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path("scripts/generate.py")
    spec = importlib.util.spec_from_file_location("scripts.generate_top_stories_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _stamp(now, hours):
    return (now - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _card(headline, now, hours, urgency, *, cat="crime", slug=None, **extra):
    slug = slug or headline.lower().replace(" ", "-")
    return {
        "headline": headline,
        "teaser": headline,
        "body": headline,
        "published_raw": _stamp(now, hours),
        "urgency_score": urgency,
        "cat_key": cat,
        "category_key": cat,
        "enriched": True,
        "_archived_slug": slug,
        "link": f"https://treasurecoast.today/articles/{slug}.html",
        **extra,
    }


def _archive(card, first_published, **extra):
    return {
        "slug": card["_archived_slug"],
        "headline": card["headline"],
        "date": first_published[:10],
        "first_published": first_published,
        **extra,
    }


def test_top_stories_caps_at_twelve_and_rejects_archive_age():
    g = _load_generate()
    now = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
    fresh = [
        _card(f"Fresh story {i}", now, i + 1, 5 + (i % 4), cat="st_lucie")
        for i in range(14)
    ]
    stale_high = _card("Old major story", now, 100, 10, cat="crime")
    cards = fresh + [stale_high]
    archive = [_archive(card, card["published_raw"]) for card in cards]

    selected, report = g._select_top_story_cards(cards, archive, now=now)

    assert len(selected) == 12
    assert stale_high not in selected
    assert all((row["age_hours"] or 0) <= 60 for row in report["selected"])
    assert any(row.get("eligibility_reason") == "older_than_60_hours" for row in report["excluded"])


def test_recent_medium_urgency_can_outrank_older_routine_story():
    g = _load_generate()
    now = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
    recent = _card("Fresh school safety update", now, 2, 6, cat="st_lucie")
    older = _card("Older routine government item", now, 34, 6, cat="local_gov")

    selected, report = g._select_top_story_cards(
        [older, recent],
        [_archive(older, older["published_raw"]), _archive(recent, recent["published_raw"])],
        now=now,
        limit=2,
    )

    assert selected == [recent, older]
    assert report["selected"][0]["priority_score"] > report["selected"][1]["priority_score"]


def test_high_urgency_story_can_survive_extended_window_but_routine_one_cannot_when_pool_is_full():
    g = _load_generate()
    now = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
    fresh = [_card(f"Fresh {i}", now, 4 + i, 6, cat="martin") for i in range(10)]
    urgent_old = _card("Major fatal crash investigation", now, 50, 9, cat="crime")
    routine_old = _card("Routine older commission story", now, 50, 5, cat="local_gov")
    cards = fresh + [urgent_old, routine_old]
    archive = [_archive(card, card["published_raw"]) for card in cards]

    selected, report = g._select_top_story_cards(cards, archive, now=now, limit=12)

    assert urgent_old in selected
    assert routine_old not in selected
    assert any(
        row["headline"] == routine_old["headline"]
        and row.get("eligibility_reason") == "older_than_48_hours_not_urgent_enough"
        for row in report["excluded"]
    )


def test_lastmod_cannot_make_old_archive_story_top_again():
    g = _load_generate()
    now = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
    card = _card("Old story with fresh looking card timestamp", now, 1, 10, slug="old-story")
    old_first = _stamp(now, 24 * 10)
    archive = [_archive(card, old_first, lastmod=now.date().isoformat())]

    selected, report = g._select_top_story_cards([card], archive, now=now)

    assert selected == []
    excluded = next(row for row in report["excluded"] if row["headline"] == card["headline"])
    assert excluded["timestamp_basis"] == "archive:first_published"
    assert excluded["age_hours"] == 240.0


def test_validated_meaningful_update_can_refresh_old_canonical():
    g = _load_generate()
    now = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
    card = _card("Old canonical with major new development", now, 200, 8, slug="old-canonical")
    old_first = _stamp(now, 200)
    archive = [
        _archive(
            card,
            old_first,
            meaningful_update_validated=True,
            last_meaningful_update_at=_stamp(now, 2),
        )
    ]

    selected, report = g._select_top_story_cards([card], archive, now=now)

    assert selected == [card]
    assert report["selected"][0]["age_hours"] == 2.0
    assert report["selected"][0]["timestamp_basis"] == "archive:last_meaningful_update_at"


def test_transient_advisory_and_road_closure_expire_after_one_day():
    g = _load_generate()
    now = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
    flood = _card("Flood Advisory issued for western Martin County", now, 30, 10, cat="martin")
    closure = _card("U.S. 1 closed in both directions after crash", now, 30, 10, cat="st_lucie")
    archive = [_archive(flood, flood["published_raw"]), _archive(closure, closure["published_raw"])]

    selected, report = g._select_top_story_cards([flood, closure], archive, now=now)

    assert selected == []
    reasons = {row["headline"]: row.get("eligibility_reason") for row in report["excluded"]}
    assert reasons[flood["headline"]] == "expired_transient_story"
    assert reasons[closure["headline"]] == "expired_transient_story"


def test_routine_sports_recap_drops_after_24_hours():
    g = _load_generate()
    now = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
    recap = _card("Mets win routine Wednesday game", now, 30, 8, cat="sports")
    archive = [_archive(recap, recap["published_raw"])]

    selected, report = g._select_top_story_cards([recap], archive, now=now)

    assert selected == []
    assert report["excluded"][0]["eligibility_reason"] == "routine_sports_recap_older_than_24_hours"


def test_render_index_no_longer_uses_claude_global_rank_for_top_stories():
    source = Path("scripts/generate.py").read_text(encoding="utf-8")
    render_source = source[source.index("def render_index("):source.index("\ndef slugify", source.index("def render_index("))]
    assert "topnews     = global_rank" not in render_source
    assert "_select_top_story_cards(" in render_source
    assert "limit=TOP_STORIES_LIMIT" in render_source


def test_category_hero_is_projected_into_top_stories_candidate_pool_and_can_rank():
    g = _load_generate()
    now = datetime(2026, 9, 2, 3, 30, tzinfo=timezone.utc)
    slug = "2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach"
    hero = {
        "headline": "Martin County Sheriff's Office investigates body found in Hutchinson Island mangroves",
        "body": "A body found in mangroves is believed to be the missing Oklahoma visitor pending formal identification.",
        "teaser": "A body found in mangroves is believed to be the missing Oklahoma visitor pending formal identification.",
        "published_raw": _stamp(now, 96),
        "urgency_score": 8,
        "_archived_slug": slug,
        "link": f"https://treasurecoast.today/articles/{slug}.html",
        # Archive-recovery heroes are not required to carry the ordinary card flag.
        "enriched": False,
    }
    categories = [{
        "category_key": "martin",
        "category_label": "Martin County",
        "hero": hero,
        "cards": [],
    }]

    candidates = g._category_hero_top_story_candidates(categories)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate is not hero
    assert candidate["headline"] == hero["headline"]
    assert candidate["cat_key"] == "martin"
    assert candidate["enriched"] is True
    assert candidate["_top_stories_category_hero_candidate"] is True
    assert hero["enriched"] is False  # projection must not mutate the category hero

    archive = [{
        "slug": slug,
        "headline": candidate["headline"],
        "date": "2026-08-29",
        "first_published": _stamp(now, 96),
        "meaningful_update_validated": True,
        "last_meaningful_update_at": _stamp(now, 1),
    }]
    selected, report = g._select_top_story_cards(candidates, archive, now=now, limit=12)

    assert selected == [candidate]
    assert report["input_count"] == 1
    assert report["selected"][0]["timestamp_basis"] == "archive:last_meaningful_update_at"
    assert report["selected"][0]["age_hours"] == 1.0


def test_render_index_projects_category_heroes_and_renders_selected_copy_top_news_only():
    source = Path("scripts/generate.py").read_text(encoding="utf-8")
    render_source = source[source.index("def render_index("):source.index("\ndef slugify", source.index("def render_index("))]

    assert "_category_hero_candidates = _category_hero_top_story_candidates(all_categories)" in render_source
    assert "enriched_pool = _category_hero_candidates + [c for c in all_cards_pool if c.get(\"enriched\")]" in render_source
    assert "_category_hero_permalink_keys" in render_source
    assert 'card.get("_top_stories_category_hero_candidate")' in render_source
    assert '_render_data_cat = "all" if _is_category_hero_equivalent else ck' in render_source
    assert 'if _is_category_hero_equivalent:\n            data_cats = "all"' in render_source
