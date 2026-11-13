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


NOV_WEEKEND_ARTICLE = ROOT / "articles" / "2026-11-12-treasure-coast-weekend-events-nov-13-15.html"


def test_november_13_15_roundup_remains_published_after_queue_turnover():
    """Historical published guides stay readable when a new custom story is queued."""
    page = NOV_WEEKEND_ARTICLE.read_text(encoding="utf-8")
    assert "Nov. 13–15" in page
    assert "article-hero-image" in page
    assert "Stuart Air Show" in page
    for title in (
        "Stuart Air Show",
        "Mr Motwn",
        "PalmCon",
        "Pick, Paddle & Play Beach Jam",
        "Hispanic Heritage Festival",
    ):
        assert title in page
    assert page.count('<h2 class="article-section">') >= 5


def test_current_custom_queue_contains_only_new_traffic_article_and_fdot_image():
    """The one-item queue holds the newly requested story, never an old guide."""
    entries = _items()
    assert len(entries) == 1
    article = entries[0]
    assert article["custom_id"] == "treasure-coast-traffic-report-2026-11-13-20"
    assert article["slug"].endswith("nov-13-20")
    assert article["custom_series_key"] == "treasure-coast-traffic-report"
    assert article["custom_edition_key"] == "nov-13-20"
    assert article["image_url"] == "https://treasurecoast.today/images/florida-traffic.png"
    assert article["category"] == "local_gov"
    assert article["publish_on"] == "2026-11-13"
    assert article["expires"] == "2026-11-21"
    assert "Martin County" in article["body"]
    assert "St. Lucie County" in article["body"]
    assert "Indian River County" in article["body"]
    assert article["sponsored"] is False


def test_november_13_15_roundup_matches_live_events_calendar():
    """Editorial source links are intact and upcoming source events are present.

    Rolling event feeds can correctly prune concluded listings after their day.
    The weekend guide is checked against the available calendar while it is live.
    """
    events = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))["events"]
    guide = NOV_WEEKEND_ARTICLE.read_text(encoding="utf-8")
    now = datetime.now(ZoneInfo("America/New_York"))
    # (event title fragment, calendar listing date, confirmed end time, organizer link)
    # The Stuart Air Show calendar lists Nov. 14–15; Friday is its kickoff party.
    source_events = (
        ("Stuart Air Show", "2026-11-14", "2026-11-15T17:00:00-05:00",
         "https://www.stuartairshow.com/"),
        ("Mr Motwn", "2026-11-13", "2026-11-13T20:30:00-05:00",
         "https://www.riversidetheatre.com/loop-music-calendar"),
        ("PalmCon", "2026-11-14", "2026-11-15T17:00:00-05:00",
         "https://palmcon.net/treasure-coast"),
        ("Pick, Paddle & Play Beach Jam", "2026-11-14", "2026-11-14T20:00:00-05:00",
         "https://www.stabilizerevitalizefortpierce.org/pick-paddle-and-play-beach-jam"),
        ("Hispanic Heritage Festival", "2026-11-15", "2026-11-15T20:00:00-05:00",
         "https://www.stuartfl.gov/m/calendar/event/detail/6883"),
    )
    for title, day, end_iso, organizer_url in source_events:
        assert organizer_url in guide, f"Archived weekend guide lost its organizer link: {organizer_url}"
        matches = [
            event for event in events
            if title.lower() in str(event.get("title") or "").lower()
            and str(event.get("starts_at") or "").startswith(day)
        ]
        if now < datetime.fromisoformat(end_iso):
            assert matches, f"Upcoming weekend event missing from calendar: {title} ({day})"


def test_november_13_15_guide_expires_after_sunday_in_eastern_time(monkeypatch, tmp_path):
    """An 8 p.m. Eastern reader on Nov. 15 can still see the current guide."""
    # Recreate the dated guide in an isolated test queue; production now queues
    # a different custom article, while the published guide remains archived.
    old_guide = {
        "custom_id": "treasure-coast-top-five-weekend-2026-11-13-15",
        "headline": "Looking for something to do this weekend? Here are the Top 5 local events for Nov. 13–15",
        "teaser": "Weekend events across the Treasure Coast.",
        "body": "Stuart Air Show, PalmCon and more local weekend events.",
        "category": "things_to_do",
        "publish_on": "2026-11-11",
        "expires": "2026-11-16",
    }
    (tmp_path / "custom_articles.json").write_text(json.dumps([old_guide]), encoding="utf-8")
    engine = _engine()
    monkeypatch.setattr(engine, "OUTPUT_DIR", tmp_path)
    _as_of(monkeypatch, engine, datetime(2026, 11, 16, 1, 0, tzinfo=timezone.utc))
    assert any(
        story.get("custom_id") == "treasure-coast-top-five-weekend-2026-11-13-15"
        for story in engine.load_custom_articles()
    )
    _as_of(monkeypatch, engine, datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc))
    assert not any(
        story.get("custom_id") == "treasure-coast-top-five-weekend-2026-11-13-15"
        for story in engine.load_custom_articles()
    )
