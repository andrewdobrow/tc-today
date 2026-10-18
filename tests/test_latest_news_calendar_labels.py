"""Regression checks for Eastern-calendar-day Latest News timestamps.

The source function is loaded by AST to keep these clock tests deterministic
and independent of external news/LLM API dependencies.
"""

import ast
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SOURCE = Path(__file__).parents[1] / "scripts" / "generate.py"
EASTERN = ZoneInfo("America/New_York")


def _formatter_at(eastern_now: datetime):
    assert eastern_now.tzinfo is not None
    parsed = ast.parse(SOURCE.read_text(encoding="utf-8"))
    func = next(
        node for node in parsed.body
        if isinstance(node, ast.FunctionDef) and node.name == "format_age"
    )

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            utc_now = eastern_now.astimezone(timezone.utc)
            return utc_now.astimezone(tz) if tz is not None else utc_now.replace(tzinfo=None)

    scope = {
        "datetime": FixedDatetime,
        "timezone": timezone,
        "timedelta": timedelta,
        "ZoneInfo": ZoneInfo,
    }
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(SOURCE), "exec"), scope)
    return scope["format_age"]


def _rss_date(year, month, day, hour, minute, tz=EASTERN):
    return format_datetime(datetime(year, month, day, hour, minute, tzinfo=tz))


def test_october_16_stories_are_not_yesterday_on_october_18():
    display = _formatter_at(datetime(2026, 10, 18, 15, 53, tzinfo=EASTERN))
    assert display(_rss_date(2026, 10, 16, 18, 51)) == "Oct 16, 6:51 PM ET"
    assert display(_rss_date(2026, 10, 16, 21, 53)) == "Oct 16, 9:53 PM ET"


def test_previous_calendar_day_is_yesterday():
    display = _formatter_at(datetime(2026, 10, 18, 15, 53, tzinfo=EASTERN))
    assert display(_rss_date(2026, 10, 17, 16, 51)) == "Yesterday, 4:51 PM ET"


def test_today_shows_time_without_yesterday():
    display = _formatter_at(datetime(2026, 10, 18, 15, 53, tzinfo=EASTERN))
    assert display(_rss_date(2026, 10, 18, 10, 21)) == "10:21 AM ET"


def test_same_day_under_one_hour_is_recent():
    display = _formatter_at(datetime(2026, 10, 18, 15, 53, tzinfo=EASTERN))
    assert display(_rss_date(2026, 10, 18, 15, 40)) == "A few minutes ago"


def test_previous_day_just_after_midnight_does_not_say_a_few_minutes_ago():
    display = _formatter_at(datetime(2026, 10, 18, 0, 15, tzinfo=EASTERN))
    assert display(_rss_date(2026, 10, 17, 23, 50)) == "Yesterday, 11:50 PM ET"


def test_dst_transition_uses_eastern_calendar_days():
    display = _formatter_at(datetime(2026, 11, 2, 12, 0, tzinfo=EASTERN))
    assert display(_rss_date(2026, 11, 1, 1, 30)) == "Yesterday, 1:30 AM ET"
    assert display(_rss_date(2026, 10, 31, 21, 30)) == "Oct 31, 9:30 PM ET"


def test_year_boundary_yesterday_is_previous_calendar_day():
    display = _formatter_at(datetime(2027, 1, 1, 0, 15, tzinfo=EASTERN))
    assert display(_rss_date(2026, 12, 31, 23, 50)) == "Yesterday, 11:50 PM ET"


def test_latest_news_renderer_uses_timestamp_formatter_for_both_publications_and_updates():
    source = SOURCE.read_text(encoding="utf-8")
    assert "_ltime = _latest_news_display_timestamp(_latest, archive_for_links)" in source
    assert 'label = format_age(format_datetime(updated_at))' in source
    assert "return _format_category_hero_timestamp(entry, archive_entries)" in source
