from __future__ import annotations

import json
import os
from pathlib import Path


from scripts import update_events as events

ROOT = Path(__file__).resolve().parents[1]


def _window(days: int = 120):
    os.environ["TCT_EVENTS_NOW"] = "2026-09-04T12:00:00-04:00"
    return events._window(days)


def _source(**overrides):
    base = {
        "id": "fixture-source",
        "name": "Fixture Source",
        "url": "https://example.com/events",
        "adapter": "dated_headings",
        "county": "Martin",
        "city": "Stuart",
        "kind": "venue",
        "priority": 10,
    }
    base.update(overrides)
    return base


def test_source_registry_has_broad_official_and_local_venue_coverage():
    payload = json.loads((ROOT / "data" / "events-sources.json").read_text(encoding="utf-8"))
    sources = payload["sources"]
    ids = {source["id"] for source in sources}
    assert len(sources) >= 37
    assert {
        "stuart-city-events",
        "fort-pierce-community-calendar",
        "sebastian-events",
        "discover-martin",
        "visit-st-lucie",
        "visit-indian-river",
        "terra-fermata",
        "lyric-theatre",
        "summer-crush",
        "midflorida-event-center",
        "sunrise-theatre",
        "capt-hirams",
        "riverside-loop-music",
        "environmental-learning-center",
        "childrens-museum-treasure-coast",
        "tradition-events",
        "heathcote-botanical-gardens",
        "fort-pierce-jazz-blues",
        "vero-beach-theatre-guild",
        "manatee-center",
        "elliott-museum-events",
        "pineapple-playhouse",
        "musicworks-concerts",
        "vero-beach-opera",
        "hobe-sound-farms",
    }.issubset(ids)
    assert all(source["url"].startswith("https://") for source in sources)
    assert not any("facebook.com" in source["url"] or "instagram.com" in source["url"] for source in sources)


def test_events_engine_is_deterministic_and_has_no_llm_dependency():
    text = (ROOT / "scripts" / "update_events.py").read_text(encoding="utf-8").lower()
    assert "import anthropic" not in text
    assert "client.messages" not in text
    assert "claude" not in text


def test_ical_adapter_accepts_public_event_and_rejects_routine_government_meeting():
    source = _source(kind="government", adapter="ical")
    ical = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260906T130000
