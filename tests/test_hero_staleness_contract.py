import importlib.util
from datetime import datetime, timezone
from pathlib import Path


def _load_generate_module():
    path = Path("scripts/generate.py")
    spec = importlib.util.spec_from_file_location("scripts.generate_stale_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _category(key, headline, date_value, body, urgency):
    return {
        "category_key": key,
        "category_label": key,
        "hero": {
            "headline": headline,
            "date": date_value,
            "published_raw": date_value,
            "body": body,
            "teaser": body,
            "urgency_score": urgency,
        },
        "cards": [],
    }


def test_same_day_high_urgency_story_is_not_filtered_by_past_day_language():
    generate = _load_generate_module()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fresh = _category(
        "st_lucie",
        "3 arrested in death of 3-month-old in St. Lucie County",
        today,
        "Deputies said the child was found Thursday and arrests were announced.",
        9,
    )
    stale = _category(
        "martin",
        "Older routine story",
        "2020-01-01",
        "The event happened last week.",
        2,
    )
    selected = generate.select_front_page_hero([fresh, stale])
    assert selected is fresh
    assert all(row["headline"] != fresh["hero"]["headline"] for row in generate.HERO_PREFILTER_AUDIT)
    assert any(row["headline"] == stale["hero"]["headline"] for row in generate.HERO_PREFILTER_AUDIT)


def test_stale_audit_records_date_age_and_reason():
    generate = _load_generate_module()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fresh = _category("crime", "Fresh local story", today, "New details announced today.", 8)
    stale = _category("martin", "Old local story", "2020-01-01", "This happened last week.", 4)
    generate.select_front_page_hero([fresh, stale])
    row = next(item for item in generate.HERO_PREFILTER_AUDIT if item["headline"] == "Old local story")
    assert row["stale"] is True
    assert row["reason"]
    assert row["date_value"] == "2020-01-01"
    assert row["age_hours"] is not None
