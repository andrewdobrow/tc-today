from scripts import update_events as e


def row(title, venue, city="Palm City", time="12:00"):
    return {"title": title, "venue": venue, "city": city, "starts_at": f"2026-10-10T{time}:00-04:00", "ends_at": None, "source_priority": 35, "source_name": "Discover Martin", "time_known": True, "all_day": False, "description": "", "event_url": "https://discovermartin.com/event/example/", "address": "", "category": "Live Music"}


def test_newfield_festival_annual_and_short_title_are_one_event():
    events = [row("1st Annual Newfield Harvest Festival", "Newfield Fields"), row("Harvest Festival", "Newfield")]
    merged = e._dedupe_cross_source(events)
    assert len(merged) == 1
    assert merged[0]["city"] == "Palm City"


def test_simultaneous_other_venue_festival_not_merged():
    events = [row("1st Annual Newfield Harvest Festival", "Newfield Fields"), row("Harvest Festival", "Other Venue")]
    assert len(e._dedupe_cross_source(events)) == 2


def test_separate_festival_sessions_not_merged():
    events = [row("1st Annual Newfield Harvest Festival", "Newfield Fields"), row("Harvest Festival", "Newfield", time="17:00")]
    assert len(e._dedupe_cross_source(events)) == 2


def test_generic_same_city_festivals_not_merged():
    events = [row("Harbor Harvest Festival", "Harbor Park"), row("Harvest Festival", "Newfield")]
    assert len(e._dedupe_cross_source(events)) == 2
