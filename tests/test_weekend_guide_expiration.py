"""Weekend-guide expiration contracts independent of the one-item editorial queue."""
from __future__ import annotations

import importlib
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "custom_articles.json"
CURRENT_ID = "treasure-coast-top-five-weekend-2026-10-24-25"
WEEKEND_FIXTURE = ROOT / "tests" / "fixtures" / "weekend_top_five_oct_24_25_2026.json"
OLD_ID = "treasure-coast-top-five-weekend-2026-10-10-11"


def _items():
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def _weekend_example():
    """Use the historical Oct. 24–25 submission without requeueing it."""
    return json.loads(WEEKEND_FIXTURE.read_text(encoding="utf-8"))


def _engine():
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


def _as_of(monkeypatch, engine, instant):
    original = engine.datetime
    class FrozenDateTime(original):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return instant.replace(tzinfo=None)
            return instant.astimezone(tz)
    monkeypatch.setattr(engine, "datetime", FrozenDateTime)


def test_october_tenth_weekend_guide_expires_after_events(monkeypatch, tmp_path):
    """Retired Oct. 10–11 edition may be archived, but cannot be live now."""
    old = {
        "custom_id": OLD_ID,
        "slug": "2026-10-09-treasure-coast-weekend-events-oct-10-11",
        "headline": "Top five weekend events for Oct. 10-11",
        "teaser": "Historical calendar guide.",
        "body": "Five historical weekend events.",
        "category": "things_to_do",
        "publish_on": "2026-10-09",
        "expires": "2026-10-12",
    }
    (tmp_path / "custom_articles.json").write_text(json.dumps([old]), encoding="utf-8")
    engine = _engine()
    monkeypatch.setattr(engine, "OUTPUT_DIR", tmp_path)
    _as_of(monkeypatch, engine, datetime(2026, 10, 21, 12, tzinfo=timezone.utc))
    assert not any(x.get("custom_id") == OLD_ID for x in engine.load_custom_articles())
    assert all(x.get("custom_id") != OLD_ID for x in _items())


def test_stale_weekend_guide_cannot_stay_in_active_queue(monkeypatch, tmp_path):
    """The generator must ignore an expired queued guide rather than republish it."""
    # A dated guide must expire even after it leaves the active editorial queue.
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([_weekend_example()]), encoding="utf-8"
    )
    engine = _engine()
    monkeypatch.setattr(engine, "OUTPUT_DIR", tmp_path)
    _as_of(monkeypatch, engine, datetime(2026, 10, 27, 12, tzinfo=timezone.utc))
    assert not any(x.get("custom_id") == CURRENT_ID for x in engine.load_custom_articles())


def test_weekend_event_guides_in_current_editor_queue_have_expiration():
    # Queue entries change whenever a new custom article is submitted. Check
    # each queued weekend guide, without requiring a retired guide to remain.
    for row in _items():
        if "weekend" not in str(row.get("custom_id", "")).lower():
            continue
        expiry = row.get("expires")
        assert isinstance(expiry, str) and expiry, (
            f"Date-specific weekend guide requires expires: {row['headline']}"
        )
        expires_on = datetime.strptime(expiry, "%Y-%m-%d").date()
        publish_on = datetime.strptime(row["publish_on"], "%Y-%m-%d").date()
        assert expires_on > publish_on
    # Separately retain the specific Oct. 24–25 expiration regression.
    example = _weekend_example()
    assert example["expires"] == "2026-10-26"


def test_current_weekend_guide_is_available_through_sunday_evening(monkeypatch, tmp_path):
    """Oct 25 evening hike should not be discarded by a UTC-midnight cutoff."""
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([_weekend_example()]), encoding="utf-8"
    )
    engine = _engine()
    monkeypatch.setattr(engine, "OUTPUT_DIR", tmp_path)
    _as_of(monkeypatch, engine, datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc))
    published = engine.load_custom_articles()
    assert any(x.get("custom_id") == CURRENT_ID for x in published)


def test_november_6_8_roundup_is_only_active_custom_story_and_uses_requested_image():
    """The editorial queue must contain only this new custom assignment."""
    entries = _items()
    assert len(entries) == 1
    guide = entries[0]
    assert guide["custom_id"] == "treasure-coast-top-five-weekend-2026-11-06-08"
    assert guide["category"] == "things_to_do"
    assert guide["publish_on"] == "2026-11-05"
    assert guide["expires"] == "2026-11-09"
    assert guide["image_url"] == "https://treasurecoast.today/images/first-friday-walk.webp"
    assert guide["sponsored"] is False
    assert guide["force_hero"] is False
    assert guide["body"].count("\\n## ") == 5
    assert guide["headline"].endswith("Nov. 6-8")
    for title in (
        "First Friday Art Walk",
        "41st Annual Navy SEAL Museum Muster",
        "Treasure Coast Caribbean Food & Music Festival",
        "St. Johns Wood",
        "Shopapalooza Fall Sidewalk Sale",
    ):
        assert title in guide["body"]


def test_november_roundup_matches_current_events_calendar():
    """Protect against publishing roundup items absent from the event data."""
    events = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))["events"]
    guide = _items()[0]
    source_titles = (
        ("First Friday Art Walk", "2026-11-06"),
        ("41st Annual Navy SEAL Museum Muster", "2026-11-07"),
        ("Treasure Coast Caribbean Food & Music Festival", "2026-11-07"),
        ("St. Johns Wood", "2026-11-07"),
        ("Shopapalooza Fall Sidewalk Sale", "2026-11-08"),
    )
    for title, day in source_titles:
        matches = [x for x in events if x.get("title") == title and str(x.get("starts_at", "")).startswith(day)]
        assert matches, f"Weekend guide event not in calendar: {title} ({day})"
        assert matches[0]["event_url"] in guide["body"]


def test_november_guide_expires_after_sunday_in_eastern_time(monkeypatch, tmp_path):
    """An 8 p.m. Eastern reader on Nov. 8 should still see the guide."""
    (tmp_path / "custom_articles.json").write_text(json.dumps(_items()), encoding="utf-8")
    engine = _engine()
    monkeypatch.setattr(engine, "OUTPUT_DIR", tmp_path)
    _as_of(monkeypatch, engine, datetime(2026, 11, 9, 1, 0, tzinfo=timezone.utc))
    assert any(
        story.get("custom_id") == "treasure-coast-top-five-weekend-2026-11-06-08"
        for story in engine.load_custom_articles()
    )
    _as_of(monkeypatch, engine, datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc))
    assert not any(
        story.get("custom_id") == "treasure-coast-top-five-weekend-2026-11-06-08"
        for story in engine.load_custom_articles()
    )
