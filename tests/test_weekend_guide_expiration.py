"""Current weekend-guide expiration and historical-queue safety contracts."""
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
OLD_ID = "treasure-coast-top-five-weekend-2026-10-10-11"


def _items():
    return json.loads(QUEUE.read_text(encoding="utf-8"))


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
    rows = _items()
    assert [x.get("custom_id") for x in rows if "weekend" in str(x.get("custom_id", "")).lower()] == [CURRENT_ID]
    (tmp_path / "custom_articles.json").write_text(json.dumps(rows), encoding="utf-8")
    engine = _engine()
    monkeypatch.setattr(engine, "OUTPUT_DIR", tmp_path)
    _as_of(monkeypatch, engine, datetime(2026, 10, 27, 12, tzinfo=timezone.utc))
    assert not any(x.get("custom_id") == CURRENT_ID for x in engine.load_custom_articles())


def test_weekend_event_guides_in_current_editor_queue_have_expiration():
    rows = _items()
    assert len([row for row in rows if "weekend" in str(row.get("custom_id", "")).lower()]) == 1
    for row in rows:
        if "weekend" not in str(row.get("custom_id", "")).lower():
            continue
        expiry = row.get("expires")
        assert isinstance(expiry, str) and expiry, (
            f"Date-specific weekend guide requires expires: {row['headline']}"
        )
        expires_on = datetime.strptime(expiry, "%Y-%m-%d").date()
        assert expires_on == datetime(2026, 10, 26).date()
        assert expires_on > datetime(2026, 10, 25).date()


def test_current_weekend_guide_is_available_through_sunday_evening(monkeypatch, tmp_path):
    """Oct 25 evening hike should not be discarded by a UTC-midnight cutoff."""
    rows = _items()
    (tmp_path / "custom_articles.json").write_text(json.dumps(rows), encoding="utf-8")
    engine = _engine()
    monkeypatch.setattr(engine, "OUTPUT_DIR", tmp_path)
    _as_of(monkeypatch, engine, datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc))
    published = engine.load_custom_articles()
    assert any(x.get("custom_id") == CURRENT_ID for x in published)