DTEND:20260906T160000
SUMMARY:Rock'n Riverwalk
LOCATION:Riverwalk Stage
URL:https://example.com/riverwalk
END:VEVENT
BEGIN:VEVENT
DTSTART:20260907T173000
SUMMARY:Regular City Commission Meeting
LOCATION:City Hall
END:VEVENT
END:VCALENDAR
"""
    parsed = events._parse_ical(ical, source, _window())
    assert [event["title"] for event in parsed] == ["Rock'n Riverwalk"]
    assert parsed[0]["starts_at"].startswith("2026-09-06T13:00")


def test_terra_fermata_adapter_captures_show_and_not_duplicate_card_copy():
    source = _source(
        id="terra-fermata", name="Terra Fermata", adapter="terra_fermata",
        venue="Terra Fermata", category="Live Music", priority=5,
    )
    html = """
    <h3>RAELYN NELSON @ Terra Fermata</h3>
    <div>Friday</div><div>Sep</div><div>04</div><div>7:00pm</div>
    <div>Advance tickets $17.85 total cost.</div>
    <a href="/event/raelyn">MORE DETAILS</a><a href="https://tickets.example/raelyn">BUY TICKETS</a>
    <h3>RAELYN NELSON</h3><div>Sep 04 Fri | 7:00pm</div>
    """
    parsed = events._terra_events(html, source, _window())
    assert len(parsed) == 1
    assert parsed[0]["title"] == "RAELYN NELSON"
    assert parsed[0]["category"] == "Live Music"
    assert parsed[0]["starts_at"].startswith("2026-09-04T19:00")


def test_martinarts_adapter_uses_explicit_day_heading_for_each_performance():
    source = _source(id="martinarts", name="MartinArts", adapter="martinarts_calendar", category="Arts & Culture")
    html = """
    <h3>Friday, September 4, 2026</h3>
    <ul><li>A.C.T Studio Theatre presents &quot;Fools&quot; 7:30 pm - 9:00 pm</li></ul>
    <h3>Saturday, September 5, 2026</h3>
    <ul><li>Sunset Concerts at the Gallery 5:30 pm - 6:30 pm</li></ul>
    """
    parsed = events._martinarts_events(html, source, _window())
    assert [(event["title"], event["starts_at"][:16]) for event in parsed] == [
        ('A.C.T Studio Theatre presents "Fools"', "2026-09-04T19:30"),
        ("Sunset Concerts at the Gallery", "2026-09-05T17:30"),
    ]


def test_st_lucie_county_compact_calendar_rejects_private_and_board_rows():
    source = _source(id="st-lucie-county", county="St. Lucie", city="", kind="government", adapter="stlucie_county_calendar")
    html = """
    <div>Sep 05 A Life in the Wild Hike at Oxbow Eco-Center &amp; Preserve 09:00 AM - 11:00 AM</div>
    <div>Sep 05 Private Event 06:00 PM - 09:00 PM</div>
    <div>Sep 08 Board of County Commissioners Meeting 06:00 PM - 08:00 PM</div>
    """
    parsed = events._stlucie_county_events(html, source, _window())
    assert [event["title"] for event in parsed] == ["A Life in the Wild Hike at Oxbow Eco-Center & Preserve"]


def test_jazz_calendar_adapter_reads_explicit_date_rows():
    source = _source(id="jazz", name="Fort Pierce Jazz & Blues Society", county="St. Lucie", city="Fort Pierce", adapter="jazz_calendar", category="Live Music")
    html = """
    <h4>GARDENS JAM</h4><p>Date: Wed, Sep 9, 2026, 6:30 PM to 9:00 PM</p>
    <h4>FORT PIERCE - Yacht Club</h4><p>Date: Tue, Sep 15, 2026, 6:30 PM to 9:00 PM</p>
    """
    parsed = events._jazz_calendar_events(html, source, _window())
    assert [event["title"] for event in parsed] == ["GARDENS JAM", "FORT PIERCE - Yacht Club"]
    assert all(event["category"] == "Live Music" for event in parsed)


def test_hard_rejects_keep_private_canceled_and_closed_rows_off_calendar():
    source = _source()
    window = _window()
    for title in ("Private Event", "Concert CANCELED", "Garage Sale", "CLOSED"):
        raw = {"title": title, "starts_at": "2026-09-10T18:00:00-04:00"}
        assert events._normalize_event(raw, source, window) is None


def test_cross_source_dedupe_prefers_official_venue_and_fills_missing_details():
    venue = _source(id="venue", name="Official Venue", priority=5, venue="Terra Fermata", category="Live Music")
    tourism = _source(id="tourism", name="Tourism Calendar", priority=35, kind="tourism", venue="Terra Fermata", category="Live Music")
    window = _window()
    official = events._normalize_event({"title":"Raelyn Nelson", "starts_at":"2026-09-04T19:00:00-04:00", "event_url":"https://venue.example/show"}, venue, window)
    duplicate = events._normalize_event({"title":"Raelyn Nelson", "starts_at":"2026-09-04T19:00:00-04:00", "description":"Tourism description", "event_url":"https://tourism.example/show"}, tourism, window)
    merged = events._dedupe_cross_source([duplicate, official])
    assert len(merged) == 1
    assert merged[0]["source_name"] == "Official Venue"
    assert merged[0]["event_url"] == "https://venue.example/show"
    assert merged[0]["description"] == "Tourism description"
    assert merged[0]["also_listed_by"] == ["Tourism Calendar"]


def test_cache_write_is_content_stable_when_source_events_do_not_change():
    source = _source()
    cache = {"schema_version": 1, "sources": {}}
    sample = events._normalize_event({"title":"Local Festival", "starts_at":"2026-09-12T12:00:00-04:00"}, source, _window())
    events._cache_write_source(cache, source, [sample], "2026-09-04T12:00:00-04:00")
    first = json.loads(json.dumps(cache))
    events._cache_write_source(cache, source, [sample], "2026-09-04T15:00:00-04:00")
    assert cache == first
    assert cache["sources"][source["id"]]["fetched_at"] == "2026-09-04T12:00:00-04:00"


def test_existing_events_page_is_live_filterable_and_not_coming_soon():
    page = (ROOT / "events.html").read_text(encoding="utf-8")
    assert "Coming Soon" not in page
    assert "data-events-search" in page
    assert 'data-range="today"' in page
    assert 'data-range="weekend"' in page
    assert 'data-county-filter="Martin"' in page
    assert 'data-category-filter="Live Music"' in page
    assert page.count(events.DYNAMIC_START) == 1
    assert page.count(events.DYNAMIC_END) == 1
    assert page.count(events.JSONLD_START) == 1
    assert page.count(events.JSONLD_END) == 1
    assert '<a href="/feed.xml" type="application/rss+xml">RSS Feed</a>' in page


def test_launch_artifacts_validate_without_network():
    events.validate_outputs()
    payload = json.loads((ROOT / "data" / "events.json").read_text(encoding="utf-8"))
    assert payload["events"]
    assert all("Private Event" not in event["title"] for event in payload["events"])


def test_events_workflow_is_independent_scheduled_and_serialized_with_pages_deploy():
    path = ROOT / ".github" / "workflows" / "update-events.yml"
    text = path.read_text(encoding="utf-8")
    assert "cron: '17 10,22 * * *'" in text
    assert 'group: "pages"' in text
    assert "python -u scripts/update_events.py" in text
    assert "python scripts/update_events.py --validate-only" in text
    assert "beautifulsoup4" in text
    assert "git add events.html data/events.json data/events-source-cache.json data/events-source-status.json" in text
    assert "anthropic" not in text.lower()


def test_generate_news_refreshes_events_without_allowing_event_source_failure_to_fail_news():
    text = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
    marker = "- name: Refresh Treasure Coast events"
    assert marker in text
    block = text[text.index(marker): text.index(marker) + 220]
    assert "continue-on-error: true" in block
    assert "python -u scripts/update_events.py" in block
    assert "beautifulsoup4" in text


def test_editorial_ci_runs_when_events_engine_or_artifacts_change():
    text = (ROOT / ".github" / "workflows" / "test-editorial-engine.yml").read_text(encoding="utf-8")
    assert '"events.html"' in text
    assert '"data/events*.json"' in text
    assert '".github/workflows/update-events.yml"' in text
    assert "beautifulsoup4" in text


def test_same_title_same_venue_two_performances_same_day_keep_distinct_ids_and_rows():
    source = _source(id="theatre", name="Official Theatre", venue="Pineapple Playhouse", priority=5)
    window = _window()
    matinee = events._normalize_event({"title":"Proof", "starts_at":"2026-09-12T14:00:00-04:00"}, source, window)
    evening = events._normalize_event({"title":"Proof", "starts_at":"2026-09-12T19:00:00-04:00"}, source, window)
    assert matinee and evening
    assert matinee["id"] != evening["id"]
    merged = events._dedupe_cross_source([matinee, evening])
    assert [(row["starts_at"][:16], row["title"]) for row in merged] == [
        ("2026-09-12T14:00", "Proof"),
        ("2026-09-12T19:00", "Proof"),
    ]


def test_cross_source_dedupe_still_merges_same_performance_with_nearby_time():
    official_source = _source(id="official", name="Official Theatre", venue="Pineapple Playhouse", priority=5)
    tourism_source = _source(id="tourism", name="Tourism Calendar", venue="Pineapple Playhouse", priority=35)
    window = _window()
    official = events._normalize_event({"title":"Proof", "starts_at":"2026-09-12T19:00:00-04:00"}, official_source, window)
    tourism = events._normalize_event({"title":"Proof", "starts_at":"2026-09-12T19:15:00-04:00", "description":"Tourism listing"}, tourism_source, window)
    merged = events._dedupe_cross_source([tourism, official])
    assert len(merged) == 1
    assert merged[0]["source_name"] == "Official Theatre"
    assert merged[0]["description"] == "Tourism listing"


def test_pineapple_show_page_parser_keeps_every_official_performance_including_two_on_same_day():
    source = _source(
        id="pineapple-playhouse", name="Pineapple Playhouse", county="St. Lucie", city="Fort Pierce",
        venue="Pineapple Playhouse", adapter="pineapple_linked_shows", category="Arts & Culture", priority=5,
    )
    html = """
    <main><h1>Proof</h1><h2>Dates</h2>
      <p>Friday, September 4, 2026 7:00 PM</p>
      <p>Saturday, September 12, 2026 2:00 PM</p>
      <p>Saturday, September 12, 2026 7:00 PM</p>
      <h2>Show Details</h2><p>A Pulitzer Prize-winning drama about family, genius and trust.</p>
      <a href="https://thepineappleplayhouse.ludus.com/">BUY TICKETS</a>
    </main>
    """
    parsed = events._pineapple_show_page_events(
        html, source, _window(), "https://www.pineappleplayhouse.com/seasonal-shows/proof"
    )
    assert [(row["starts_at"][:16], row["title"]) for row in parsed] == [
        ("2026-09-04T19:00", "Proof"),
        ("2026-09-12T14:00", "Proof"),
        ("2026-09-12T19:00", "Proof"),
    ]
    assert len({row["id"] for row in parsed}) == 3
    assert all(row["event_url"].endswith("/seasonal-shows/proof") for row in parsed)
    assert all("ludus.com" in row["ticket_url"] for row in parsed)


def test_vero_beach_opera_parser_reads_mainstage_and_met_live_transmissions():
    source = _source(
        id="vero-beach-opera", name="Vero Beach Opera", county="Indian River", city="Vero Beach",
        venue="VBHS Performing Arts Center", met_venue="The Majestic 11", adapter="opera_schedule",
        category="Arts & Culture", priority=7,
    )
    html = """
    <h2>TOSCA by Puccini</h2><p>Sunday, January 10, 2027 at 3 pm</p>
    <p>at the VBHS Performing Arts Center</p>
    <h2>MET Live in HD</h2>
    <p>September 19, 2026 at 1 pm: Twenty Years of the Met in Cinemas: An Anniversary Celebration</p>
    <p>October 3, 2026 at 1 pm: Così fan tutte (Mozart)</p>
    <h2>Prizes</h2>
    """
    parsed = events._opera_schedule_events(html, source, _window(180))
    assert any(row["title"] == "TOSCA by Puccini" and row["starts_at"].startswith("2027-01-10T15:00") for row in parsed)
    met = [row for row in parsed if "Twenty Years of the Met" in row["title"]][0]
    assert met["venue"] == "The Majestic 11"
    assert met["address"] == ""  # fixture omits met_address; never borrow the VBHS address
    assert met["starts_at"].startswith("2026-09-19T13:00")
    assert any("Così fan tutte" in row["title"] for row in parsed)


def test_source_scoped_title_exclusion_removes_repetitive_daily_museum_rows_only():
    source = _source(exclude_title_regex=r"^DAILY EXHIBIT$")
    window = _window()
    assert events._normalize_event({"title":"DAILY EXHIBIT", "starts_at":"2026-09-10T10:00:00-04:00"}, source, window) is None
    assert events._normalize_event({"title":"Special Museum Lecture", "starts_at":"2026-09-10T13:00:00-04:00"}, source, window)


def test_city_locality_can_authorize_cross_county_source_without_default_county():
    source = _source(county="", city="")
    row = events._normalize_event({
        "title":"Local Blues Jam", "starts_at":"2026-09-10T19:00:00-04:00",
        "city":"Vero Beach", "address":"123 Main St, Vero Beach, FL 32960",
    }, source, _window())
    assert row and row["county"] == "Indian River"


def test_same_day_event_that_already_ended_is_not_kept_until_midnight():
    source = _source()
    row = events._normalize_event({
        "title":"Morning Workshop", "starts_at":"2026-09-04T09:00:00-04:00", "ends_at":"2026-09-04T10:00:00-04:00"
    }, source, _window())
    assert row is None


def test_tribe_adapter_normalizes_manatee_center_event_with_official_venue_details():
    source = _source(
        id="manatee-center", name="The Manatee Center", county="St. Lucie", city="Fort Pierce",
        venue="Manatee Center", adapter="tribe", category="Outdoors & Nature", priority=7,
    )
    payload = {
        "events": [{
            "title": "Free Community Day",
            "start_date": "2026-09-30 10:00:00",
            "end_date": "2026-09-30 15:00:00",
            "all_day": False,
            "url": "https://manateecenter.org/event/free-community-day/",
            "description": "<p>Admission is waived for the community.</p>",
            "venue": {"venue": "Manatee Center", "address": "480 N Indian River Drive", "city": "Fort Pierce", "state": "FL", "zip": "34950"},
        }]
    }
    parsed = events._tribe_api_events(payload, source, _window())
    assert len(parsed) == 1
    assert parsed[0]["title"] == "Free Community Day"
    assert parsed[0]["starts_at"].startswith("2026-09-30T10:00")
    assert parsed[0]["venue"] == "Manatee Center"
    assert parsed[0]["county"] == "St. Lucie"


def test_elliott_calendar_generic_parser_keeps_special_event_but_drops_configured_daily_exhibit():
    source = _source(
        id="elliott-museum-events", name="Historical Society of Martin County — Elliott Museum",
        county="Martin", city="Stuart", venue="Elliott Museum", adapter="dated_headings",
        category="Arts & Culture", exclude_title_regex=r"^3D DOUBT YOUR EYES$",
    )
    html = """
    <section><p>September 23, 2026</p><p>1:00 pm - 2:30 pm</p>
      <h3><a href="/calendar/hidden-history/">The Hidden History of WWII in Florida</a></h3></section>
    <section><p>September 24, 2026</p><p>10:00 am - 5:00 pm</p>
      <h3><a href="/calendar/3d-doubt/">3D DOUBT YOUR EYES</a></h3></section>
    """
    parsed = events._dated_heading_events(html, source, _window())
    assert [row["title"] for row in parsed] == ["The Hidden History of WWII in Florida"]
    assert parsed[0]["starts_at"].startswith("2026-09-23T13:00")
    assert parsed[0]["event_url"].endswith("/calendar/hidden-history/")


def test_musicworks_dated_heading_parser_reads_future_emerson_center_concert():
    source = _source(
        id="musicworks-concerts", name="MusicWorks Concerts", county="Indian River", city="Vero Beach",
        venue="The Emerson Center", adapter="dated_headings", category="Live Music", priority=7,
    )
    html = """
    <article><h3>Go Now! The Music of the Moody Blues - The Tribute</h3>
      <p>Thursday November 19, 2026</p><p>Time: 7:00 pm</p><p>The Emerson Center</p></article>
    """
    parsed = events._dated_heading_events(html, source, _window(180))
    assert len(parsed) == 1
    assert parsed[0]["title"].startswith("Go Now!")
    assert parsed[0]["starts_at"].startswith("2026-11-19T19:00")
    assert parsed[0]["venue"] == "The Emerson Center"


def test_pineapple_linked_show_adapter_tolerates_one_broken_detail_page(monkeypatch):
    source = _source(
        id="pineapple-playhouse", name="Pineapple Playhouse", url="https://www.pineappleplayhouse.com/",
        county="St. Lucie", city="Fort Pierce", venue="Pineapple Playhouse",
        adapter="pineapple_linked_shows", category="Arts & Culture", priority=5,
    )
    homepage = """
    <a href="/seasonal-shows/proof">Proof</a>
    <a href="/seasonal-shows/broken">Broken show page</a>
    <a href="https://example.com/seasonal-shows/foreign">Foreign</a>
    """
    good = """<h1>Proof</h1><h2>Dates</h2><p>Saturday, September 12, 2026 7:00 PM</p>"""

    class Response:
        def __init__(self, text): self.text = text

    def fake_get(_session, url, **_kwargs):
        if url.endswith("/proof"):
            return Response(good)
        raise RuntimeError("fixture detail page unavailable")

    monkeypatch.setattr(events, "_get", fake_get)
    parsed = events._pineapple_events(object(), homepage, source, _window())
    assert len(parsed) == 1
    assert parsed[0]["title"] == "Proof"
    assert parsed[0]["starts_at"].startswith("2026-09-12T19:00")


def test_hobe_sound_farms_recurring_rules_generate_both_weekend_market_days_only_when_evidence_is_live():
    source = _source(
        id="hobe-sound-farms", name="Hobe Sound Farms", county="Martin", city="Hobe Sound",
        venue="Hobe Sound Farms", adapter="recurring_page", priority=7,
        recurring=[
            {"title":"Hobe Sound Farmers Market", "weekday":5, "time":"09:00", "end_time":"14:00", "category":"Food & Markets", "evidence":"Farmers Market Hours"},
            {"title":"Hobe Sound Farmers Market", "weekday":6, "time":"09:00", "end_time":"14:00", "category":"Food & Markets", "evidence":"Farmers Market Hours"},
        ],
    )
    parsed = events._recurring_events("<p>Farmers Market Hours Saturday & Sunday 9:00 AM – 2:00 PM</p>", source, _window(10))
    assert len(parsed) >= 2
    assert {events._parse_iso_datetime(row["starts_at"]).weekday() for row in parsed} == {5, 6}
    assert all(row["category"] == "Food & Markets" for row in parsed)
    assert events._recurring_events("<p>Farm Stand Hours Monday - Friday</p>", source, _window(10)) == []


def test_civicengage_ical_uses_real_event_detail_url_instead_of_relative_feed_link():
    source = _source(
        id="stuart-city-events",
        name="City of Stuart — City Events",
        url="https://www.stuartfl.gov/common/modules/iCalendar/iCalendar.aspx?catID=22&feed=calendar",
        page_url="https://www.stuartfl.gov/calendar.aspx",
        kind="government",
        adapter="ical",
    )
    ical = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260904T170000
DTEND:20260904T210000
SUMMARY:First Friday Art Walk
LOCATION:The Creek District of Arts & Entertainment
DESCRIPTION:https://www.stuartfl.gov/calendar.aspx?EID=6186
URL:/common/modules/iCalendar/iCalendar.aspx?feed=calendar&catID=22
END:VEVENT
END:VCALENDAR
"""
    parsed = events._parse_ical(ical, source, _window())
    assert len(parsed) == 1
    assert parsed[0]["event_url"] == "https://www.stuartfl.gov/calendar.aspx?EID=6186"
    assert parsed[0]["description"] == ""
    assert not parsed[0]["event_url"].startswith("/")


