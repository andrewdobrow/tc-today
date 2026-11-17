"""Coverage contracts: no invented sports, forced quotas, or box-score spam."""
from datetime import datetime
from zoneinfo import ZoneInfo

from tct_engine.local_sports_editorial import (
    SPORTS_ASSIGNMENT_RULE,
    SPORTS_EDITORIAL_VERSION,
    SPORTS_PER_RUN_MAX,
    SPORTS_WEEKLY_MAX,
    SPORTS_WEEKLY_TARGET_LOW,
    SPORTS_WRITER_RULE,
    filter_sports_sources,
    sports_source_decision,
    sports_weekly_budget,
)

ET = ZoneInfo("America/New_York")


def test_sports_has_broad_competitive_scope_and_no_mandatory_quota():
    assert SPORTS_WEEKLY_TARGET_LOW == 4
    assert SPORTS_WEEKLY_MAX == 6
    assert SPORTS_PER_RUN_MAX == 2
    for sport in ("basketball", "golf"):
        # Neither of these sports is an exclusive requirement.
        assert sport not in SPORTS_ASSIGNMENT_RULE.lower()
    assert "ALL genuinely local competitive sports" in SPORTS_ASSIGNMENT_RULE
    assert "Publishing fewer stories" in SPORTS_ASSIGNMENT_RULE
    assert "final score alone" in SPORTS_WRITER_RULE


def test_scoreboard_only_sourcing_rejected_but_real_recaps_allowed():
    score = {
        "title": "High school basketball scoreboard: Tuesday scores",
        "link": "https://example.org/news/scoreboard",
        "article_text": "Local scores and fixtures",
    }
    assert not sports_source_decision(score)["eligible"]
    result = {
        "title": "Jensen Beach clinches district soccer title after late winner",
        "link": "https://example.org/news/jensen-beach-soccer-title",
        "article_text": "A named team advanced after a decisive second-half goal. "
        "The source identifies the opponent, result, and next postseason opponent.",
    }
    assert sports_source_decision(result)["eligible"]
    for sport in ("volleyball", "wrestling", "golf", "soccer", "softball", "swimming", "lacrosse", "track"):
        assert sports_source_decision({
            "title": f"Vero Beach {sport} team wins district championship",
            "link": "https://example.org/news/locals",
            "article_text": "Verified local competition and standings.",
        })["eligible"]


def test_score_only_title_requires_substantive_reporting():
    row = {"title": "Vero Beach 62, Sebastian River 59", "article_text": "Vero Beach won 62-59."}
    assert sports_source_decision(row)["reason"] == "score_only_without_reporting"
    row["article_text"] = "The local high school game had verified key plays. " * 35
    assert sports_source_decision(row)["eligible"]


def test_topic_filter_applies_only_to_sports_and_does_not_modify_sources():
    listing = {"title": "College scoreboard", "link": "https://example.com/scores/"}
    real = {"title": "Martin County swimmers win regional championship"}
    local, rejects = filter_sports_sources("sports", [listing, real])
    assert local == [real] and len(rejects) == 1
    untouched, no_rejects = filter_sports_sources("martin", [listing, real])
    assert untouched == [listing, real] and not no_rejects


def test_weekly_ceiling_counts_primary_sports_once_and_is_not_a_floor():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=ET)
    rows = [
        {"category_key": "sports", "date": "2026-11-16", "canonical_slug": "a"},
        {"category_key": "sports", "date": "2026-11-16", "canonical_slug": "a"},
        {"category_key": "sports", "date": "2026-11-17", "canonical_slug": "b"},
        {"category_key": "martin", "category_keys": ["sports", "martin"], "date": "2026-11-17", "slug": "not-sports"},
        {"category_key": "sports", "date": "2026-11-08", "slug": "older"},
    ]
    budget = sports_weekly_budget(rows, now=now)
    assert budget["published"] == 2
    assert budget["remaining_week"] == 4
    assert budget["available_this_run"] == 2
    assert sports_weekly_budget([], now=now)["available_this_run"] == 2
    assert sports_weekly_budget(rows + [
        {"category_key": "sports", "date": "2026-11-18", "slug": str(x)}
        for x in range(4)
    ], now=now)["available_this_run"] == 0


def test_sports_contract_is_wired_to_production_source_and_models():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text()
    assert "SPORTS_EDITORIAL_VERSION" in source
    assert "sports_weekly_budget(_pre_generation_archive)" in source
    assert "filter_sports_sources(cat_key, headlines)" in source
    assert "SPORTS_ASSIGNMENT_RULE" in source
    assert "SPORTS_WRITER_RULE" in source
    assert '\"sports_weekly_available\"' in source
    assert SPORTS_EDITORIAL_VERSION.startswith("curated-local-sports-v")
