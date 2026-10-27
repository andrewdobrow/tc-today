"""Regression tests for invalid publisher clock evidence in events refresh."""
from copy import deepcopy

from scripts import update_events as events


def test_invalid_12_hour_clocks_are_rejected_without_inventing_a_time():
    for value in ("13 p.m.", "14:00 p.m.", "0 a.m.", "12:60 p.m.", "9:99 a.m."):
        assert events._parse_clock(value) is None, value
    assert events._parse_clock("24:00") is None
    assert events._parse_clock("13:00") == (13, 0)
    assert events._parse_clock("12 a.m.") == (0, 0)
    assert events._parse_clock("12 p.m.") == (12, 0)
    assert events._parse_clock("1:30 p.m.") == (13, 30)


def test_impossible_publisher_time_range_cannot_crash_deduplication():
    # The former code converted 13 p.m. to hour=25, then datetime.replace
    # raised ValueError, aborting the entire scheduled event refresh.
    event = {
        "title": "Event with malformed clock text",
        "description": "Doors open 13 p.m. - 5 p.m.",
        "starts_at": "2026-10-30T09:00-04:00",
        "ends_at": "2026-10-30T11:00-04:00",
        "all_day": False,
        "time_known": True,
        "source_priority": 1,
        "venue": "Community Center",
        "city": "Stuart",
    }
    original = deepcopy(event)
    assert events._clock_range_from_text(event["description"]) is None
    deduped = events._dedupe_cross_source([event])
    assert len(deduped) == 1
    for key in ("starts_at", "ends_at", "time_known"):
        assert deduped[0][key] == original[key]


def test_out_of_range_cached_time_evidence_does_not_overwrite_event():
    event = {
        "starts_at": "2026-10-30T09:00-04:00",
        "ends_at": "2026-10-30T11:00-04:00",
        "time_known": True,
    }
    original = deepcopy(event)
    events._apply_time_evidence(event, ((25, 0), (17, 0)), source="description")
    assert event == original
    events._apply_time_evidence(event, ((13, 75), (17, 0)), source="description")
    assert event == original


def test_ordinary_clock_conflict_correction_remains_supported():
    event = {
        "starts_at": "2026-10-30T13:00-04:00",
        "ends_at": "2026-10-30T16:00-04:00",
        "description": "The concert runs 9 a.m. - 12 p.m.",
        "time_known": True,
        "all_day": False,
    }
    events._repair_explicit_clock_conflict(event)
    assert event["starts_at"].startswith("2026-10-30T09:00")
    assert event["ends_at"].startswith("2026-10-30T12:00")
