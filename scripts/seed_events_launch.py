#!/usr/bin/env python3
"""One-time launch seed for the TCT events page.

This file is not called by production workflows. It exists only to make the release artifact
useful before its first network refresh, using events verified from official source pages on
2026-09-04. Production ownership immediately transfers to scripts/update_events.py.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("TCT_EVENTS_NOW", "2026-09-04T17:45:00-04:00")

from update_events import (  # noqa: E402
    CACHE_PATH, EVENTS_PATH, SOURCE_PATH, STATUS_PATH, SCHEMA_VERSION,
    _atomic_json, _dedupe_cross_source, _normalize_event, _render_page, _window,
)

ROOT = Path(__file__).resolve().parents[1]
config = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
sources = {source["id"]: source for source in config["sources"]}
window = _window(int(config.get("lookahead_days", 180)))

# title, start, end, source id, optional metadata
ROWS = [
    # Martin County: official city/community/venue schedules.
    ("First Friday Art Walk", "2026-09-04T17:00:00-04:00", "2026-09-04T21:00:00-04:00", "stuart-city-events", {"venue":"The Creek District of Arts & Entertainment", "event_url":"https://www.stuartfl.gov/Calendar.aspx"}),
    ("Rock'n Riverwalk", "2026-09-06T13:00:00-04:00", "2026-09-06T16:00:00-04:00", "stuart-city-events", {"venue":"Riverwalk Stage"}),
    ("Picnic in the Park", "2026-09-10T18:00:00-04:00", "2026-09-10T20:00:00-04:00", "stuart-city-events", {"venue":"Memorial Park Amphitheater"}),
    ("Rock'n Riverwalk", "2026-09-13T13:00:00-04:00", "2026-09-13T16:00:00-04:00", "stuart-city-events", {"venue":"Riverwalk Stage"}),
    ("Rock'n Riverwalk", "2026-09-20T13:00:00-04:00", "2026-09-20T16:00:00-04:00", "stuart-city-events", {"venue":"Riverwalk Stage"}),
    ("NAACP 6th Annual 5K / 10K Race", "2026-09-26T07:00:00-04:00", "2026-09-26T09:00:00-04:00", "stuart-city-events", {"venue":"Memorial Park"}),
    ("Downtown Stuart Car & Bike Show", "2026-09-26T09:00:00-04:00", "2026-09-26T13:00:00-04:00", "stuart-city-events", {"venue":"Stuart City Hall and Annex Parking Lots"}),
    ("Little Lamb Family Festival", "2026-09-26T11:00:00-04:00", "2026-09-26T15:00:00-04:00", "stuart-city-events", {"venue":"Memorial Park Amphitheater"}),
    ("Rock'n Riverwalk", "2026-09-27T13:00:00-04:00", "2026-09-27T16:00:00-04:00", "stuart-city-events", {"venue":"Riverwalk Stage"}),

    ("RAELYN NELSON", "2026-09-04T19:00:00-04:00", None, "terra-fermata", {"price":"Advance tickets $17.85 total cost"}),
    ("FREEBIRD ATL - The Ultimate Lynyrd Skynyrd Experience", "2026-09-05T19:00:00-04:00", None, "terra-fermata", {"price":"Advance $14.20 total; $20 at the door"}),
    ("SPIRAL LIGHT - Grateful Labor Day Weekend w/Billy Gilmore", "2026-09-06T19:00:00-04:00", None, "terra-fermata", {"price":"$10 advance; $15 at the door"}),
    ("LEATHER & LACE DUO", "2026-09-09T19:00:00-04:00", None, "terra-fermata", {"price":"$5 admission"}),
    ("TERRA THURSDAY JAM", "2026-09-10T19:00:00-04:00", None, "terra-fermata", {"price":"No cover"}),
    ("THE CHILI POPPERS - Red Hot Chili Peppers Tribute Band", "2026-09-11T19:00:00-04:00", None, "terra-fermata", {"price":"Advance tickets $17.85 total cost"}),
    ("CRAZY HORSES Neil Young Tribute by Leo Lee Rock Band", "2026-09-12T19:00:00-04:00", None, "terra-fermata", {"price":"Advance $10.20 total; $15 at the door"}),
    ("BROTHERS AFTER ALL - Allman Brothers Tribute", "2026-09-19T19:30:00-04:00", None, "terra-fermata", {}),
    ("DEAD ALL OVER", "2026-09-20T19:00:00-04:00", None, "terra-fermata", {}),

    # Pineapple Playhouse — exact performance dates from the official show page.
    ("Proof", "2026-09-04T19:00:00-04:00", None, "pineapple-playhouse", {"event_url":"https://www.pineappleplayhouse.com/seasonal-shows/proof", "ticket_url":"https://thepineappleplayhouse.ludus.com/"}),
    ("Proof", "2026-09-05T14:00:00-04:00", None, "pineapple-playhouse", {"event_url":"https://www.pineappleplayhouse.com/seasonal-shows/proof", "ticket_url":"https://thepineappleplayhouse.ludus.com/"}),
    ("Proof", "2026-09-06T14:00:00-04:00", None, "pineapple-playhouse", {"event_url":"https://www.pineappleplayhouse.com/seasonal-shows/proof", "ticket_url":"https://thepineappleplayhouse.ludus.com/"}),
    ("Proof", "2026-09-11T19:00:00-04:00", None, "pineapple-playhouse", {"event_url":"https://www.pineappleplayhouse.com/seasonal-shows/proof", "ticket_url":"https://thepineappleplayhouse.ludus.com/"}),
    ("Proof", "2026-09-12T14:00:00-04:00", None, "pineapple-playhouse", {"event_url":"https://www.pineappleplayhouse.com/seasonal-shows/proof", "ticket_url":"https://thepineappleplayhouse.ludus.com/"}),
    ("Proof", "2026-09-12T19:00:00-04:00", None, "pineapple-playhouse", {"event_url":"https://www.pineappleplayhouse.com/seasonal-shows/proof", "ticket_url":"https://thepineappleplayhouse.ludus.com/"}),
    ("Proof", "2026-09-13T14:00:00-04:00", None, "pineapple-playhouse", {"event_url":"https://www.pineappleplayhouse.com/seasonal-shows/proof", "ticket_url":"https://thepineappleplayhouse.ludus.com/"}),

    # Elliott Museum / Historical Society of Martin County.
    ("Leaf It to the E", "2026-09-10T17:00:00-04:00", "2026-09-10T19:00:00-04:00", "elliott-museum-events", {"event_url":"https://hsmc-fl.com/calendar/leaf-it-to-the-e/"}),
    ("The Hidden History of WWII in Florida", "2026-09-23T13:00:00-04:00", "2026-09-23T14:30:00-04:00", "elliott-museum-events", {"event_url":"https://hsmc-fl.com/calendar/the-hidden-history-of-wwii-in-florida/"}),
    ("Turkish Mosaic Candle Holder & Lamp Workshop", "2026-09-24T13:00:00-04:00", "2026-09-24T16:00:00-04:00", "elliott-museum-events", {"event_url":"https://hsmc-fl.com/calendar/turkish-mosaic-candle-holder-lamp-workshop/", "category":"Classes & Workshops"}),

    ("The Artimus Pyle Band - Honoring Ronnie Van Zant’s Lynyrd Skynyrd", "2026-09-20T19:00:00-04:00", None, "lyric-theatre", {}),
    ("Kevin Nealon", "2026-09-24T19:00:00-04:00", None, "lyric-theatre", {}),
    ("Dancing with the Martin Stars", "2026-09-26T19:00:00-04:00", None, "lyric-theatre", {}),

    ("Bank of America Museums on Us", "2026-09-05T10:00:00-04:00", "2026-09-05T16:00:00-04:00", "childrens-museum-treasure-coast", {}),
    ("Sensory Friendly Day", "2026-09-13T09:30:00-04:00", "2026-09-13T11:00:00-04:00", "childrens-museum-treasure-coast", {}),
    ("Treasure Fest & Worldwide Day of Play", "2026-09-26T10:00:00-04:00", "2026-09-26T13:00:00-04:00", "childrens-museum-treasure-coast", {}),

    ("A.C.T Studio Theatre presents \"Fools\"", "2026-09-04T19:30:00-04:00", "2026-09-04T21:00:00-04:00", "martinarts-cultural-calendar", {"venue":"A.C.T. Studio Theatre"}),
    ("A.C.T Studio Theatre presents \"Fools\"", "2026-09-05T19:30:00-04:00", "2026-09-05T21:00:00-04:00", "martinarts-cultural-calendar", {"venue":"A.C.T. Studio Theatre"}),
    ("A.C.T Studio Theatre presents \"Fools\"", "2026-09-06T15:00:00-04:00", "2026-09-06T16:30:00-04:00", "martinarts-cultural-calendar", {"venue":"A.C.T. Studio Theatre"}),
    ("The Barn Theatre presents \"Sister Act\"", "2026-09-10T20:00:00-04:00", "2026-09-10T22:30:00-04:00", "martinarts-cultural-calendar", {"venue":"The Barn Theatre"}),
    ("The Barn Theatre presents \"Sister Act\"", "2026-09-11T20:00:00-04:00", "2026-09-11T22:30:00-04:00", "martinarts-cultural-calendar", {"venue":"The Barn Theatre"}),
    ("The Barn Theatre presents \"Sister Act\"", "2026-09-12T20:00:00-04:00", "2026-09-12T22:30:00-04:00", "martinarts-cultural-calendar", {"venue":"The Barn Theatre"}),
    ("The Barn Theatre presents \"Sister Act\"", "2026-09-13T14:00:00-04:00", "2026-09-13T16:30:00-04:00", "martinarts-cultural-calendar", {"venue":"The Barn Theatre"}),

    # St. Lucie County.
    ("Friday Fest", "2026-09-04T17:30:00-04:00", "2026-09-04T20:30:00-04:00", "main-street-fort-pierce", {"venue":"Marina Square", "address":"1 Avenue A, Fort Pierce, FL 34950", "event_url":"https://mainstreetfortpierce.org/local-events-calendar/friday-fest-september-4-2026"}),
    ("Food Trucks and Tributes – Johnny Cash Tribute", "2026-09-04T17:00:00-04:00", "2026-09-04T21:00:00-04:00", "visit-st-lucie", {"venue":"Tradition Square", "city":"Port St. Lucie"}),
    ("Jupiter Hammerheads @ St. Lucie Mets", "2026-09-04T18:10:00-04:00", "2026-09-04T21:10:00-04:00", "visit-st-lucie", {"venue":"Clover Park", "city":"Port St. Lucie", "category":"Sports & Recreation"}),
    ("Downtown Fort Pierce Farmers Market", "2026-09-05T08:00:00-04:00", "2026-09-05T12:00:00-04:00", "visit-st-lucie", {"venue":"Downtown Farmers’ Market of Fort Pierce", "city":"Fort Pierce", "category":"Food & Markets"}),
    ("Neighborhood Farmer’s Market at Tradition Square", "2026-09-06T09:00:00-04:00", "2026-09-06T14:00:00-04:00", "tradition-events", {"venue":"Tradition Square", "category":"Food & Markets", "event_url":"https://traditionfl.com/events/neighborhood-farmers-market-at-tradition-square/"}),
    ("Breakfast in the Square", "2026-09-11T09:00:00-04:00", "2026-09-11T12:00:00-04:00", "tradition-events", {"venue":"Tradition Square", "category":"Food & Markets", "event_url":"https://traditionfl.com/events/breakfast-in-the-square-12/"}),
    ("Where the Gardens Waits: An 80’s Glow Party Book Event!", "2026-09-18T18:00:00-04:00", "2026-09-18T20:00:00-04:00", "heathcote-botanical-gardens", {}),
    ("GARDENS JAM", "2026-09-09T18:30:00-04:00", "2026-09-09T21:00:00-04:00", "fort-pierce-jazz-blues", {"venue":"Port St. Lucie Botanical Gardens"}),
    ("FORT PIERCE - Yacht Club", "2026-09-15T18:30:00-04:00", "2026-09-15T21:00:00-04:00", "fort-pierce-jazz-blues", {"venue":"Fort Pierce Yacht Club"}),
    ("GAZEBO - Silver Mullets", "2026-09-19T09:00:00-04:00", "2026-09-19T12:00:00-04:00", "fort-pierce-jazz-blues", {}),
    ("GARDENS JAM", "2026-09-23T18:30:00-04:00", "2026-09-23T21:00:00-04:00", "fort-pierce-jazz-blues", {"venue":"Port St. Lucie Botanical Gardens"}),
    ("FARMERS MARKET - Latin Band", "2026-09-26T09:00:00-04:00", "2026-09-26T12:00:00-04:00", "fort-pierce-jazz-blues", {"venue":"Downtown Fort Pierce Farmers Market"}),

    # Manatee Center official calendar.
    ("Lunch & Learn Lecture Series", "2026-09-11T12:00:00-04:00", "2026-09-11T13:00:00-04:00", "manatee-center", {"venue":"Fort Pierce Yacht Club", "address":"700 N Indian River Dr, Fort Pierce, FL", "event_url":"https://manateecenter.org/events/"}),
    ("ManaTales – Thursdays", "2026-09-17T09:30:00-04:00", "2026-09-17T12:00:00-04:00", "manatee-center", {"description":"Two sessions are offered: 9:30–10:30 a.m. and 11 a.m.–noon."}),
    ("ManaTales – Saturdays", "2026-09-26T09:30:00-04:00", "2026-09-26T12:00:00-04:00", "manatee-center", {"description":"Two sessions are offered: 9:30–10:30 a.m. and 11 a.m.–noon."}),
    ("Free Community Day", "2026-09-30T10:00:00-04:00", "2026-09-30T15:00:00-04:00", "manatee-center", {}),
    ("Learn at the Lagoon with a Creekside Chat at the Manatee Center", "2026-09-30T11:00:00-04:00", "2026-09-30T13:00:00-04:00", "manatee-center", {}),

    # Hobe Sound Farms recurring public market (launch seed; production generates recurrences).
    ("Hobe Sound Farmers Market", "2026-09-05T09:00:00-04:00", "2026-09-05T14:00:00-04:00", "hobe-sound-farms", {"category":"Food & Markets"}),
    ("Hobe Sound Farmers Market", "2026-09-06T09:00:00-04:00", "2026-09-06T14:00:00-04:00", "hobe-sound-farms", {"category":"Food & Markets"}),
    ("Hobe Sound Farmers Market", "2026-09-12T09:00:00-04:00", "2026-09-12T14:00:00-04:00", "hobe-sound-farms", {"category":"Food & Markets"}),
    ("Hobe Sound Farmers Market", "2026-09-13T09:00:00-04:00", "2026-09-13T14:00:00-04:00", "hobe-sound-farms", {"category":"Food & Markets"}),

    # Indian River County.
    ("Greg & Brian", "2026-09-04T15:00:00-04:00", None, "capt-hirams", {}),
    ("Hypersona Duo", "2026-09-04T19:30:00-04:00", None, "capt-hirams", {}),
    ("Innuendo Duo", "2026-09-05T15:00:00-04:00", None, "capt-hirams", {}),
    ("Hypersona Duo", "2026-09-05T19:30:00-04:00", None, "capt-hirams", {}),
    ("Caribbean Chillers", "2026-09-06T14:00:00-04:00", None, "capt-hirams", {}),
    ("Brad Brock", "2026-09-07T11:00:00-04:00", None, "capt-hirams", {}),
    ("AnnaLee Talley", "2026-09-07T16:00:00-04:00", None, "capt-hirams", {}),
    ("Cover Up", "2026-09-11T19:30:00-04:00", None, "capt-hirams", {}),
    ("The Spazmatics", "2026-09-12T19:30:00-04:00", None, "capt-hirams", {}),
    ("Metalucious", "2026-09-19T19:30:00-04:00", None, "capt-hirams", {}),

    ("Pippin & Willin'", "2026-09-04T17:30:00-04:00", "2026-09-04T20:30:00-04:00", "riverside-loop-music", {}),
    ("Collins & Company", "2026-09-05T17:30:00-04:00", "2026-09-05T20:30:00-04:00", "riverside-loop-music", {}),
    ("Abby Owens", "2026-09-10T17:30:00-04:00", "2026-09-10T20:30:00-04:00", "riverside-loop-music", {}),
    ("Chemistry", "2026-09-11T17:30:00-04:00", "2026-09-11T20:30:00-04:00", "riverside-loop-music", {}),
    ("Glory Days", "2026-09-12T17:30:00-04:00", "2026-09-12T20:00:00-04:00", "riverside-loop-music", {}),
    ("Brad Brock's One Man Band", "2026-09-17T17:30:00-04:00", "2026-09-17T20:30:00-04:00", "riverside-loop-music", {}),
    ("SoulTime", "2026-09-18T17:30:00-04:00", "2026-09-18T20:30:00-04:00", "riverside-loop-music", {}),
    ("Joe Reid & Heartland Band", "2026-09-19T17:30:00-04:00", "2026-09-19T20:30:00-04:00", "riverside-loop-music", {}),
    ("Dave & the Wave", "2026-09-24T17:30:00-04:00", "2026-09-24T20:30:00-04:00", "riverside-loop-music", {}),
    ("Vince Love and Soul Cats", "2026-09-25T17:30:00-04:00", "2026-09-25T20:30:00-04:00", "riverside-loop-music", {}),
    ("Dottie Kelly & the Rock House Band", "2026-09-26T17:30:00-04:00", "2026-09-26T20:30:00-04:00", "riverside-loop-music", {}),
    ("Live Music Wednesday at Sailfish Brewing", "2026-09-09T17:00:00-04:00", "2026-09-09T20:00:00-04:00", "sailfish-vero-beach", {}),
    ("Sunday Funday Live Music at Sailfish Brewing", "2026-09-06T12:00:00-04:00", "2026-09-06T15:00:00-04:00", "sailfish-vero-beach", {}),

    # MusicWorks at The Emerson Center — official 2026–27 concert schedule.
    ("Go Now! The Music of the Moody Blues - The Tribute", "2026-11-19T19:00:00-05:00", None, "musicworks-concerts", {}),
    ("One More Night, The Music of Phil Collins and Genesis", "2027-01-14T19:00:00-05:00", None, "musicworks-concerts", {}),
    ("Jay and The Americans", "2027-01-21T19:00:00-05:00", None, "musicworks-concerts", {}),
    ("The Drifters", "2027-01-28T19:00:00-05:00", None, "musicworks-concerts", {}),
    ("The Docksiders - A Yacht Rock Experience", "2027-02-04T19:00:00-05:00", None, "musicworks-concerts", {}),
    ("MJ Live! Michael Jackson Tribute Concert", "2027-02-11T19:00:00-05:00", None, "musicworks-concerts", {}),
    ("Celebrating Meat Loaf", "2027-02-18T19:00:00-05:00", None, "musicworks-concerts", {}),
    ("Eaglemania, The World’s Greatest Eagles Tribute Band", "2027-02-25T19:00:00-05:00", None, "musicworks-concerts", {}),
    ("Eaglemania, The World’s Greatest Eagles Tribute Band", "2027-02-26T19:00:00-05:00", None, "musicworks-concerts", {}),

    # Vero Beach Opera and its MET Live in HD presentations.
    ("Twenty Years of the Met in Cinemas: An Anniversary Celebration", "2026-09-19T13:00:00-04:00", None, "vero-beach-opera", {"venue":"The Majestic 11", "address":"940 14th Ln, Vero Beach, FL 32960"}),
    ("Così fan tutte (Mozart)", "2026-10-03T13:00:00-04:00", None, "vero-beach-opera", {"venue":"The Majestic 11", "address":"940 14th Ln, Vero Beach, FL 32960"}),
    ("Macbeth (Verdi – New Production)", "2026-10-17T13:00:00-04:00", None, "vero-beach-opera", {"venue":"The Majestic 11", "address":"940 14th Ln, Vero Beach, FL 32960"}),
    ("Carmen by Bizet", "2026-11-14T13:00:00-05:00", None, "vero-beach-opera", {"venue":"The Majestic 11", "address":"940 14th Ln, Vero Beach, FL 32960"}),
    ("Samson et Dalila (Saint-Saëns)", "2026-12-05T12:00:00-05:00", None, "vero-beach-opera", {"venue":"The Majestic 11", "address":"940 14th Ln, Vero Beach, FL 32960"}),
    ("The Magic Flute by Mozart", "2026-12-12T13:00:00-05:00", None, "vero-beach-opera", {"venue":"The Majestic 11", "address":"940 14th Ln, Vero Beach, FL 32960"}),
    ("TOSCA by Puccini", "2027-01-10T15:00:00-05:00", None, "vero-beach-opera", {}),
    ("La Fanciulla del West (Puccini)", "2027-01-23T13:00:00-05:00", None, "vero-beach-opera", {"venue":"The Majestic 11", "address":"940 14th Ln, Vero Beach, FL 32960"}),
    ("Rising Stars Competition — Semifinals", "2027-02-11T15:00:00-05:00", None, "vero-beach-opera", {}),
    ("Rising Stars Competition — Finals", "2027-02-12T15:00:00-05:00", None, "vero-beach-opera", {}),
    ("Rising Stars Competition — Awards Concert", "2027-02-13T19:00:00-05:00", None, "vero-beach-opera", {}),
]

by_source = defaultdict(list)
all_events = []
for title, start, end, source_id, extra in ROWS:
    source = sources[source_id]
    raw = {"title": title, "starts_at": start, "ends_at": end, "event_url": source.get("page_url") or source.get("url"), **extra}
    event = _normalize_event(raw, source, window)
    if event:
        by_source[source_id].append(event)
        all_events.append(event)

events = _dedupe_cross_source(all_events)
generated = "2026-09-04T17:45:00-04:00"
status_rows = []
for source in config["sources"]:
    rows = by_source.get(source["id"], [])
    status_rows.append({
        "id": source["id"], "name": source["name"], "status": "seeded" if rows else "pending",
        "event_count": len(rows), "url": source.get("page_url") or source.get("url"), "error": "",
    })
cache = {"schema_version": SCHEMA_VERSION, "sources": {}}
for source_id, rows in by_source.items():
    source = sources[source_id]
    cache["sources"][source_id] = {
        "fetched_at": generated,
        "source_url": source.get("page_url") or source.get("url"),
        "event_count": len(rows),
        "events": rows,
    }
status = {
    "schema_version": SCHEMA_VERSION, "generated_at": generated, "source_count": len(status_rows),
    "successful_sources": 0, "cached_sources": len(by_source), "failed_sources": 0,
    "event_count": len(events), "sources": status_rows,
}
payload = {"schema_version": SCHEMA_VERSION, "generated_at": generated, "timezone": "America/New_York", "event_count": len(events), "events": events}
_atomic_json(CACHE_PATH, cache)
_atomic_json(EVENTS_PATH, payload)
_atomic_json(STATUS_PATH, status)
_render_page(events, status)
print(f"Seeded {len(events)} launch events across {len(by_source)} verified sources")
