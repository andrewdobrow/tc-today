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
        "venue": "Memorial Park",
        "city": "Stuart",
    }


def test_ongoing_multiday_card_rolls_forward_to_current_date():
    event = _event(
        "Ongoing marathon",
        "2026-10-02T00:00-04:00",
        "2026-10-06T00:00-04:00",
        all_day=True,
    )
    oct4 = datetime(2026, 10, 4, 15, 27, tzinfo=TZ)
    oct5 = datetime(2026, 10, 5, 9, 0, tzinfo=TZ)

    html4 = events._render_card(event, now=oct4)
    html5 = events._render_card(event, now=oct5)

    assert 'data-date="2026-10-04"' in html4
    assert '<span>ONGOING</span><strong>OCT 4</strong>' in html4
    assert '<strong>All day</strong> · Started Oct 2 · Memorial Park · Stuart' in html4

    assert 'data-date="2026-10-05"' in html5
    assert '<span>ONGOING</span><strong>OCT 5</strong>' in html5
    assert 'Started Oct 2' in html5


def test_first_day_and_future_event_keep_true_calendar_date():
    event = _event(
        "Opening day",
        "2026-10-04T17:00-04:00",
        "2026-10-06T20:00-04:00",
    )
    now = datetime(2026, 10, 4, 15, 27, tzinfo=TZ)
    html = events._render_card(event, now=now)

    assert 'data-date="2026-10-04"' in html
    assert '<span>SUN</span><strong>OCT 4</strong>' in html
    assert 'ONGOING' not in html
    assert 'Started Oct 4' not in html


def test_events_page_has_client_side_daily_rollover_contract():
    page = events.EVENTS_HTML_PATH.read_text(encoding="utf-8")
    assert "const eventDisplayState = (event, today, nowMs) =>" in page
    assert "const kicker = display.ongoing ? 'ONGOING' : date.weekday;" in page
    assert "dateIso: ongoing ? today : startDate" in page
    assert "Started ${startMonth} ${startDate.day}" in page
