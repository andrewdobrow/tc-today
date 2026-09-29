import importlib.util
import json
import os
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
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)
        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    if "json_repair" not in sys.modules:
        json_repair = types.ModuleType("json_repair")
        json_repair.repair_json = lambda value: value
        sys.modules["json_repair"] = json_repair
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_temporal_hero_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


generate = _load_generate()


def test_scheduled_execution_source_cannot_be_rewritten_as_completed():
    source = {
        "title": "Florida is set to execute a 77-year-old man convicted of a 1995 murder",
        "summary": "Curtis Beasley is scheduled Tuesday to become Florida's 16th execution this year.",
        "article_text": (
            "Curtis Wilkie Beasley is scheduled Tuesday to become the 16th person executed "
            "this year. He is set to receive a three-drug injection starting at 6 p.m."
        ),
    }
    generated = {
        "headline": "Florida executes 77-year-old Curtis Beasley, state's 16th this year",
        "body": (
            "Florida executed Curtis Wilkie Beasley on Tuesday evening. Beasley, 77, "
            "received a lethal injection at the state prison starting at 6 p.m."
        ),
    }
    diag = generate._scheduled_execution_temporal_diagnostics(generated, source)
    assert diag["required"] is True
    assert diag["passed"] is False
    assert "scheduled_execution_reported_as_completed" in diag["missing"]

    framing = generate._article_framing_diagnostics(generated, source)
    assert framing["passed"] is False
    assert "scheduled_execution_reported_as_completed" in framing["missing"]


def test_confirmed_execution_source_can_support_completed_tense():
    source = {
        "title": "Florida executes Curtis Beasley after final appeals denied",
        "article_text": (
            "Florida executed Curtis Wilkie Beasley Tuesday evening. He received a lethal "
            "injection and was pronounced dead at 6:12 p.m."
        ),
    }
    generated = {
        "headline": "Florida executes Curtis Beasley",
        "body": "Florida executed Curtis Beasley Tuesday evening after his final appeals were denied.",
    }
    diag = generate._scheduled_execution_temporal_diagnostics(generated, source)
    # No future-only source evidence remains, so ordinary framing rules apply.
    assert diag["passed"] is True


def test_late_archive_guard_uses_preserved_source_title_not_generated_body():
    archived = {
        "headline": "Florida executes 77-year-old Curtis Beasley, state's 16th this year",
        "body": "Florida executed Curtis Beasley Tuesday evening.",
        "source_title": "Florida is set to execute a 77-year-old man convicted of a 1995 murder",
        "source_summary": "Beasley is scheduled to be executed Tuesday at 6 p.m.",
    }
    diag = generate._scheduled_execution_temporal_diagnostics(archived, archived)
    assert diag["passed"] is False
    assert diag["source_confirms_completion"] is False


def test_canonical_hero_lifetime_uses_first_publication_not_last_update():
    item = {
        "headline": "I-95 northbound in Martin County reopens after fatal crash closes lanes over 7 hours",
        "canonical_slug": "2026-09-28-driver-killed-after-honda-slams-into-box-truck-bursts-into-flames-on-i-95-in-mar",
        "canonical_first_published_at": "2026-09-28T09:04:00-04:00",
        "canonical_last_material_update_at": "2026-09-28T22:13:00-04:00",
        "meaningful_update_validated": True,
    }
    now = datetime.fromisoformat("2026-09-29T13:34:00-04:00").astimezone(timezone.utc)
    generate.CANONICAL_HERO_REFRESHED_SLUGS_THIS_RUN.clear()
    assessment = generate._canonical_hero_freshness_assessment(item, now=now)
    assert assessment["stale"] is True
    assert assessment["reason"] == "aged_canonical_update_hero_window_expired"
    assert assessment["first_publication_age_hours"] > 24


