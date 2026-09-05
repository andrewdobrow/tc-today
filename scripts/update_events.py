#!/usr/bin/env python3
"""Treasure Coast Today deterministic events aggregation.

This intentionally does not use an LLM.  Each configured source is fetched independently,
normalized into one event schema, deduplicated, cached, and rendered into events.html.
A source outage falls back to its last known good cache without taking down the calendar.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "data" / "events-sources.json"
CACHE_PATH = ROOT / "data" / "events-source-cache.json"
EVENTS_PATH = ROOT / "data" / "events.json"
STATUS_PATH = ROOT / "data" / "events-source-status.json"
EVENTS_HTML_PATH = ROOT / "events.html"
TZ = ZoneInfo("America/New_York")
USER_AGENT = "Treasure Coast Today Events/1.0 (+https://treasurecoast.today/events.html)"
HTTP_TIMEOUT = 25
SCHEMA_VERSION = 1
INITIAL_EVENT_ROWS = 10
EVENT_JSONLD_ROWS = 10
DYNAMIC_START = "<!-- TCT_EVENTS_DYNAMIC_START -->"
DYNAMIC_END = "<!-- TCT_EVENTS_DYNAMIC_END -->"
JSONLD_START = "<!-- TCT_EVENTS_JSONLD_START -->"
JSONLD_END = "<!-- TCT_EVENTS_JSONLD_END -->"

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

CATEGORY_ORDER = [
    "Live Music", "Arts & Culture", "Family", "Food & Markets", "Sports & Recreation",
    "Outdoors & Nature", "Community", "Classes & Workshops",
]

BOILERPLATE_TITLES = {
    "events", "upcoming events", "upcoming shows", "event calendar", "events calendar",
    "events & meetings", "calendar of events", "list of events", "featured events",
    "event views navigation", "events search and views navigation", "filters", "details",
    "details and tickets", "view event", "view event details", "buy tickets", "learn more",
    "contact us", "our upcoming shows", "this season at the sunrise theatre",
}

HARD_REJECT_RE = re.compile(
    r"\b(?:private event|private function|cancelled|canceled|postponed|garage sale|yard sale)\b|^closed$",
    re.I,
)
GOVERNMENT_MEETING_RE = re.compile(
    r"\b(?:commission|council|board|committee|advisory|authority|hearing|workshop|agenda|meeting)\b",
    re.I,
)

FULL_DATE_RE = re.compile(
    r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(20\d{2})",
    re.I,
)
SHORT_DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2})(?:,\s*(20\d{2}))?\b",
    re.I,
)
TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b", re.I)
TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?m\.?)?\s*(?:-|–|—|to)\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b",
    re.I,
)

CITY_TO_COUNTY = {
    "stuart": "Martin", "jensen beach": "Martin", "palm city": "Martin",
    "hobe sound": "Martin", "indian town": "Martin", "indiantown": "Martin",
    "port salerno": "Martin", "sewall s point": "Martin", "jupiter island": "Martin",
    "port st lucie": "St. Lucie", "port saint lucie": "St. Lucie",
    "fort pierce": "St. Lucie", "st lucie village": "St. Lucie",
    "vero beach": "Indian River", "sebastian": "Indian River", "fellsmere": "Indian River",
    "indian river shores": "Indian River", "orchid": "Indian River",
}


class EventSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Window:
    now: datetime
    start: datetime
    end: datetime


def _now_local() -> datetime:
    forced = str(__import__("os").environ.get("TCT_EVENTS_NOW", "")).strip()
    if forced:
        parsed = datetime.fromisoformat(forced.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TZ)
        return parsed.astimezone(TZ)
    return datetime.now(TZ)


def _window(lookahead_days: int) -> Window:
    now = _now_local()
    start = datetime.combine(now.date(), time.min, tzinfo=TZ)
    return Window(now=now, start=start, end=start + timedelta(days=lookahead_days + 1))


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    _atomic_text(path, text)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.replace(path)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(str(value or ""))).strip()


def _clip(value: Any, limit: int = 260) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return cut + "…"


def _slug_text(value: str) -> str:
    text = value.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _event_id(event: dict[str, Any]) -> str:
    seed = "|".join([
        _slug_text(event.get("title", "")),
        str(event.get("starts_at", ""))[:16],
        _slug_text(event.get("venue", "") or event.get("city", "")),
    ])
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:18]


def _infer_year(month: int, day: int, now: datetime) -> int:
    year = now.year
    candidate = date(year, month, day)
    if candidate < now.date() - timedelta(days=21):
        year += 1
    return year


def _parse_clock(text_value: str) -> tuple[int, int] | None:
    match = TIME_RE.search(_clean(text_value))
    if not match:
        if re.fullmatch(r"\d{1,2}:\d{2}", _clean(text_value)):
            h, m = [int(part) for part in _clean(text_value).split(":")]
            return h, m
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = match.group(3).lower()
    if ampm == "p" and hour != 12:
        hour += 12
    if ampm == "a" and hour == 12:
        hour = 0
    return hour, minute


def _parse_full_date(text_value: str, default_time: tuple[int, int] = (0, 0)) -> datetime | None:
    text_value = _clean(text_value)
    match = FULL_DATE_RE.search(text_value)
    if not match:
        return None
    month = MONTHS[match.group(1).lower()]
    day = int(match.group(2))
    year = int(match.group(3))
    clock_match = TIME_RE.search(text_value[match.end():]) or TIME_RE.search(text_value)
    if clock_match:
        clock = _parse_clock(clock_match.group(0)) or default_time
    else:
        clock = default_time
    try:
        return datetime(year, month, day, clock[0], clock[1], tzinfo=TZ)
    except ValueError:
        return None


def _parse_short_date(month_text: str, day_text: str, year_text: str | None, now: datetime, clock_text: str = "") -> datetime | None:
    month = MONTHS.get(month_text.lower())
    if not month:
        return None
    day = int(day_text)
    year = int(year_text) if year_text else _infer_year(month, day, now)
    clock = _parse_clock(clock_text) or (0, 0)
    try:
        return datetime(year, month, day, clock[0], clock[1], tzinfo=TZ)
    except ValueError:
        return None


def _iso_local(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ).isoformat(timespec="minutes")


def _parse_iso_datetime(value: Any) -> datetime | None:
    text_value = _clean(value)
    if not text_value:
        return None
    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        parsed = _parse_full_date(text_value)
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ)


def _source_url(source: dict[str, Any]) -> str:
    return _clean(source.get("page_url") or source.get("url"))


def _absolute_event_url(value: Any, source: dict[str, Any]) -> str:
    """Return an absolute URL for an event/ticket link from a source adapter.

    Several municipal iCalendar feeds emit root-relative ``URL`` properties.
    If those strings are written directly into events.html, the browser resolves
    them against treasurecoast.today and creates a dead TCT link. Resolve all
    relative source links against the source's own origin before publication.
    """
    raw = _clean(value)
    if not raw:
        return ""
    if raw.startswith("//"):
        return "https:" + raw
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return raw
    if parsed.scheme:
        return raw
    base = _clean(source.get("page_url") or source.get("url"))
    return urljoin(base, raw) if base else raw


def _standalone_http_url(value: Any) -> str:
    """Return *value* only when it is effectively just one HTTP(S) URL."""
    text = _clean(value)
    if not text:
        return ""
    match = re.fullmatch(r"https?://[^\s<>]+", text, re.I)
    return match.group(0).rstrip(".,;)") if match else ""


def _county_from_locality(city: Any, address: Any = "") -> str:
    city_key = _slug_text(_clean(city))
    if city_key in CITY_TO_COUNTY:
        return CITY_TO_COUNTY[city_key]
    address_key = _slug_text(_clean(address))
    for place, county in sorted(CITY_TO_COUNTY.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?:^| )\b{re.escape(place)}\b(?: |$)", address_key):
            return county
    return ""


def _source_excludes_title(title: str, source: dict[str, Any]) -> bool:
    pattern = _clean(source.get("exclude_title_regex"))
    if not pattern:
        return False
    try:
        return re.search(pattern, title, re.I) is not None
    except re.error as exc:
        raise RuntimeError(f"Invalid exclude_title_regex for {source.get('id')}: {exc}") from exc


def _category_for(event: dict[str, Any], source: dict[str, Any]) -> str:
    preset = _clean(event.get("category") or source.get("category"))
    if preset in CATEGORY_ORDER:
        return preset
    text_value = _slug_text(" ".join([
        str(event.get("title", "")), str(event.get("description", "")), str(event.get("venue", "")),
    ]))
    rules = [
        ("Live Music", r"\b(?:live music|concert|band|tribute|singer|songwriter|jazz|blues|rock|reggae|motown|orchestra|symphony|jam|dueling piano|music bingo)\b"),
        ("Arts & Culture", r"\b(?:theatre|theater|comedy|film|movie|art|artist|gallery|museum|exhibit|exhibition|ballet|opera|dance performance|lecture|author|book talk)\b"),
        ("Family", r"\b(?:family|families|kids|children|child|touch a truck|story time|storytime|holiday|parade|pumpkin|santa)\b"),
        ("Food & Markets", r"\b(?:market|farmers|farmer s|food truck|food trucks|wine|brewery|beer|bbq|barbecue|bacon|culinary|tasting|brunch)\b"),
        ("Sports & Recreation", r"\b(?:baseball|mets|wrestling|5k|10k|race|run club|golf|fishing|pickleball|soccer|football|basketball|tournament|game at|kayak|paddle)\b"),
        ("Outdoors & Nature", r"\b(?:nature|garden|botanical|lagoon|wildlife|bird|coastal|cleanup|clean up|kayak|paddle|hike|hiking|eco|environment|ocean|fishing)\b"),
        ("Classes & Workshops", r"\b(?:class|workshop|lesson|yoga|tai chi|qigong|seminar|training|studio)\b"),
        ("Community", r"\b(?:festival|fair|ceremony|fundraiser|community|first friday|friday fest|art walk|car show|market|celebration)\b"),
    ]
    for category, pattern in rules:
        if re.search(pattern, text_value, re.I):
            return category
    return "Community"


def _normalize_event(raw: dict[str, Any], source: dict[str, Any], window: Window) -> dict[str, Any] | None:
    title = _clean(raw.get("title"))
    if not title or title.lower() in BOILERPLATE_TITLES or len(title) < 3:
        return None
    if HARD_REJECT_RE.search(title) or _source_excludes_title(title, source):
        return None
    if source.get("kind") == "government" and GOVERNMENT_MEETING_RE.search(title):
        return None

    start = _parse_iso_datetime(raw.get("starts_at") or raw.get("start"))
    if start is None:
        return None
    end = _parse_iso_datetime(raw.get("ends_at") or raw.get("end"))
    if end and end < start:
        end = None
    # Treat multi-month calendar encodings for recurring programs as an instance, not
    # one impossibly long event card. True exhibitions may legitimately span weeks.
    if end and (end - start) > timedelta(days=31) and not re.search(r"\b(?:exhibit|exhibition)\b", title, re.I):
        end = None

    address = _clean(raw.get("address") or source.get("address"))
    city = _clean(raw.get("city") or source.get("city"))
    county = _clean(raw.get("county") or source.get("county")) or _county_from_locality(city, address)
    event = {
        "title": title,
        "starts_at": _iso_local(start),
        "ends_at": _iso_local(end),
        "all_day": bool(raw.get("all_day", False)),
        "venue": _clean(raw.get("venue") or source.get("venue")),
        "address": address,
        "city": city,
        "county": county,
        "category": _clean(raw.get("category")),
        "price": _clip(raw.get("price"), 100),
        "description": _clip(raw.get("description"), 260),
        "event_url": _absolute_event_url(
            raw.get("event_url") or raw.get("url") or _source_url(source), source
        ),
        "ticket_url": _absolute_event_url(raw.get("ticket_url"), source),
        "source_name": _clean(source.get("name")),
        "source_url": _source_url(source),
        "source_id": _clean(source.get("id")),
        "source_priority": int(source.get("priority", 50)),
        "source_kind": _clean(source.get("kind")),
    }
    event["category"] = _category_for(event, source)

    # Keep only the Treasure Coast counties this product covers.
    if event["county"] not in {"Martin", "St. Lucie", "Indian River"}:
        return None
    if start >= window.end:
        return None
    effective_end = end or (start + timedelta(hours=4))
    if effective_end < window.now:
        return None

    event["id"] = _event_id(event)
    return event


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/json,text/calendar;q=0.9,*/*;q=0.7"})
    return session


def _get(session: requests.Session, url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
    response = session.get(url, params=params, timeout=HTTP_TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


def _unescape_ical(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _parse_ical_datetime(key: str, value: str) -> tuple[datetime | None, bool]:
    all_day = "VALUE=DATE" in key.upper() or re.fullmatch(r"\d{8}", value.strip()) is not None
    raw = value.strip()
    if all_day:
        try:
            d = datetime.strptime(raw[:8], "%Y%m%d").date()
            return datetime.combine(d, time.min, tzinfo=TZ), True
        except ValueError:
            return None, True
    fmt = "%Y%m%dT%H%M%S" if len(raw.rstrip("Z")) >= 15 else "%Y%m%dT%H%M"
    try:
        dt = datetime.strptime(raw.rstrip("Z"), fmt)
    except ValueError:
        return None, False
    if raw.endswith("Z"):
        return dt.replace(tzinfo=timezone.utc).astimezone(TZ), False
    return dt.replace(tzinfo=TZ), False


def _parse_ical(text_value: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    lines: list[str] = []
    for raw_line in text_value.replace("\r\n", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current:
                start, all_day = _parse_ical_datetime(current.get("DTSTART_KEY", "DTSTART"), current.get("DTSTART", ""))
                end, _ = _parse_ical_datetime(current.get("DTEND_KEY", "DTEND"), current.get("DTEND", "")) if current.get("DTEND") else (None, False)
                description = _unescape_ical(current.get("DESCRIPTION", ""))
                description_url = _standalone_http_url(description)
                raw = {
                    "title": _unescape_ical(current.get("SUMMARY", "")),
                    "starts_at": _iso_local(start),
                    "ends_at": _iso_local(end),
                    "all_day": all_day,
                    "venue": _unescape_ical(current.get("LOCATION", "")),
                    # CivicEngage municipal feeds commonly put the real event-detail
                    # page in DESCRIPTION while URL points back to the calendar feed.
                    "description": "" if description_url else description,
                    "event_url": description_url or _unescape_ical(current.get("URL", "")) or _source_url(source),
                }
                event = _normalize_event(raw, source, window)
                if event:
                    events.append(event)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        base = key.split(";", 1)[0].upper()
        if base in {"DTSTART", "DTEND"}:
            current[base] = value
            current[f"{base}_KEY"] = key
        elif base in {"SUMMARY", "LOCATION", "DESCRIPTION", "URL", "UID"}:
            current[base] = value
    return events


def _jsonld_objects(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict):
        if payload.get("@type") == "Event" or (isinstance(payload.get("@type"), list) and "Event" in payload["@type"]):
            yield payload
        for key in ("@graph", "itemListElement"):
            value = payload.get(key)
            if value:
                yield from _jsonld_objects(value)
        item = payload.get("item")
        if item:
            yield from _jsonld_objects(item)
    elif isinstance(payload, list):
        for item in payload:
            yield from _jsonld_objects(item)


def _jsonld_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    events: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        content = script.string or script.get_text()
        if not content.strip():
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        for obj in _jsonld_objects(payload):
            location = obj.get("location") if isinstance(obj.get("location"), dict) else {}
            address_obj = location.get("address") if isinstance(location.get("address"), dict) else {}
            offers = obj.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if not isinstance(offers, dict):
                offers = {}
            address_parts = [
                address_obj.get("streetAddress"), address_obj.get("addressLocality"),
                address_obj.get("addressRegion"), address_obj.get("postalCode"),
            ]
            price = offers.get("price")
            currency = offers.get("priceCurrency")
            raw = {
                "title": obj.get("name"),
                "starts_at": obj.get("startDate"),
                "ends_at": obj.get("endDate"),
                "venue": location.get("name"),
                "address": ", ".join(_clean(part) for part in address_parts if _clean(part)),
                "city": address_obj.get("addressLocality"),
                "description": obj.get("description"),
                "event_url": obj.get("url"),
                "ticket_url": offers.get("url"),
                "price": (f"{currency} {price}" if price not in (None, "") and currency else price),
            }
            event = _normalize_event(raw, source, window)
            if event:
                events.append(event)
    return events


def _tribe_api_events(payload: dict[str, Any], source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in payload.get("events", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        venue = item.get("venue") if isinstance(item.get("venue"), dict) else {}
        cost = item.get("cost")
        description = BeautifulSoup(str(item.get("description") or ""), "html.parser").get_text(" ", strip=True)
        raw = {
            "title": item.get("title"),
            "starts_at": item.get("start_date_details", {}).get("year") and item.get("start_date") or item.get("start_date"),
            "ends_at": item.get("end_date"),
            "all_day": item.get("all_day", False),
            "venue": venue.get("venue"),
            "address": ", ".join(filter(None, [_clean(venue.get("address")), _clean(venue.get("city")), _clean(venue.get("state")), _clean(venue.get("zip"))])),
            "city": venue.get("city"),
            "description": description,
            "event_url": item.get("url") or item.get("website"),
            "price": cost,
        }
        event = _normalize_event(raw, source, window)
        if event:
            events.append(event)
    return events


def _fetch_tribe(session: requests.Session, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    api_url = _clean(source.get("api_url"))
    if api_url:
        try:
            response = _get(session, api_url, params={
                "per_page": 100,
                "start_date": window.start.date().isoformat(),
                "end_date": window.end.date().isoformat(),
            })
            payload = response.json()
            events = _tribe_api_events(payload, source, window)
            if events:
                return events
        except Exception:
            pass
    response = _get(session, source["url"])
    events = _jsonld_events(response.text, source, window)
    events.extend(_dated_heading_events(response.text, source, window))
    return _dedupe_exact(events)


def _plausible_heading(text_value: str) -> bool:
    cleaned = _clean(text_value)
    if len(cleaned) < 4 or len(cleaned) > 180:
        return False
    lowered = cleaned.lower().strip(" :–—-")
    if lowered in BOILERPLATE_TITLES:
        return False
    if re.match(r"^(?:about|contact|hours|navigation|filter|search|location|details|events? & tickets)$", lowered):
        return False
    return True


def _context_strings(node: Any, before: int = 5, after: int = 14) -> tuple[list[str], list[str]]:
    prior: list[str] = []
    for item in node.find_all_previous(string=True, limit=before):
        cleaned = _clean(item)
        if cleaned:
            prior.append(cleaned)
    prior.reverse()
    following: list[str] = []
    for item in node.find_all_next(string=True, limit=after):
        cleaned = _clean(item)
        if cleaned and cleaned != _clean(node.get_text(" ", strip=True)):
            following.append(cleaned)
    return prior, following


def _find_datetime_in_context(parts: list[str]) -> tuple[datetime | None, str]:
    joined = " | ".join(parts)
    full = FULL_DATE_RE.search(joined)
    if full:
        date_text = full.group(0)
        tail = joined[full.end(): full.end() + 80]
        clock = TIME_RE.search(tail)
        combined = date_text + (" " + clock.group(0) if clock else "")
        return _parse_full_date(combined), combined
    return None, ""


def _dated_heading_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    events: list[dict[str, Any]] = []
    seen_heading_nodes: set[int] = set()
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        title = _clean(heading.get_text(" ", strip=True))
        if not _plausible_heading(title):
            continue
        if id(heading) in seen_heading_nodes:
            continue
        seen_heading_nodes.add(id(heading))
        prior, following = _context_strings(heading)
        start, _ = _find_datetime_in_context(prior[-5:] + [title] + following[:10])
        if not start:
            continue
        # Avoid distant dates borrowed from navigation: require the textual date to be close.
        context = " ".join(prior[-3:] + following[:6])
        if not FULL_DATE_RE.search(context):
            continue
        end: datetime | None = None
        time_range = TIME_RANGE_RE.search(context)
        if time_range:
            start_clock = _parse_clock("".join(filter(None, [time_range.group(1), ":", time_range.group(2) or "00", " ", (time_range.group(3) or time_range.group(6)) + "m"])))
            end_clock = _parse_clock(f"{time_range.group(4)}:{time_range.group(5) or '00'} {time_range.group(6)}m")
            if start_clock:
                start = start.replace(hour=start_clock[0], minute=start_clock[1])
            if end_clock:
                end = start.replace(hour=end_clock[0], minute=end_clock[1])
                if end <= start:
                    end += timedelta(days=1)
        link = heading.find("a", href=True)
        event_url = urljoin(source["url"], link["href"]) if link else _source_url(source)
        parent_text = _clean((heading.parent or heading).get_text(" ", strip=True))
        description = ""
        if parent_text and parent_text != title:
            description = parent_text.replace(title, "", 1)
            description = FULL_DATE_RE.sub("", description, count=1)
        raw = {
            "title": title,
            "starts_at": _iso_local(start),
            "ends_at": _iso_local(end),
            "description": description,
            "event_url": event_url,
        }
        event = _normalize_event(raw, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _squarespace_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    events: list[dict[str, Any]] = []
    # Squarespace event collections normally keep each entry in an article/eventlist block.
    blocks = soup.select("article, .eventlist-event, .eventlist-column-info, .summary-item")
    for block in blocks:
        text_value = _clean(block.get_text(" ", strip=True))
        start = _parse_full_date(text_value)
        if not start:
            continue
        title_node = block.find(["h1", "h2", "h3", "h4"])
        if not title_node:
            continue
        title = _clean(title_node.get_text(" ", strip=True))
        if not _plausible_heading(title):
            continue
        times = list(TIME_RE.finditer(text_value))
        if times:
            clock = _parse_clock(times[0].group(0))
            if clock:
                start = start.replace(hour=clock[0], minute=clock[1])
        end = None
        if len(times) >= 2:
            clock = _parse_clock(times[1].group(0))
            if clock:
                end = start.replace(hour=clock[0], minute=clock[1])
                if end <= start:
                    end += timedelta(days=1)
        link = title_node.find("a", href=True) or block.find("a", href=True)
        event_url = urljoin(source["url"], link["href"]) if link else _source_url(source)
        raw = {
            "title": title,
            "starts_at": _iso_local(start),
            "ends_at": _iso_local(end),
            "description": text_value.replace(title, "", 1),
            "event_url": event_url,
        }
        event = _normalize_event(raw, source, window)
        if event:
            events.append(event)
    if not events:
        events = _dated_heading_events(html_text, source, window)
    return _dedupe_exact(events)


def _terra_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    events: list[dict[str, Any]] = []
    for heading in soup.find_all("h3"):
        title_raw = _clean(heading.get_text(" ", strip=True))
        if "@ Terra Fermata" not in title_raw:
            continue
        title = re.sub(r"\s*@\s*Terra Fermata\s*$", "", title_raw, flags=re.I).strip()
        following = [_clean(x) for x in heading.find_all_next(string=True, limit=18) if _clean(x)]
        context = " | ".join(following[:12])
        month_day = SHORT_DATE_RE.search(context)
        clock = TIME_RE.search(context)
        if not month_day or not clock:
            continue
        start = _parse_short_date(month_day.group(1), month_day.group(2), month_day.group(3), window.now, clock.group(0))
        if not start:
            continue
        details_link = None
        ticket_link = None
        for link in heading.find_all_next("a", href=True, limit=6):
            label = _clean(link.get_text(" ", strip=True)).lower()
            if not details_link and ("detail" in label or "event info" in label):
                details_link = urljoin(source["url"], link["href"])
            if not ticket_link and "ticket" in label:
                ticket_link = urljoin(source["url"], link["href"])
        description = next((part for part in following if len(part) > 8 and not re.match(r"^(?:doors:|\$?\d+(?:\.\d+)?$|more details|buy tickets)", part, re.I) and not TIME_RE.fullmatch(part)), "")
        price = next((part for part in following if "$" in part and len(part) < 180), "")
        raw = {
            "title": title,
            "starts_at": _iso_local(start),
            "description": description,
            "price": price,
            "event_url": details_link or _source_url(source),
            "ticket_url": ticket_link or "",
        }
        event = _normalize_event(raw, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _summer_crush_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    strings = [_clean(x) for x in soup.stripped_strings if _clean(x)]
    events: list[dict[str, Any]] = []
    for idx, value in enumerate(strings):
        if not re.fullmatch(r"(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),\s+"
                            r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+"
                            r"\d{1,2},\s+20\d{2}", value, re.I):
            continue
        start = _parse_full_date(value)
        if not start:
            continue
        chunk = strings[idx + 1: idx + 18]
        title = next((part for part in chunk[:5] if part and not part.lower().startswith(("when", "whats to eat", "description", "click here")) and len(part) > 4), "")
        if not title:
            continue
        time_line = next((part for part in chunk if part.lower().startswith("when")), "")
        range_match = TIME_RANGE_RE.search(time_line)
        end = None
        if range_match:
            first_meridiem = range_match.group(3) or range_match.group(6)
            start_clock = _parse_clock(f"{range_match.group(1)}:{range_match.group(2) or '00'} {first_meridiem}m")
            end_clock = _parse_clock(f"{range_match.group(4)}:{range_match.group(5) or '00'} {range_match.group(6)}m")
            if start_clock:
                start = start.replace(hour=start_clock[0], minute=start_clock[1])
            if end_clock:
                end = start.replace(hour=end_clock[0], minute=end_clock[1])
                if end <= start:
                    end += timedelta(days=1)
        description = ""
        try:
            desc_index = next(i for i, part in enumerate(chunk) if part.lower().startswith("description"))
            if desc_index + 1 < len(chunk):
                description = chunk[desc_index + 1]
        except StopIteration:
            pass
        price = next((part for part in chunk if "$" in part and "ticket" in part.lower()), "")
        raw = {
            "title": title,
            "starts_at": _iso_local(start),
            "ends_at": _iso_local(end),
            "description": description,
            "price": price,
            "event_url": _source_url(source),
        }
        event = _normalize_event(raw, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _capt_hirams_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    text_value = BeautifulSoup(html_text, "html.parser").get_text("\n", strip=True)
    pattern = re.compile(
        r"(?:^|\n)\s*(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+"
        r"(.+?)\s+(\d{2})-(\d{2})-(20\d{2})\s+@\s+(\d{1,2}:\d{2}\s*[AP]M)",
        re.I,
    )
    events: list[dict[str, Any]] = []
    for match in pattern.finditer(text_value):
        title = _clean(match.group(3))
        month = int(match.group(4))
        day = int(match.group(5))
        year = int(match.group(6))
        clock = _parse_clock(match.group(7)) or (0, 0)
        try:
            start = datetime(year, month, day, clock[0], clock[1], tzinfo=TZ)
        except ValueError:
            continue
        event = _normalize_event({"title": title, "starts_at": _iso_local(start), "event_url": _source_url(source)}, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _lyric_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    strings = [_clean(x) for x in soup.stripped_strings if _clean(x)]
    events: list[dict[str, Any]] = []
    date_re = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2}),\s+(20\d{2})\s+at\s+(.+)$", re.I)
    for idx, value in enumerate(strings):
        match = date_re.match(value)
        if not match:
            continue
        start = _parse_short_date(match.group(1), match.group(2), match.group(3), window.now, match.group(4))
        if not start:
            continue
        title = ""
        for prior in reversed(strings[max(0, idx - 5):idx]):
            if prior.lower() in {"details and tickets", "upcoming events"} or prior.lower().endswith("presents"):
                continue
            if _plausible_heading(prior):
                title = prior
                break
        if not title:
            continue
        event = _normalize_event({"title": title, "starts_at": _iso_local(start), "event_url": _source_url(source)}, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _elc_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    strings = [_clean(x) for x in soup.stripped_strings if _clean(x)]
    events: list[dict[str, Any]] = []
    inline = re.compile(r"^(\d{1,2})/(\d{1,2})\s+(.+?)\s+(\d{1,2}(?::\d{2})?\s*[AP]M)(?:\b|$)", re.I)
    for value in strings:
        match = inline.match(value)
        if not match:
            continue
        month, day = int(match.group(1)), int(match.group(2))
        year = _infer_year(month, day, window.now)
        clock = _parse_clock(match.group(4)) or (0, 0)
        start = datetime(year, month, day, clock[0], clock[1], tzinfo=TZ)
        event = _normalize_event({
            "title": match.group(3), "starts_at": _iso_local(start), "event_url": _source_url(source)
        }, source, window)
        if event:
            events.append(event)
    # Also accept richer standalone pages or future layout changes.
    events.extend(_jsonld_events(html_text, source, window))
    return _dedupe_exact(events)


def _martinarts_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    """Parse the MartinArts cultural calendar without depending on its presentation markup.

    The calendar exposes a full-date heading followed by individual event rows in the form
    ``Title 7:30 pm - 9:00 pm``.  Reading stripped strings makes the adapter resilient to
    table/list layout changes while still requiring an explicit date and time for every row.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    strings = [_clean(x) for x in soup.stripped_strings if _clean(x)]
    current_day: date | None = None
    events: list[dict[str, Any]] = []
    event_line = re.compile(
        r"^(.+?)\s+(\d{1,2}(?::\d{2})?\s*[ap]m)\s*(?:-|–|—|to)\s*"
        r"(\d{1,2}(?::\d{2})?\s*[ap]m)$",
        re.I,
    )
    for value in strings:
        full = FULL_DATE_RE.fullmatch(value)
        if full:
            parsed = _parse_full_date(value)
            current_day = parsed.date() if parsed else None
            continue
        if current_day is None:
            continue
        match = event_line.match(value)
        if not match:
            continue
        title = _clean(match.group(1))
        start_clock = _parse_clock(match.group(2))
        end_clock = _parse_clock(match.group(3))
        if not start_clock:
            continue
        start = datetime.combine(current_day, time(*start_clock), tzinfo=TZ)
        end = datetime.combine(current_day, time(*(end_clock or start_clock)), tzinfo=TZ) if end_clock else None
        if end and end <= start:
            end += timedelta(days=1)
        event = _normalize_event({
            "title": title,
            "starts_at": _iso_local(start),
            "ends_at": _iso_local(end),
            "event_url": _source_url(source),
        }, source, window)
        if event:
            events.append(event)
    # Some individual event cards carry structured data; merge those if present.
    events.extend(_jsonld_events(html_text, source, window))
    return _dedupe_exact(events)