def test_relative_event_and_ticket_urls_resolve_against_source_not_tct():
    source = _source(
        url="https://venue.example/calendar/list",
        page_url="https://venue.example/calendar",
    )
    row = events._normalize_event(
        {
            "title": "Local Show",
            "starts_at": "2026-09-10T19:00:00-04:00",
            "event_url": "/events/local-show",
            "ticket_url": "/tickets/local-show",
        },
        source,
        _window(),
    )
    assert row
    assert row["event_url"] == "https://venue.example/events/local-show"
    assert row["ticket_url"] == "https://venue.example/tickets/local-show"


def test_events_page_omits_backend_process_copy_and_puts_events_before_archive():
    page = (ROOT / "events.html").read_text(encoding="utf-8")
    assert "Automatic updates" not in page
    assert "Duplicate listings combined" not in page
    assert "Sources refresh automatically" not in page
    nav_start = page.index('<nav class="category-nav">')
    nav_end = page.index("</nav>", nav_start)
    nav = page[nav_start:nav_end]
    assert nav.count('href="/events.html"') == 1
    assert nav.index('href="/events.html"') < nav.index('href="/archive.html"')


def test_sitewide_events_nav_normalizer_inserts_events_before_archive(tmp_path):
    import ast
    import re

    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "_normalize_events_navigation_sitewide"
    )
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {"Path": Path, "re": re}
    exec(compile(module, "generate.py", "exec"), namespace)
    normalize = namespace["_normalize_events_navigation_sitewide"]

    sample = tmp_path / "index.html"
    sample.write_text(
        '<nav class="category-nav">'
        '<a href="/weather.html" class="cat-btn">Weather</a>'
        '<a href="/archive.html" class="cat-btn">Archive</a>'
        '</nav>',
        encoding="utf-8",
    )
    result = normalize(tmp_path)
    rendered = sample.read_text(encoding="utf-8")
    assert result == {"scanned": 1, "updated": 1}
    assert rendered.count('href="/events.html"') == 1
    assert rendered.index('href="/events.html"') < rendered.index('href="/archive.html"')

    # A second pass is stable rather than appending another Events tab.
    again = normalize(tmp_path)
    assert again == {"scanned": 1, "updated": 0}


def test_cached_civicengage_rows_cannot_restore_relative_event_links():
    source = _source(
        id="stuart-city-events",
        name="City of Stuart — City Events",
        url="https://www.stuartfl.gov/common/modules/iCalendar/iCalendar.aspx?catID=22&feed=calendar",
        page_url="https://www.stuartfl.gov/calendar.aspx",
        kind="government",
        adapter="ical",
    )
    cache = {
        "schema_version": 1,
        "sources": {
            "stuart-city-events": {
                "events": [{
                    "title": "First Friday Art Walk",
                    "starts_at": "2026-09-04T17:00:00-04:00",
                    "ends_at": "2026-09-04T21:00:00-04:00",
                    "county": "Martin",
                    "city": "Stuart",
                    "category": "Arts & Culture",
                    "description": "https://www.stuartfl.gov/calendar.aspx?EID=6186",
                    "event_url": "/common/modules/iCalendar/iCalendar.aspx?feed=calendar&catID=22",
                }]
            }
        },
    }
    parsed = events._cached_source_events(cache, "stuart-city-events", source, _window())
    assert len(parsed) == 1
    assert parsed[0]["event_url"] == "https://www.stuartfl.gov/calendar.aspx?EID=6186"
    assert parsed[0]["description"] == ""