def test_same_run_validated_update_gets_one_immediate_hero_exception():
    slug = "old-story-with-real-new-development"
    item = {
        "headline": "Old canonical receives a genuinely new development",
        "canonical_slug": slug,
        "canonical_first_published_at": "2026-09-27T09:00:00-04:00",
        "canonical_last_material_update_at": "2026-09-29T13:20:00-04:00",
        "meaningful_update_validated": True,
    }
    now = datetime.fromisoformat("2026-09-29T13:34:00-04:00").astimezone(timezone.utc)
    generate.CANONICAL_HERO_REFRESHED_SLUGS_THIS_RUN.clear()
    generate.CANONICAL_HERO_REFRESHED_SLUGS_THIS_RUN.add(slug)
    try:
        assessment = generate._canonical_hero_freshness_assessment(item, now=now)
        assert assessment["stale"] is False
        assert assessment["reason"] == "validated_meaningful_update_fresh"
        assert assessment["refreshed_this_run"] is True
    finally:
        generate.CANONICAL_HERO_REFRESHED_SLUGS_THIS_RUN.clear()


def test_front_page_selector_replaces_over_24_hour_canonical_when_fresh_local_exists(monkeypatch):
    fixed_now = datetime.fromisoformat("2026-09-29T13:34:00-04:00").astimezone(timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(generate, "datetime", FixedDateTime)
    generate.CANONICAL_HERO_REFRESHED_SLUGS_THIS_RUN.clear()

    old_crash = {
        "headline": "I-95 northbound in Martin County reopens after fatal crash closes lanes over 7 hours",
        "teaser": "The fatal crash closed I-95 Monday.",
        "body": "A fatal crash closed Interstate 95 in Martin County Monday morning before lanes reopened.",
        "urgency_score": 10,
        "canonical_slug": "old-crash",
        "canonical_first_published_at": "2026-09-28T09:04:00-04:00",
        "canonical_last_material_update_at": "2026-09-28T22:13:00-04:00",
        "meaningful_update_validated": True,
        "ranking_eligible": True,
    }
    fresh_local = {
        "headline": "Port St. Lucie schedules removal of 18 Flock cameras by Sept. 30",
        "teaser": "Port St. Lucie officials said the cameras will be removed this week.",
        "body": "Port St. Lucie will remove 18 Flock cameras installed in county and state rights-of-way.",
        "urgency_score": 6,
        "published": "Tue, 29 Sep 2026 13:20:00 -0400",
        "ranking_eligible": True,
    }
    categories = [
        {"category_key": "martin", "category_label": "Martin County", "hero": old_crash, "cards": []},
        {"category_key": "local_gov", "category_label": "Local Government", "hero": fresh_local, "cards": []},
    ]
    selected = generate.select_front_page_hero(categories, deterministic_only=True)
    assert selected["hero"]["headline"] == fresh_local["headline"]


def test_content_override_active_until_expires_without_deleting_override(tmp_path):
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps({
        "version": 1,
        "overrides": {
            "article-a": {"headline": "Temporary correction", "active_until": "2026-09-29T18:15:00-04:00"},
            "article-b": {"headline": "Permanent correction"},
        },
    }))
    before = datetime.fromisoformat("2026-09-29T17:00:00-04:00").astimezone(timezone.utc)
    after = datetime.fromisoformat("2026-09-29T19:00:00-04:00").astimezone(timezone.utc)
    assert "article-a" in generate._load_article_content_overrides(path, now=before)
    assert "article-a" not in generate._load_article_content_overrides(path, now=after)
    assert "article-b" in generate._load_article_content_overrides(path, now=after)


def test_beasley_correction_override_is_present_and_time_bounded():
    payload = json.loads((Path(__file__).resolve().parents[1] / "data" / "article-content-overrides.json").read_text())
    row = payload["overrides"]["2026-09-29-florida-executes-77-year-old-curtis-beasley-states-16th-this-year"]
    assert row["headline"].startswith("Florida set to execute 77-year-old Curtis Beasley")
    assert "scheduled for 6 p.m. Tuesday" in row["update_text"]
    assert row["active_until"] == "2026-09-29T18:15:00-04:00"