def _stlucie_county_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    """Parse the county's compact calendar rows such as ``Sep 04 Event 07:00 PM - 09:00 PM``."""
    text_value = _clean(BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True))
    pattern = re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2})\s+"
        r"(.{3,180}?)\s+(\d{1,2}:\d{2}\s*[AP]M)\s*(?:-|–|—|to)\s*"
        r"(\d{1,2}:\d{2}\s*[AP]M)(?=\s|$)",
        re.I,
    )
    events: list[dict[str, Any]] = []
    for match in pattern.finditer(text_value):
        start = _parse_short_date(match.group(1), match.group(2), None, window.now, match.group(4))
        if not start:
            continue
        end_clock = _parse_clock(match.group(5))
        end = start.replace(hour=end_clock[0], minute=end_clock[1]) if end_clock else None
        if end and end <= start:
            end += timedelta(days=1)
        title = re.sub(r"^(?:\d{1,2}:\d{2}\s*[AP]M\s*)+", "", _clean(match.group(3)), flags=re.I)
        event = _normalize_event({
            "title": title,
            "starts_at": _iso_local(start),
            "ends_at": _iso_local(end),
            "event_url": _source_url(source),
        }, source, window)
        if event:
            events.append(event)
    events.extend(_jsonld_events(html_text, source, window))
    return _dedupe_exact(events)


