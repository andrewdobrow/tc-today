"""Regression coverage for time-bound custom weekend-event editions.

An existing published guide stays in the archive but must leave the active
homepage/category selection pool once its event dates are past. The pipeline's
load_custom_articles() already honors the optional `expires` field.
"""
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = "2026-10-09-treasure-coast-weekend-events-oct-10-11"


def _queue():
    return json.loads((ROOT / "custom_articles.json").read_text(encoding="utf-8"))


def test_october_tenth_weekend_guide_expires_after_events():
    matches = [r for r in _queue() if r.get("slug") == TARGET]
    assert len(matches) == 1
    row = matches[0]
    assert row["expires"] == "2026-10-11"
    assert row["publish_on"] == "2026-10-09"
    assert row.get("retired") is not True


def test_stale_weekend_guide_cannot_stay_in_active_queue():
    row = next(r for r in _queue() if r.get("slug") == TARGET)
    # Mirrors the existing load_custom_articles expiration check, which does
    # not modify/retire the existing archived article or its canonical URL.
    expires = datetime.strptime(row["expires"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    assert datetime(2026, 10, 18, tzinfo=timezone.utc) > expires + timedelta(days=1)


def test_weekend_event_guides_in_current_editor_queue_have_expiration():
    # Editorial guard: future date-specific Top 5 weekend editions must include
    # an expiration. Persistent news features are deliberately not covered.
    for row in _queue():
        title = str(row.get("headline") or "")
        if not ("weekend" in title.lower() and re.search(r"\b(?:top\s*5|events?)\b", title, re.I)):
            continue
        expiry = row.get("expires")
        assert expiry, f"Date-specific weekend guide requires expires: {title}"
        assert date.fromisoformat(str(expiry)) >= date.fromisoformat(row["publish_on"])
