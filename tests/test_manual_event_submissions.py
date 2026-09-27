from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts import update_events as events


def _window():
    os.environ["TCT_EVENTS_NOW"] = "2026-09-27T01:00:00-04:00"
    return events._window(180)


def test_manual_submitted_event_is_normalized_and_kept(tmp_path: Path):
    path = tmp_path / "events-manual.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "events": [{
            "title": "FREE CONCERT: Beach Jam (2nd Annual Pick, Paddle & Play Beach Jam)",
            "starts_at": "2026-11-14T10:00:00-05:00",
            "ends_at": "2026-11-14T20:00:00-05:00",
            "venue": "Causeway Cove Marina",
            "address": "601 Seaway Drive, Fort Pierce, FL 34949",
            "city": "Fort Pierce",
            "county": "St. Lucie",
            "category": "Community",
            "price": "Free",
            "event_url": "https://stabilizerevitalizefortpierce.org/beach-jam",
            "ticket_url": "https://www.eventbrite.com/e/beach-jam",
            "organizer_name": "Stabilize Revitalize Fort Pierce, Inc.",
            "source_name": "Stabilize Revitalize Fort Pierce, Inc.",
            "source_url": "https://stabilizerevitalizefortpierce.org/beach-jam"
        }]
    }), encoding="utf-8")

    loaded = events._manual_submitted_events(path, _window())
    assert len(loaded) == 1
    event = loaded[0]
    assert event["county"] == "St. Lucie"
    assert event["starts_at"] == "2026-11-14T10:00-05:00"
    assert event["ends_at"] == "2026-11-14T20:00-05:00"
    assert event["source_kind"] == "organizer"
    assert event["source_priority"] == 3
    assert event["organizer_name"] == "Stabilize Revitalize Fort Pierce, Inc."


def test_manual_submitted_event_still_obeys_treasure_coast_boundary(tmp_path: Path):
    path = tmp_path / "events-manual.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "events": [{
            "title": "Palm Beach Event",
            "starts_at": "2026-11-14T10:00:00-05:00",
            "city": "West Palm Beach",
            "county": "Palm Beach",
            "event_url": "https://example.com/event",
            "source_name": "Example Organizer",
            "source_url": "https://example.com/event"
        }]
    }), encoding="utf-8")
    assert events._manual_submitted_events(path, _window()) == []


def test_manual_direct_organizer_submission_wins_duplicate_source():
    window = _window()
    manual_source = {
        "id": "submitted-organizer",
        "name": "Organizer",
        "url": "https://organizer.example/event",
        "county": "St. Lucie",
        "city": "Fort Pierce",
        "kind": "organizer",
        "priority": 3,
    }
    tourism_source = {
        "id": "tourism",
        "name": "Tourism Calendar",
        "url": "https://tourism.example/event",
        "county": "St. Lucie",
        "city": "Fort Pierce",
        "kind": "tourism",
        "priority": 35,
    }
    manual = events._normalize_event({
        "title": "Beach Jam",
        "starts_at": "2026-11-14T10:00:00-05:00",
        "venue": "Causeway Cove Marina",
        "description": "Organizer-supplied description",
        "event_url": "https://organizer.example/event",
    }, manual_source, window)
    tourism = events._normalize_event({
        "title": "Beach Jam",
        "starts_at": "2026-11-14T10:00:00-05:00",
        "venue": "Causeway Cove Marina",
        "event_url": "https://tourism.example/event",
    }, tourism_source, window)
    merged = events._dedupe_cross_source([tourism, manual])
    assert len(merged) == 1
    assert merged[0]["source_name"] == "Organizer"
    assert merged[0]["event_url"] == "https://organizer.example/event"


def test_repository_manual_events_file_contains_beach_jam():
    root = Path(__file__).resolve().parents[1]
    loaded = events._manual_submitted_events(root / "data" / "events-manual.json", _window())
    matches = [event for event in loaded if "Beach Jam" in event["title"]]
    assert len(matches) == 1
    assert matches[0]["venue"] == "Causeway Cove Marina"
    assert matches[0]["price"] == "Free"


def test_manual_events_file_schema_must_be_valid(tmp_path: Path):
    path = tmp_path / "events-manual.json"
    path.write_text('{"schema_version": 999, "events": []}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="events-manual.json is invalid"):
        events._manual_submitted_events(path, _window())