def _jazz_calendar_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    text_value = BeautifulSoup(html_text, "html.parser").get_text("\n", strip=True)
    pattern = re.compile(
        r"(?:^|\n)\s*([^\n]{3,160})\s*\n\s*Date:\s*"
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2}),\s+(20\d{2}),\s*"
        r"(\d{1,2}:\d{2}\s*[AP]M)\s*(?:to|-|–|—)\s*(\d{1,2}:\d{2}\s*[AP]M)",
        re.I,
    )
    events: list[dict[str, Any]] = []
    for match in pattern.finditer(text_value):
        start = _parse_short_date(match.group(2), match.group(3), match.group(4), window.now, match.group(5))
        if not start:
            continue
        end_clock = _parse_clock(match.group(6))
        end = start.replace(hour=end_clock[0], minute=end_clock[1]) if end_clock else None
        if end and end <= start:
            end += timedelta(days=1)
        event = _normalize_event({
            "title": match.group(1),
            "starts_at": _iso_local(start),
            "ends_at": _iso_local(end),
            "event_url": _source_url(source),
        }, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _ticketing_performances(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    """Best-effort adapter for an official theatre ticketing page with repeated performance dates."""
    soup = BeautifulSoup(html_text, "html.parser")
    strings = [_clean(x) for x in soup.stripped_strings if _clean(x)]
    date_re = re.compile(
        r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),\s+(20\d{2})\s+(\d{1,2}:\d{2}\s*[AP]M)$",
        re.I,
    )
    events: list[dict[str, Any]] = []
    for idx, value in enumerate(strings):
        match = date_re.match(value)
        if not match:
            continue
        start = _parse_short_date(match.group(1), match.group(2), match.group(3), window.now, match.group(4))
        if not start:
            continue
        title = ""
        for prior in reversed(strings[max(0, idx - 18):idx]):
            low = prior.lower()
            if low in {"get tickets", "sold out", "join waitlist", "order now", "26/27 mainstage"}:
                continue
            if re.fullmatch(r"\$?\d+(?:\.\d+)?\s*(?:-\s*\$?\d+(?:\.\d+)?)?", prior):
                continue
            if _plausible_heading(prior) and not FULL_DATE_RE.search(prior):
                title = prior
                break
        if not title:
            continue
        event = _normalize_event({
            "title": title,
            "starts_at": _iso_local(start),
            "event_url": _source_url(source),
        }, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _pineapple_show_page_events(
    html_text: str, source: dict[str, Any], window: Window, detail_url: str
) -> list[dict[str, Any]]:
    """Parse every performance from one official Pineapple Playhouse show page."""
    soup = BeautifulSoup(html_text, "html.parser")
    title_node = soup.find("h1")
    title = _clean(title_node.get_text(" ", strip=True)) if title_node else ""
    if not _plausible_heading(title):
        return []
    ticket_url = ""
    for anchor in soup.find_all("a", href=True):
        if "buy tickets" in _clean(anchor.get_text(" ", strip=True)).lower():
            ticket_url = urljoin(detail_url, anchor["href"])
            break
    description = ""
    details_heading = soup.find(lambda tag: getattr(tag, "name", None) in {"h2", "h3", "h4"} and "show details" in _clean(tag.get_text(" ", strip=True)).lower())
    if details_heading:
        for sibling in details_heading.find_all_next(["p", "div"], limit=6):
            candidate = _clean(sibling.get_text(" ", strip=True))
            if candidate and candidate.lower() not in {"buy tickets", "show details"} and not FULL_DATE_RE.search(candidate):
                description = candidate
                break
    text_value = soup.get_text("\n", strip=True)
    performance_re = re.compile(
        r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+)?"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\s+(\d{1,2})(?::(\d{2}))?\s*([AP])\.?M?\.?",
        re.I,
    )
    events: list[dict[str, Any]] = []
    for match in performance_re.finditer(text_value):
        start = _parse_short_date(
            match.group(1), match.group(2), match.group(3), window.now,
            f"{match.group(4)}:{match.group(5) or '00'} {match.group(6)}M",
        )
        if not start:
            continue
        event = _normalize_event({
            "title": title, "starts_at": _iso_local(start), "description": description,
            "event_url": detail_url, "ticket_url": ticket_url,
        }, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _pineapple_events(
    session: requests.Session, html_text: str, source: dict[str, Any], window: Window
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    base_host = urlparse(source["url"]).netloc.lower()
    detail_urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        url = urljoin(source["url"], anchor["href"])
        parsed = urlparse(url)
        if parsed.netloc.lower() != base_host or "/seasonal-shows/" not in parsed.path:
            continue
        canonical = parsed._replace(query="", fragment="").geturl()
        if canonical not in detail_urls:
            detail_urls.append(canonical)
    detail_urls = detail_urls[:20]
    if not detail_urls:
        raise EventSourceError("official season page exposed no seasonal-show links")
    events: list[dict[str, Any]] = []
    fetched_pages = 0
    for detail_url in detail_urls:
        try:
            response = _get(session, detail_url)
            fetched_pages += 1
            events.extend(_pineapple_show_page_events(response.text, source, window, detail_url))
        except Exception:
            continue
    if fetched_pages == 0:
        raise EventSourceError("all official Pineapple show detail pages failed")
    return _dedupe_exact(events)


def _opera_schedule_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    """Parse Vero Beach Opera mainstage, competition, MET Live and encore dates."""
    soup = BeautifulSoup(html_text, "html.parser")
    strings = [_clean(value) for value in soup.stripped_strings if _clean(value)]
    events: list[dict[str, Any]] = []
    in_met = False
    for idx, value in enumerate(strings):
        low = value.lower()
        if low == "met live in hd":
            in_met = True
            continue
        if in_met and low in {"prizes", "watch videos", "past operas"}:
            in_met = False
        match = FULL_DATE_RE.search(value)
        if not match or not TIME_RE.search(value):
            continue
        start = _parse_full_date(value)
        if not start:
            continue
        suffix = _clean(value[match.end():])
        # Remove the leading time expression and punctuation before a transmission title.
        time_match = TIME_RE.search(suffix)
        if time_match:
            suffix = _clean(suffix[time_match.end():]).lstrip(":-–— ")
        title = ""
        venue = source.get("venue", "")
        address = source.get("address", "")
        if suffix and len(suffix) >= 4:
            title = suffix
        else:
            prior = strings[max(0, idx - 8):idx]
            role = ""
            for candidate in reversed(prior):
                c_low = candidate.lower()
                if c_low in {"semifinals", "finals", "awards concert"}:
                    role = candidate.title()
                    continue
                if c_low in {"tickets:", "members only:", "general public tickets", "priority seating"}:
                    continue
                if re.search(r"\b(?:tickets?|on sale|members?|advance|priority seating|performing arts center)\b", c_low):
                    continue
                if _plausible_heading(candidate) and not FULL_DATE_RE.search(candidate):
                    title = candidate
                    break
            if role:
                if "rising stars" in title.lower():
                    title = f"{title} — {role}"
                else:
                    title = f"Rising Stars Competition — {role}"
        if in_met:
            venue = _clean(source.get("met_venue") or "The Majestic 11")
            address = _clean(source.get("met_address"))
            if not title:
                title = "MET Live in HD"
        if not title:
            continue
        event = _normalize_event({
            "title": title, "starts_at": _iso_local(start), "venue": venue, "address": address,
            "event_url": _source_url(source),
        }, source, window)
        if event:
            events.append(event)
    return _dedupe_exact(events)


def _recurring_events(html_text: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    page_text = _clean(BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True))
    events: list[dict[str, Any]] = []
    for rule in source.get("recurring", []):
        evidence = _clean(rule.get("evidence"))
        if evidence and evidence.lower() not in page_text.lower():
            continue
        weekday = int(rule["weekday"])
        cursor = window.start.date()
        while cursor.weekday() != weekday:
            cursor += timedelta(days=1)
        while cursor < window.end.date():
            start_clock = tuple(int(x) for x in str(rule.get("time", "00:00")).split(":", 1))
            start = datetime.combine(cursor, time(start_clock[0], start_clock[1]), tzinfo=TZ)
            end = None
            if rule.get("end_time"):
                end_clock = tuple(int(x) for x in str(rule["end_time"]).split(":", 1))
                end = datetime.combine(cursor, time(end_clock[0], end_clock[1]), tzinfo=TZ)
                if end <= start:
                    end += timedelta(days=1)
            event = _normalize_event({
                "title": rule["title"], "starts_at": _iso_local(start), "ends_at": _iso_local(end),
                "category": rule.get("category"), "event_url": _source_url(source),
            }, source, window)
            if event:
                events.append(event)
            cursor += timedelta(days=7)
    return events


def _fetch_source(session: requests.Session, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    adapter = source.get("adapter")
    if adapter == "ical":
        response = _get(session, source["url"])
        return _parse_ical(response.text, source, window)
    if adapter == "tribe":
        events = _fetch_tribe(session, source, window)
        if source.get("recurring"):
            response = _get(session, source["url"])
            events.extend(_recurring_events(response.text, source, window))
        return _dedupe_exact(events)
    if adapter == "pineapple_linked_shows":
        response = _get(session, source["url"])
        return _pineapple_events(session, response.text, source, window)

    response = _get(session, source["url"])
    html_text = response.text
    parsers = {
        "jsonld": lambda: _jsonld_events(html_text, source, window),
        "dated_headings": lambda: _dedupe_exact(_jsonld_events(html_text, source, window) + _dated_heading_events(html_text, source, window)),
        "squarespace_events": lambda: _dedupe_exact(_jsonld_events(html_text, source, window) + _squarespace_events(html_text, source, window)),
        "terra_fermata": lambda: _terra_events(html_text, source, window),
        "summer_crush": lambda: _summer_crush_events(html_text, source, window),
        "capt_hirams": lambda: _capt_hirams_events(html_text, source, window),
        "lyric": lambda: _lyric_events(html_text, source, window),
        "elc_monthly": lambda: _elc_events(html_text, source, window),
        "martinarts_calendar": lambda: _martinarts_events(html_text, source, window),
        "stlucie_county_calendar": lambda: _stlucie_county_events(html_text, source, window),
        "jazz_calendar": lambda: _jazz_calendar_events(html_text, source, window),
        "ticketing_performances": lambda: _ticketing_performances(html_text, source, window),
        "opera_schedule": lambda: _opera_schedule_events(html_text, source, window),
        "recurring_page": lambda: _recurring_events(html_text, source, window),
    }
    if adapter not in parsers:
        raise EventSourceError(f"Unknown adapter {adapter!r} for {source.get('id')}")
    events = parsers[adapter]()
    if source.get("recurring") and adapter != "recurring_page":
        events.extend(_recurring_events(html_text, source, window))
    return _dedupe_exact(events)


def _dedupe_exact(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        key = (
            _slug_text(event.get("title", "")),
            str(event.get("starts_at", ""))[:16],
            _slug_text(event.get("venue", "") or event.get("city", "")),
        )
        if key not in out:
            out[key] = event
    return list(out.values())


def _dedupe_cross_source(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from difflib import SequenceMatcher

    ordered = sorted(events, key=lambda e: (e["starts_at"], int(e.get("source_priority", 50)), e["title"]))
    kept: list[dict[str, Any]] = []
    for event in ordered:
        start_day = event["starts_at"][:10]
        title_key = _slug_text(re.sub(r"\b(?:at|@)\s+.+$", "", event["title"], flags=re.I))
        merged_into = None
        for existing in reversed(kept):
            if existing["starts_at"][:10] != start_day:
                if existing["starts_at"][:10] < start_day:
                    break
                continue
            existing_key = _slug_text(re.sub(r"\b(?:at|@)\s+.+$", "", existing["title"], flags=re.I))
            ratio = SequenceMatcher(None, title_key, existing_key).ratio()
            venue_match = bool(_slug_text(event.get("venue", "")) and _slug_text(event.get("venue", "")) == _slug_text(existing.get("venue", "")))
            city_match = event.get("city") and event.get("city") == existing.get("city")
            event_start = _parse_iso_datetime(event.get("starts_at"))
            existing_start = _parse_iso_datetime(existing.get("starts_at"))
            time_match = bool(
                event_start and existing_start
                and abs(event_start - existing_start) <= timedelta(minutes=45)
            )
            if event.get("all_day") or existing.get("all_day"):
                time_match = True
            if ratio >= 0.91 and time_match and (venue_match or city_match or ratio >= 0.97):
                merged_into = existing
                break
        if merged_into is None:
            kept.append(event)
            continue
        if int(event.get("source_priority", 50)) < int(merged_into.get("source_priority", 50)):
            preferred, other = event, merged_into.copy()
            merged_into.clear()
            merged_into.update(preferred)
        else:
            other = event
        for field in ("description", "price", "ticket_url", "venue", "address", "city"):
            if not merged_into.get(field) and other.get(field):
                merged_into[field] = other[field]
        sources = set(merged_into.get("also_listed_by", []))
        sources.add(other.get("source_name", ""))
        sources.discard(merged_into.get("source_name", ""))
        sources.discard("")
        if sources:
            merged_into["also_listed_by"] = sorted(sources)
    for event in kept:
        event["id"] = _event_id(event)
    return sorted(kept, key=lambda e: (e["starts_at"], e["title"].lower()))


def _cached_source_events(cache: dict[str, Any], source_id: str, source: dict[str, Any], window: Window) -> list[dict[str, Any]]:
    entry = cache.get("sources", {}).get(source_id, {})
    events: list[dict[str, Any]] = []
    for raw in entry.get("events", []):
        if not isinstance(raw, dict):
            continue
        # Cached rows already have normalized source metadata; still revalidate dates,
        # locality, and URL authority. Older CivicEngage cache rows may contain the
        # same relative feed links that caused the live TCT-link regression.
        cached_raw = dict(raw)
        description_url = _standalone_http_url(cached_raw.get("description"))
        if source.get("adapter") == "ical" and description_url:
            cached_raw["event_url"] = description_url
            cached_raw["description"] = ""
        event = _normalize_event(cached_raw, source, window)
        if event:
            # Preserve authoritative descriptive fields from cache, but never restore
            # raw URL strings after _normalize_event has made them absolute.
            for field in ("description", "price", "venue", "address", "city", "category"):
                if cached_raw.get(field):
                    event[field] = cached_raw[field]
            events.append(event)
    return events


def _cache_write_source(cache: dict[str, Any], source: dict[str, Any], events: list[dict[str, Any]], fetched_at: str) -> None:
    cache.setdefault("schema_version", SCHEMA_VERSION)
    sources = cache.setdefault("sources", {})
    prior = sources.get(source["id"], {}) if isinstance(sources.get(source["id"]), dict) else {}
    # Keep the cache content-stable when a successful refresh returned identical data.
    # This avoids eight timestamp-only commits per day from the scheduled updater.
    if prior.get("events") == events and prior.get("source_url") == _source_url(source):
        return
    sources[source["id"]] = {
        "fetched_at": fetched_at,
        "source_url": _source_url(source),
        "event_count": len(events),
        "events": events,
    }


def _stable_generated_at(path: Path, events_or_sources: Any, fresh_at: str, key: str) -> str:
    """Preserve a prior content timestamp when the material payload did not change."""
    prior = _load_json(path, {})
    if isinstance(prior, dict) and prior.get(key) == events_or_sources and prior.get("generated_at"):
        return str(prior["generated_at"])
    return fresh_at


def _date_label(dt: datetime) -> tuple[str, str, str]:
    return dt.strftime("%a").upper(), dt.strftime("%b").upper(), str(dt.day)


def _format_time(event: dict[str, Any]) -> str:
    if event.get("all_day"):
        return "All day"
    start = _parse_iso_datetime(event.get("starts_at"))
    end = _parse_iso_datetime(event.get("ends_at"))
    if not start:
        return ""
    start_text = start.strftime("%-I:%M %p").replace(":00 ", " ")
    if not end or end.date() != start.date():
        return start_text
    end_text = end.strftime("%-I:%M %p").replace(":00 ", " ")
    return f"{start_text}–{end_text}"


def _render_card(event: dict[str, Any]) -> str:
    start = _parse_iso_datetime(event["starts_at"]) or _now_local()
    weekday, month, day = _date_label(start)
    esc = html_lib.escape
    venue_parts = [event.get("venue"), event.get("city")]
    location = " · ".join(_clean(x) for x in venue_parts if _clean(x))
    if not location:
        location = event.get("county", "") + " County"
    description = event.get("description", "")
    price = event.get("price", "")
    details_url = event.get("event_url") or event.get("source_url") or "#"
    ticket_url = event.get("ticket_url") or ""
    secondary = ""
    if ticket_url and ticket_url != details_url:
        secondary = f'<a class="event-ticket" href="{esc(ticket_url, quote=True)}" target="_blank" rel="noopener noreferrer external">Tickets</a>'
    description_html = f'<p class="event-desc">{esc(description)}</p>' if description else ""
    price_html = f'<span class="event-price">{esc(price)}</span>' if price else ""
    return f'''<article class="event-card" data-event-id="{esc(event['id'])}" data-county="{esc(event['county'])}" data-category="{esc(event['category'])}" data-date="{esc(start.date().isoformat())}">
  <div class="event-datebox" aria-label="{esc(start.strftime('%A, %B %-d, %Y'))}"><span>{weekday}</span><strong>{month} {day}</strong></div>
  <div class="event-card-body">
    <div class="event-card-meta"><span class="event-category">{esc(event['category'])}</span>{price_html}</div>
    <h2 class="event-title"><a href="{esc(details_url, quote=True)}" target="_blank" rel="noopener noreferrer external">{esc(event['title'])}</a></h2>
    <p class="event-whenwhere"><strong>{esc(_format_time(event))}</strong>{' · ' if _format_time(event) and location else ''}{esc(location)}</p>
    {description_html}
    <div class="event-card-footer"><span>Source: <a href="{esc(event['source_url'], quote=True)}" target="_blank" rel="noopener noreferrer external">{esc(event['source_name'])}</a></span><div class="event-actions"><a href="{esc(details_url, quote=True)}" target="_blank" rel="noopener noreferrer external">Event details →</a>{secondary}</div></div>
  </div>
</article>'''


def _render_dynamic(events: list[dict[str, Any]], status: dict[str, Any]) -> str:
    generated = _parse_iso_datetime(status.get("generated_at"))
    updated = generated.strftime("%b %-d, %Y at %-I:%M %p") if generated else "not yet"
    initial_events = events[:INITIAL_EVENT_ROWS]
    cards = "\n".join(_render_card(event) for event in initial_events)
    if not cards:
        cards = '''<div class="events-empty events-empty--initial"><strong>The calendar is refreshing.</strong><span>We couldn't load a current event listing yet. Check back shortly.</span></div>'''
    visible_count = min(len(events), INITIAL_EVENT_ROWS)
    remaining = max(0, len(events) - visible_count)
    next_count = min(INITIAL_EVENT_ROWS, remaining)
    more_hidden = " hidden" if remaining == 0 else ""
    more_label = f"View {next_count} more" if next_count else "View more"
    return f'''{DYNAMIC_START}
<section class="events-results" aria-live="polite">
  <div class="events-results-head"><p><strong data-events-count>{len(events)}</strong> upcoming events</p><p class="events-updated">Updated {html_lib.escape(updated)} ET</p></div>
  <div class="events-list" data-events-list>
{cards}
  </div>
  <div class="events-more-wrap" data-events-more-wrap{more_hidden}>
    <button class="events-more" type="button" data-events-more>{html_lib.escape(more_label)}</button>
    <span class="events-showing" data-events-showing>Showing {visible_count} of {len(events)}</span>
  </div>
  <div class="events-empty" data-events-empty hidden><strong>No events match those filters.</strong><span>Try another county, category or date range.</span></div>
</section>
{DYNAMIC_END}'''


def _jsonld_payload(events: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for event in events[:EVENT_JSONLD_ROWS]:
        item: dict[str, Any] = {
            "@type": "Event",
            "name": event["title"],
            "startDate": event["starts_at"],
            "url": event.get("event_url") or event.get("source_url"),
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        }
        if event.get("ends_at"):
            item["endDate"] = event["ends_at"]
        if event.get("description"):
            item["description"] = event["description"]
        if event.get("venue"):
            item["location"] = {
                "@type": "Place",
                "name": event["venue"],
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": event.get("address", ""),
                    "addressLocality": event.get("city", ""),
                    "addressRegion": "FL",
                },
            }
        items.append({"@type": "ListItem", "position": len(items) + 1, "item": item})
    return {"@context": "https://schema.org", "@type": "ItemList", "name": "Treasure Coast Events", "itemListElement": items}


def _replace_between(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end < 0 or end < start:
        raise RuntimeError(f"events.html is missing required marker pair: {start_marker} / {end_marker}")
    end += len(end_marker)
    return text[:start] + replacement + text[end:]


def _render_page(events: list[dict[str, Any]], status: dict[str, Any]) -> None:
    text = EVENTS_HTML_PATH.read_text(encoding="utf-8")
    text = _replace_between(text, DYNAMIC_START, DYNAMIC_END, _render_dynamic(events, status))
    payload = json.dumps(_jsonld_payload(events), ensure_ascii=False, separators=(",", ":"))
    jsonld = f'{JSONLD_START}\n<script type="application/ld+json" data-tct-events-jsonld>{payload}</script>\n{JSONLD_END}'
    text = _replace_between(text, JSONLD_START, JSONLD_END, jsonld)
    _atomic_text(EVENTS_HTML_PATH, text)


def validate_outputs() -> None:
    payload = _load_json(EVENTS_PATH, {})
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("events.json schema_version is invalid")
    events = payload.get("events")
    if not isinstance(events, list):
        raise RuntimeError("events.json events must be a list")
    required = {"id", "title", "starts_at", "county", "category", "source_name", "source_url"}
    prior_start = ""
    ids: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict) or not required.issubset(event):
            raise RuntimeError(f"events.json row {index} is missing required fields")
        if event["county"] not in {"Martin", "St. Lucie", "Indian River"}:
            raise RuntimeError(f"events.json row {index} has invalid county")
        if event["category"] not in CATEGORY_ORDER:
            raise RuntimeError(f"events.json row {index} has invalid category")
        if event["id"] in ids:
            raise RuntimeError(f"events.json has duplicate event id {event['id']}")
        for link_field in ("event_url", "ticket_url"):
            link_value = _clean(event.get(link_field))
            if link_value.startswith("/"):
                raise RuntimeError(
                    f"events.json row {index} has unresolved relative {link_field}: {link_value}"
                )
        ids.add(event["id"])
        if prior_start and event["starts_at"] < prior_start:
            raise RuntimeError("events.json is not chronologically sorted")
        prior_start = event["starts_at"]
    if payload.get("event_count") != len(events):
        raise RuntimeError("events.json event_count does not match events length")
    page = EVENTS_HTML_PATH.read_text(encoding="utf-8")
    for marker in (DYNAMIC_START, DYNAMIC_END, JSONLD_START, JSONLD_END):
        if page.count(marker) != 1:
            raise RuntimeError(f"events.html must contain exactly one {marker}")
    if "Coming Soon" in page or "List your Treasure Coast event for free" in page:
        raise RuntimeError("events.html still contains the retired coming-soon experience")
    page_soup = BeautifulSoup(page, "html.parser")
    rendered_cards = page_soup.select("article.event-card")
    expected_initial = min(len(events), INITIAL_EVENT_ROWS)
    if len(rendered_cards) != expected_initial:
        raise RuntimeError(
            f"events.html must server-render exactly {expected_initial} initial event cards, found {len(rendered_cards)}"
        )
    if len(events) > INITIAL_EVENT_ROWS and page_soup.select_one("[data-events-more]") is None:
        raise RuntimeError("events.html must expose the incremental View more control")
    submit = page_soup.select_one('.events-note a[href^="mailto:hello@treasurecoast.today"]')
    if submit is None or "Submit an event for review" not in page:
        raise RuntimeError("events.html must expose the reviewed event-submission callout")
    footer = page_soup.find("footer")
    if footer is None or len(footer.select('a[href="/feed.xml"]')) != 1:
        raise RuntimeError("events.html must preserve exactly one sitewide RSS footer link")


def refresh(*, offline: bool = False) -> dict[str, Any]:
    config = _load_json(SOURCE_PATH, {})
    if config.get("schema_version") != SCHEMA_VERSION or not isinstance(config.get("sources"), list):
        raise RuntimeError("events-sources.json is invalid")
    lookahead = int(config.get("lookahead_days", 180))
    window = _window(lookahead)
    cache = _load_json(CACHE_PATH, {"schema_version": SCHEMA_VERSION, "sources": {}})
    if not isinstance(cache.get("sources"), dict):
        cache = {"schema_version": SCHEMA_VERSION, "sources": {}}
    session = _session()
    all_events: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    fetched_at = window.now.isoformat(timespec="seconds")

    for source in config["sources"]:
        source_id = _clean(source.get("id"))
        if not source_id:
            raise RuntimeError("Every event source requires an id")
        source_events: list[dict[str, Any]] = []
        status = "failed"
        error = ""
        if not offline:
            try:
                source_events = _fetch_source(session, source, window)
                source_events = sorted(source_events, key=lambda event: (event["starts_at"], event["title"].lower()))
                max_events = max(1, int(source.get("max_events", 150)))
                source_events = source_events[:max_events]
                # A 200 response with a suddenly empty parser result is often a layout change,
                # not proof that an active calendar has no events. If valid future cached rows
                # still exist, keep them and expose the source as cached instead of erasing them.
                if not source_events and _cached_source_events(cache, source_id, source, window):
                    raise EventSourceError("live response parsed zero events while future cached events remain")
                _cache_write_source(cache, source, source_events, fetched_at)
                status = "ok"
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        if offline or status == "failed":
            cached = _cached_source_events(cache, source_id, source, window)
            if cached or source_id in cache.get("sources", {}):
                source_events = cached
                status = "cached"
        all_events.extend(source_events)
        statuses.append({
            "id": source_id,
            "name": source.get("name"),
            "status": status,
            "event_count": len(source_events),
            "url": _source_url(source),
            "error": error if status == "failed" else "",
        })
        print(f"  events: {source_id}: {status} ({len(source_events)} events)" + (f" — {error}" if status == "failed" else ""))

    events = _dedupe_cross_source(all_events)
    stable_status_rows = [{k: item[k] for k in ("id", "name", "status", "event_count", "url", "error")} for item in statuses]
    status_generated_at = _stable_generated_at(STATUS_PATH, stable_status_rows, fetched_at, "sources")
    events_generated_at = _stable_generated_at(EVENTS_PATH, events, fetched_at, "events")
    status_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": status_generated_at,
        "source_count": len(statuses),
        "successful_sources": sum(item["status"] == "ok" for item in statuses),
        "cached_sources": sum(item["status"] == "cached" for item in statuses),
        "failed_sources": sum(item["status"] == "failed" for item in statuses),
        "event_count": len(events),
        "sources": statuses,
    }
    events_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": events_generated_at,
        "timezone": "America/New_York",
        "event_count": len(events),
        "events": events,
    }
    _atomic_json(CACHE_PATH, cache)
    _atomic_json(EVENTS_PATH, events_payload)
    _atomic_json(STATUS_PATH, status_payload)
    _render_page(events, status_payload)
    validate_outputs()
    print(
        "Events calendar updated: "
        f"{len(events)} events from {status_payload['successful_sources']} live + "
        f"{status_payload['cached_sources']} cached sources; {status_payload['failed_sources']} unavailable."
    )
    return status_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use only last-known-good source cache; perform no HTTP requests.")
    parser.add_argument("--validate-only", action="store_true", help="Validate current events artifacts without fetching or rewriting.")
    args = parser.parse_args(argv)
    if args.validate_only:
        validate_outputs()
        print("Events artifacts validation PASSED")
        return 0
    refresh(offline=args.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
