from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import update_events as events

TZ = ZoneInfo("America/New_York")


def _event(title, starts_at, ends_at=None, *, all_day=False, time_known=True):
    return {
        "id": title.lower().replace(" ", "-"),
        "title": title,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "all_day": all_day,
        "time_known": time_known,
        "county": "Martin",
        "category": "Community",
        "source_name": "Fixture",
        "source_url": "https://example.com/events",
        "event_url": "https://example.com/event",
    }


def test_display_drops_elapsed_rows_and_keeps_today_first_ahead_of_old_start_ongoing():
    now = datetime(2026, 10, 4, 15, 27, tzinfo=TZ)
    rows = [
        _event("Old finished event", "2026-10-03T09:00-04:00", "2026-10-03T10:00-04:00"),
        _event("Ongoing marathon", "2026-10-02T00:00-04:00", "2026-10-06T00:00-04:00", all_day=True),
        _event("Today later", "2026-10-04T17:00-04:00", "2026-10-04T19:00-04:00"),
        _event("Tomorrow", "2026-10-05T09:00-04:00", "2026-10-05T11:00-04:00"),
    ]
    shown = events._events_for_display(rows, now=now)
    assert [row["title"] for row in shown] == ["Today later", "Ongoing marathon", "Tomorrow"]


def test_render_dynamic_never_leads_with_prior_date_when_today_has_live_event(monkeypatch):
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-04T15:27:00-04:00")
    rows = [
        _event("Ongoing marathon", "2026-10-02T00:00-04:00", "2026-10-06T00:00-04:00", all_day=True),
        _event("Today event", "2026-10-04T17:00-04:00", "2026-10-04T19:00-04:00"),
    ]
    html = events._render_dynamic(rows, {"generated_at": "2026-10-04T15:00:00-04:00"})
    assert html.index("Today event") < html.index("Ongoing marathon")


def test_events_page_reconciles_snapshot_immediately_and_filters_live_rows():
    page = events.EVENTS_HTML_PATH.read_text(encoding="utf-8")
    assert "const eventIsLive = (event, today, nowMs) =>" in page
    assert "const displayBucket = (event, today) =>" in page
    assert "return eventIsLive(event, today, nowMs) && rangeOk" in page
    # The page must refresh on load, not wait for a filter click or View more.
    assert page.count("refreshFromInteraction();") >= 2
