#!/usr/bin/env python3
"""Refresh and render Treasure Coast missing-persons pages from FDLE.

The source is FDLE's public Missing Endangered Persons Information Clearinghouse
search.  Each county is refreshed independently.  If a county cannot be fully
parsed, its last-known-good records are retained so a partial source failure can
never erase active cases.
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import math
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlparse, urlunparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import build_audience_features as audience

SITE_URL = "https://treasurecoast.today"
SOURCE_HOME = "https://www.fdle.state.fl.us/mcicsearch/Search.asp"
RESULTS_BASE_URL = "https://www.fdle.state.fl.us/MCICSearch/Results.asp"
FDLE_PHONE = "1-888-356-4774"
COUNTIES = ("Martin", "St. Lucie", "Indian River")
COUNTY_SLUG = {"Martin": "martin", "St. Lucie": "st-lucie", "Indian River": "indian-river"}
DATA_PATH = ROOT / "data" / "missing-persons.json"
STATUS_PATH = ROOT / "data" / "missing-persons-source-status.json"
PAGE_PATH = ROOT / "missing-persons.html"
PROFILE_DIR = ROOT / "missing-persons"
IMAGE_DIR = ROOT / "images" / "missing-persons"
USER_AGENT = (
    "TreasureCoastToday-MissingPersons/1.0 "
    "(+https://treasurecoast.today/contact.html; public-service directory)"
)
MAX_RECORDS_PER_COUNTY = 250
FDLE_PAGE_SIZE = 5
REQUEST_DELAY_SECONDS = 0.20


def _now_iso() -> str:
    override = os.environ.get("TCT_MISSING_PERSONS_NOW", "").strip()
    if override:
        dt = datetime.fromisoformat(override.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slugify(value: str) -> str:
    value = value.lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "missing-person"


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def _fetch(session: requests.Session, url: str, *, binary: bool = False):
    last_error = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=25)
            response.raise_for_status()
            time.sleep(REQUEST_DELAY_SECONDS)
            return response.content if binary else response.text
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.0 + attempt)
    raise RuntimeError(f"FDLE request failed for {url}: {last_error}")


def _normalize_name(raw: str) -> str:
    raw = _clean(raw)
    if "," not in raw:
        return raw
    last, first = [part.strip() for part in raw.split(",", 1)]
    return _clean(f"{first} {last}")


def _first_date(text: str) -> str:
    match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    return match.group(1) if match else ""


def _result_window(text: str) -> tuple[int, int, int] | None:
    match = re.search(
        r"Displaying\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)\s+record",
        text,
        re.I,
    )
    if match:
        return tuple(int(match.group(i)) for i in range(1, 4))
    return None


def _result_total(text: str) -> int | None:
    window = _result_window(text)
    if window:
        return window[2]
    if re.search(r"\b0\s+record", text, re.I) or re.search(r"no\s+(?:matching\s+)?records", text, re.I):
        return 0
    return None


def _normalized_county(value: str) -> str:
    value = _clean(value).lower().replace("saint", "st")
    return re.sub(r"[^a-z0-9]+", "", value)


def _result_county(text: str) -> str:
    match = re.search(r"You\s+Searched\s+For:\s*County:\s*['\"]([^'\"]+)['\"]", text, re.I)
    return _clean(match.group(1)) if match else ""


def _county_results_url(county: str, page: int = 1) -> str:
    # FDLE's own pagination links carry the complete query state.  Supplying
    # those blank criteria explicitly avoids inheriting an unrelated server-side
    # search state and makes every county request self-contained.
    params = {
        "From": "QR",
        "Rvw": "Original",
        "agef": "",
        "aget": "",
        "cat": "",
        "cit": "",
        "cou": county,
        "cp": "1",
        "ep": str(FDLE_PAGE_SIZE),
        "fn": "",
        "ln": "",
        "rce": "",
        "rgn": "",
        "sp": "1",
        "sx": "",
    }
    if page > 1:
        params["Page"] = str(page)
        params["Pclick"] = "1"
    return RESULTS_BASE_URL + "?" + urlencode(params)

def _county_entry_urls(county: str) -> list[str]:
    # Keep both FDLE-supported entry shapes.  The short QR URL is the form used
    # by FDLE's public indexed results, while the explicit URL clears every
    # other search field.  Unioning them prevents a transient/session-specific
    # query state from collapsing a county to an incomplete first-page result.
    short = f"{RESULTS_BASE_URL}?From=QR&cou={quote_plus(county)}"
    explicit = _county_results_url(county)
    return list(dict.fromkeys([short, explicit]))


def _extract_flyer_url(node, base_url: str) -> tuple[str, str]:
    """Return (flyer_url, record_id) from row/link HTML when available."""
    raw = html_lib.unescape(str(node))
    flyer = ""
    record_id = ""

    # Normal links and JavaScript strings used by different generations of MEPIC.
    patterns = [
        r"((?:https?://[^\"'<>\s]+)?/?(?:MCICSearch/)?Flyers/Flyer[A-Za-z0-9_-]*\.asp\?[^\"'<>\s]+)",
        r"((?:\.\./)?Flyers/Flyer[A-Za-z0-9_-]*\.asp\?[^\"'<>\s]+)",
        r"(Flyer[A-Za-z0-9_-]*\.asp\?[^\"'<>\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            found = match.group(1).replace("&amp;", "&")
            lowered = found.lower()
            if lowered.startswith("flyer") and not lowered.startswith("flyers/"):
                found = "Flyers/" + found
            flyer = urljoin(base_url, found)
            break

    source_for_id = flyer or raw
    match = re.search(r"(?:[?&]|\b)ID=(\d+)", source_for_id, re.I)
    if match:
        record_id = match.group(1)
    return flyer, record_id


def _candidate_result_rows(soup: BeautifulSoup) -> list:
    """Return likely record rows, anchored to the FDLE flyer/photo cells first."""
    rows = []
    seen: set[int] = set()

    for img in soup.find_all("img", src=True):
        alt = _clean(img.get("alt", "")).lower()
        src = _clean(img.get("src", "")).lower()
        if "click to view flyer" not in alt and "getimage.asp" not in src:
            continue
        row = img.find_parent("tr")
        while row is not None:
            direct_cells = row.find_all("td", recursive=False)
            if len(direct_cells) >= 7:
                break
            row = row.find_parent("tr")
        if row is not None and id(row) not in seen:
            seen.add(id(row)); rows.append(row)

    # Keep a structural fallback for FDLE markup variants where the thumbnail
    # is background/JS driven rather than a normal <img>.
    for row in soup.find_all("tr"):
        direct_cells = row.find_all("td", recursive=False)
        row_text = _clean(row.get_text(" ", strip=True))
        if len(direct_cells) >= 7 and _first_date(row_text) and id(row) not in seen:
            seen.add(id(row)); rows.append(row)
    return rows


def _parse_result_rows(html: str, page_url: str, county: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for row in _candidate_result_rows(soup):
        direct = row.find_all("td", recursive=False)
        cells = [_clean(cell.get_text(" ", strip=True)) for cell in direct]
        if len(cells) < 7:
            cells = [_clean(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
        if len(cells) < 7:
            continue

        date_idx = next((i for i, value in enumerate(cells) if _first_date(value)), None)
        if date_idx is None or date_idx + 6 >= len(cells):
            continue
        missing_since = _first_date(cells[date_idx])
        raw_name = cells[date_idx + 1]
        race_sex = cells[date_idx + 2]
        age_today = cells[date_idx + 3]
        age_missing = cells[date_idx + 4]
        category = cells[date_idx + 5]
        missing_from = cells[date_idx + 6]
        if not missing_since or not raw_name or not missing_from:
            continue

        race_match = re.search(r"Race:\s*(.*?)(?=\s+Sex:|$)", race_sex, re.I)
        sex_match = re.search(r"Sex:\s*(.+)$", race_sex, re.I)
        race = _clean(race_match.group(1)) if race_match else ""
        sex = _clean(sex_match.group(1)) if sex_match else ""
        age_today = re.sub(r"^Age:\s*", "", age_today, flags=re.I).strip()

        flyer_url, record_id = _extract_flyer_url(row, page_url)
        image_urls = []
        for img in row.find_all("img", src=True):
            src = urljoin(page_url, img.get("src", ""))
            if "getimage.asp" in src.lower() and "fin=" in src.lower() and src not in image_urls:
                image_urls.append(src)

        key_seed = f"{county}|{raw_name}|{missing_since}".lower()
        key = record_id or hashlib.sha1(key_seed.encode("utf-8")).hexdigest()[:14]
        records.append({
            "record_key": str(key),
            "fdle_id": str(record_id or ""),
            "name": _normalize_name(raw_name),
            "source_name": raw_name,
            "missing_since": missing_since,
            "current_age": age_today,
            "age_missing": age_missing,
            "category": category,
            "missing_from": missing_from,
            "county": county,
            "race": race,
            "sex": sex,
            "source_url": flyer_url,
            "source_images": image_urls,
            "narrative": "",
            "hair": "",
            "eyes": "",
            "height": "",
            "weight": "",
        })
    return records


def _pagination_urls(html: str, page_url: str, county: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for link in soup.find_all("a", href=True):
        href = urljoin(page_url, html_lib.unescape(link["href"]))
        parsed = urlparse(href)
        if not parsed.path.lower().endswith("/results.asp"):
            continue
        query = parse_qs(parsed.query)
        qcounty = _clean((query.get("cou") or [""])[0]).lower()
        if qcounty and qcounty != county.lower():
            continue
        if "Page" not in query and "page" not in {k.lower() for k in query}:
            continue
        if href not in urls:
            urls.append(href)
    return urls


def _candidate_flyers(record_id: str) -> list[str]:
    if not record_id:
        return []
    base = "https://www.fdle.state.fl.us/MCICSearch/Flyers/"
    return [
        f"{base}FlyerCust1pic.asp?ID={record_id}",
        f"{base}FlyerCust2pic.asp?ID={record_id}",
        f"{base}FlyerCust.asp?ID={record_id}",
        f"{base}Flyer2PicCAP.asp?ID={record_id}",
    ]


def _field_from_text(text: str, label: str, next_labels: Iterable[str]) -> str:
    next_part = "|".join(re.escape(x) for x in next_labels)
    pattern = rf"\b{re.escape(label)}\s*:?\s*(.*?)(?=\s+(?:{next_part})\s*:|$)"
    match = re.search(pattern, text, re.I)
    return _clean(match.group(1)) if match else ""


def _parse_flyer(html: str, url: str, record: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    text = _clean(soup.get_text(" ", strip=True))
    if record.get("name"):
        last = record["name"].split()[-1].lower()
        if last not in text.lower() and "MISSING" not in text.upper():
            raise RuntimeError("flyer did not match expected missing-person record")

    record = dict(record)
    record["source_url"] = url
    all_images = list(record.get("source_images") or [])
    for img in soup.find_all("img", src=True):
        src = urljoin(url, img.get("src", ""))
        if "GetImage.asp" in src and "FIN=" in src and src not in all_images:
            all_images.append(src)
    record["source_images"] = all_images

    # Prefer row data when present; supplement it with detail-page fields.
    labels = ["SEX", "HAIR", "EYES", "HEIGHT", "WEIGHT", "RACE", "FROM", "COUNTY", "NARRATIVE"]
    for target, label in (("sex", "SEX"), ("hair", "HAIR"), ("eyes", "EYES"),
                          ("height", "HEIGHT"), ("weight", "WEIGHT"), ("race", "RACE")):
        value = _field_from_text(text, label, labels)
        if value and not record.get(target):
            record[target] = value

    narrative = ""
    match = re.search(
        r"NARRATIVE:\s*(.*?)(?=\s+FDLE\s+MISSING|\s+If you have any information|$)",
        text,
        re.I,
    )
    if match:
        narrative = _clean(match.group(1))
    record["narrative"] = narrative

    contact = ""
    match = re.search(r"If you have any information.*?please contact\s+(.*)$", text, re.I)
    if match:
        contact = _clean(match.group(1))
        contact = re.sub(r"^FDLE\s+or\s+the\s+", "", contact, flags=re.I)
        contact = re.sub(r"\s+or the Missing Endangered Persons Information Clearinghouse.*$", "", contact, flags=re.I)
    record["agency_contact"] = contact[:300]
    return record


def _enrich_record(session: requests.Session, record: dict) -> dict:
    candidates = []
    if record.get("source_url"):
        candidates.append(record["source_url"])
    for url in _candidate_flyers(record.get("fdle_id", "")):
        if url not in candidates:
            candidates.append(url)
    for url in candidates[:5]:
        try:
            html = _fetch(session, url)
            if "NARRATIVE" not in html.upper() and "MISSING" not in html.upper():
                continue
            return _parse_flyer(html, url, record)
        except Exception:
            continue
    return record


def scrape_county(session: requests.Session, county: str) -> tuple[list[dict], dict]:
    queue = _county_entry_urls(county)
    seen_pages: set[str] = set()
    synthetic_pages_queued: set[int] = set()
    by_key: dict[str, dict] = {}
    expected_total: int | None = None
    page_size = FDLE_PAGE_SIZE

    while queue and len(seen_pages) < 60:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        html = _fetch(session, url)
        seen_pages.add(url)
        page_text = _clean(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))

        reported_county = _result_county(page_text)
        if reported_county and _normalized_county(reported_county) != _normalized_county(county):
            # Try the alternate self-contained entry URL rather than accepting
            # or publishing data from a different county.
            continue

        window = _result_window(page_text)
        total = _result_total(page_text)
        if total is not None:
            expected_total = total if expected_total is None else max(expected_total, total)
        if window and window[1] >= window[0]:
            page_size = max(page_size, window[1] - window[0] + 1)

        for record in _parse_result_rows(html, url, county):
            by_key[record["record_key"]] = record

        for next_url in _pagination_urls(html, url, county):
            # Keep FDLE's own session-bearing pagination URL even when we have
            # also queued a synthetic fallback for the same page number.
            if next_url not in seen_pages and next_url not in queue:
                queue.append(next_url)

        # FDLE currently exposes five records per page.  Do not depend solely on
        # the visible 1-5 / >> pagination controls: once the source tells us the
        # verified total, explicitly queue every remaining page.
        if expected_total is not None and expected_total > 0:
            total_pages = max(1, math.ceil(expected_total / max(1, page_size)))
            for page_number in range(2, total_pages + 1):
                if page_number in synthetic_pages_queued:
                    continue
                candidate = _county_results_url(county, page_number)
                synthetic_pages_queued.add(page_number)
                if candidate not in seen_pages and candidate not in queue:
                    queue.append(candidate)

        if expected_total is not None and len(by_key) >= expected_total:
            break
        if expected_total is not None and expected_total > MAX_RECORDS_PER_COUNTY:
            raise RuntimeError(f"suspicious FDLE count for {county}: {expected_total}")

    if expected_total is None:
        raise RuntimeError(f"FDLE result total could not be verified for {county}")
    if len(by_key) != expected_total:
        raise RuntimeError(
            f"incomplete FDLE result set for {county}: expected {expected_total}, parsed {len(by_key)}"
        )

    enriched = [_enrich_record(session, record) for record in by_key.values()]
    return enriched, {
        "status": "fresh",
        "expected_records": expected_total,
        "records": len(enriched),
        "pages": len(seen_pages),
        "page_size": page_size,
    }


def _image_extension(content_type: str, data: bytes) -> str:
    ctype = (content_type or "").lower()
    if "png" in ctype or data.startswith(b"\x89PNG"):
        return ".png"
    if "gif" in ctype or data[:6] in {b"GIF87a", b"GIF89a"}:
        return ".gif"
    if "webp" in ctype or (len(data) > 12 and data[8:12] == b"WEBP"):
        return ".webp"
    return ".jpg"


def _download_person_images(session: requests.Session, person: dict, previous: dict | None) -> list[str]:
    source_images = list(dict.fromkeys(person.get("source_images") or []))
    if not source_images:
        return [p for p in (previous or {}).get("images", []) if (ROOT / str(p).lstrip("/")).exists()]

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9_-]+", "-", str(person["record_key"]))
    written: list[str] = []
    for index, url in enumerate(source_images, start=1):
        response = None
        for attempt in range(3):
            try:
                response = session.get(url, timeout=25)
                response.raise_for_status()
                break
            except Exception:
                response = None
                if attempt < 2:
                    time.sleep(0.8 + attempt)
        if response is None:
            continue
        data = response.content
        if len(data) < 300:
            continue
        ext = _image_extension(response.headers.get("Content-Type", ""), data)
        path = IMAGE_DIR / f"{key}-{index}{ext}"
        path.write_bytes(data)
        written.append("/" + path.relative_to(ROOT).as_posix())
        time.sleep(REQUEST_DELAY_SECONDS)

    if written:
        keep = {ROOT / p.lstrip("/") for p in written}
        for old in IMAGE_DIR.glob(f"{key}-*.*"):
            if old not in keep:
                old.unlink(missing_ok=True)
        return written
    return [p for p in (previous or {}).get("images", []) if (ROOT / str(p).lstrip("/")).exists()]


def _detail_url(person: dict, previous: dict | None) -> str:
    if previous and previous.get("detail_url"):
        return str(previous["detail_url"])
    suffix = re.sub(r"[^A-Za-z0-9]+", "", str(person["record_key"]))[:18]
    return f"/missing-persons/{_slugify(person.get('name', 'missing-person'))}-{suffix}.html"


def refresh() -> dict:
    previous_payload = _read_json(DATA_PATH, {})
    previous_people = previous_payload.get("people", []) if isinstance(previous_payload, dict) else []
    previous_by_key = {str(p.get("record_key")): p for p in previous_people if isinstance(p, dict) and p.get("record_key")}
    previous_by_county = {
        county: [p for p in previous_people if isinstance(p, dict) and p.get("county") == county]
        for county in COUNTIES
    }

    session = _session()
    checked_at = _now_iso()
    merged: list[dict] = []
    statuses: dict[str, dict] = {}
    fresh_counties = 0
    for county in COUNTIES:
        prior = previous_by_county[county]
        try:
            people, status = scrape_county(session, county)

            # A parser/source regression should never wipe most of a county's
            # established directory in one run.  Large legitimate removals are
            # rare enough that retaining the last-known-good set for one cycle
            # is safer than publishing an obviously collapsed scrape.
            if prior and len(prior) >= 4:
                drop = len(prior) - len(people)
                if drop >= 3 and len(people) < math.ceil(len(prior) * 0.50):
                    raise RuntimeError(
                        f"suspicious FDLE record-count drop for {county}: "
                        f"previous {len(prior)}, source now {len(people)}"
                    )

            fresh_counties += 1
            status["checked_at"] = checked_at
            statuses[county] = status
        except Exception as exc:
            people = [dict(p) for p in prior]
            statuses[county] = {
                "status": "stale" if people else "unavailable",
                "records": len(people),
                "checked_at": checked_at,
                "error": str(exc)[:500],
            }
        merged.extend(people)

    if fresh_counties == 0 and not previous_people:
        raise RuntimeError("FDLE refresh failed for all three counties and no prior data is available")

    unavailable_without_baseline = [
        county for county in COUNTIES
        if statuses.get(county, {}).get("status") == "unavailable" and not previous_by_county[county]
    ]
    if unavailable_without_baseline:
        raise RuntimeError(
            "FDLE refresh was incomplete and there is no last-known-good baseline for: "
            + ", ".join(unavailable_without_baseline)
            + ". Refusing to publish a partial Treasure Coast directory."
        )

    # Stable URLs and resilient local image copies.
    normalized: list[dict] = []
    for person in merged:
        key = str(person.get("record_key") or "")
        if not key:
            continue
        previous = previous_by_key.get(key)
        person = dict(person)
        person["detail_url"] = _detail_url(person, previous)
        person["images"] = _download_person_images(session, person, previous)
        person["last_checked"] = checked_at
        normalized.append(person)

    def sort_key(person: dict):
        try:
            return datetime.strptime(person.get("missing_since", ""), "%m/%d/%Y")
        except Exception:
            return datetime.min

    normalized.sort(key=sort_key, reverse=True)
    payload = {
        "schema_version": 1,
        "updated_at": checked_at,
        "source": "Florida Department of Law Enforcement",
        "source_url": SOURCE_HOME,
        "counties": list(COUNTIES),
        "count": len(normalized),
        "people": normalized,
    }
    status_payload = {
        "schema_version": 1,
        "checked_at": checked_at,
        "source_url": SOURCE_HOME,
        "counties": statuses,
    }
    _write_json(DATA_PATH, payload)
    _write_json(STATUS_PATH, status_payload)
    return {"people": len(normalized), "fresh_counties": fresh_counties, "status": statuses}


def _format_date(raw: str) -> str:
    try:
        dt = datetime.strptime(raw, "%m/%d/%Y")
        return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    except Exception:
        return raw or "Unknown"


def _format_updated(raw: str) -> str:
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y at %I:%M %p UTC").replace(" 0", " ")
    except Exception:
        return raw


def _chrome_header(active: bool = False) -> str:
    header = audience._page_header()
    if '/missing-persons.html' not in header:
        header = header.replace(
            '<a href="/weather.html" class="nav-section-link">Weather</a>',
            '<a href="/weather.html" class="nav-section-link">Weather</a>\n              '
            '<a href="/missing-persons.html" class="nav-section-link">Missing Persons</a>',
        )
        header = header.replace(
            '<a href="/weather.html" class="mobile-nav-link">Weather</a>',
            '<a href="/weather.html" class="mobile-nav-link">Weather</a>\n          '
            '<a href="/missing-persons.html" class="mobile-nav-link">Missing Persons</a>',
        )
    if active:
        header = header.replace(
            'href="/missing-persons.html" class="nav-section-link"',
            'href="/missing-persons.html" class="nav-section-link active" aria-current="page"',
            1,
        )
        header = header.replace(
            'href="/missing-persons.html" class="mobile-nav-link"',
            'href="/missing-persons.html" class="mobile-nav-link active" aria-current="page"',
            1,
        )
    return header


def _chrome_footer() -> str:
    footer = audience._page_footer()
    if '/missing-persons.html' not in footer:
        footer = footer.replace(
            '<a href="/weather.html">Weather</a>',
            '<a href="/weather.html">Weather</a>\n          <a href="/missing-persons.html">Missing Persons</a>',
            1,
        )
    return footer


def _person_card(person: dict) -> str:
    esc = html_lib.escape
    image = (person.get("images") or [""])[0]
    image_html = (
        f'<img src="{esc(image, quote=True)}" alt="FDLE image of {esc(person.get("name", ""), quote=True)}" loading="lazy">'
        if image else '<div class="missing-person-photo-placeholder" aria-hidden="true">Photo unavailable</div>'
    )
    county_slug = COUNTY_SLUG.get(person.get("county"), "")
    return f'''<article class="missing-person-card" data-county="{esc(county_slug)}">
  <a class="missing-person-card-link" href="{esc(person.get('detail_url',''), quote=True)}">
    <div class="missing-person-card-photo">{image_html}</div>
    <div class="missing-person-card-body">
      <div class="missing-person-card-meta"><span>{esc(person.get('county',''))} County</span><span>{esc(person.get('category','Missing Person'))}</span></div>
      <h2>{esc(person.get('name',''))}</h2>
      <p><strong>Missing since:</strong> {_format_date(person.get('missing_since',''))}</p>
      <p><strong>Missing from:</strong> {esc(person.get('missing_from',''))}</p>
      {f'<p><strong>Age now:</strong> {esc(person.get("current_age",""))}</p>' if person.get('current_age') else ''}
      <span class="missing-person-card-more">View case details →</span>
    </div>
  </a>
</article>'''


def _directory_page(payload: dict, status: dict) -> str:
    people = payload.get("people", [])
    cards = "\n".join(_person_card(person) for person in people)
    stale = [county for county, row in (status.get("counties") or {}).items() if row.get("status") != "fresh"]
    initializing = not payload.get("updated_at") and not (status.get("counties") or {})
    stale_html = ""
    if initializing:
        stale_html = (
            '<div class="missing-person-source-warning"><strong>Directory update in progress:</strong> '
            'TCT is loading the current FDLE listings for Martin, St. Lucie and Indian River counties. '
            'This page will populate automatically after the first successful source update.</div>'
        )
    elif stale:
        stale_html = (
            '<div class="missing-person-source-warning"><strong>Refresh note:</strong> '
            f'FDLE data for {html_lib.escape(", ".join(stale))} could not be fully refreshed. '
            'TCT is showing the last successful listing for that county.</div>'
        )
    count = len(people)
    description = "Current FDLE missing-person records for Martin, St. Lucie and Indian River counties on Florida's Treasure Coast."
    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Missing Persons on the Treasure Coast",
        "description": description,
        "url": f"{SITE_URL}/missing-persons.html",
        "isPartOf": {"@type": "WebSite", "name": "Treasure Coast Today", "url": SITE_URL},
    }
    head = audience._page_head("Missing Persons on the Treasure Coast | Treasure Coast Today", description, "/missing-persons.html", schema)
    empty = '<p class="missing-person-empty">No matching people are currently shown.</p>'
    return f'''<!DOCTYPE html>
<html lang="en"><head>
{head}
</head><body>
{_chrome_header(active=True)}
<main class="missing-persons-page">
  <section class="missing-persons-hero">
    <p class="missing-persons-kicker">Current FDLE listings</p>
    <h1>Missing Persons on the Treasure Coast</h1>
    <p>People currently listed by the Florida Department of Law Enforcement as missing from Martin, St. Lucie or Indian River counties.</p>
    <div class="missing-persons-summary">{('<strong>Directory initializing</strong><span>Waiting for the first FDLE refresh</span>' if initializing else f'<strong>{count}</strong> current FDLE record{"s" if count != 1 else ""}<span>Last checked {_format_updated(payload.get("updated_at",""))}</span>')}</div>
  </section>
  {stale_html}
  <section class="missing-persons-tools" aria-label="Filter missing persons by county">
    <button type="button" class="missing-person-filter active" data-missing-filter="all" aria-pressed="true">All</button>
    <button type="button" class="missing-person-filter" data-missing-filter="martin" aria-pressed="false">Martin</button>
    <button type="button" class="missing-person-filter" data-missing-filter="st-lucie" aria-pressed="false">St. Lucie</button>
    <button type="button" class="missing-person-filter" data-missing-filter="indian-river" aria-pressed="false">Indian River</button>
  </section>
  <section class="missing-persons-grid" data-missing-grid>{cards}</section>
  <div data-missing-empty hidden>{empty}</div>
  <aside class="missing-persons-source-note">
    <h2>Have information?</h2>
    <p>Contact the investigating law-enforcement agency or the FDLE Missing Persons Clearinghouse at <a href="tel:+18883564774">{FDLE_PHONE}</a>. TCT republishes these records as a public service and does not independently determine whether a case remains active.</p>
    <a href="{SOURCE_HOME}" rel="noopener">Search the official FDLE database →</a>
  </aside>
</main>
{_chrome_footer()}
<script>
(function(){{
  const buttons=[...document.querySelectorAll('[data-missing-filter]')];
  const cards=[...document.querySelectorAll('.missing-person-card')];
  const empty=document.querySelector('[data-missing-empty]');
  buttons.forEach(button=>button.addEventListener('click',()=>{{
    const value=button.dataset.missingFilter;
    let shown=0;
    buttons.forEach(b=>{{const on=b===button;b.classList.toggle('active',on);b.setAttribute('aria-pressed',on?'true':'false');}});
    cards.forEach(card=>{{const on=value==='all'||card.dataset.county===value;card.hidden=!on;if(on) shown++;}});
    if(empty) empty.hidden=shown!==0;
  }}));
}})();
</script>
</body></html>'''


def _fact(label: str, value: str) -> str:
    if not value:
        return ""
    return f'<div class="missing-person-fact"><dt>{html_lib.escape(label)}</dt><dd>{html_lib.escape(value)}</dd></div>'


def _profile_page(person: dict, payload: dict) -> str:
    esc = html_lib.escape
    name = person.get("name", "Missing Person")
    detail = person.get("detail_url", "")
    description = (
        f"FDLE missing-person information for {name}, missing from {person.get('missing_from','the Treasure Coast')} "
        f"since {_format_date(person.get('missing_since',''))}."
    )
    schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": f"{name} — Missing Person",
        "description": description,
        "url": f"{SITE_URL}{detail}",
        "about": {"@type": "Person", "name": name},
        "isPartOf": {"@type": "WebSite", "name": "Treasure Coast Today", "url": SITE_URL},
    }
    head = audience._page_head(f"{name} — Missing Person | Treasure Coast Today", description, detail, schema)
    images = person.get("images") or []
    gallery = ""
    if images:
        tiles = []
        for idx, image in enumerate(images):
            label = "FDLE image" if idx == 0 else "Additional or age-progression FDLE image"
            tiles.append(
                f'<figure><img src="{esc(image, quote=True)}" alt="{esc(label + " of " + name, quote=True)}">'
                f'<figcaption>{esc(label)}</figcaption></figure>'
            )
        gallery = '<div class="missing-person-gallery">' + "".join(tiles) + '</div>'
    else:
        gallery = '<div class="missing-person-profile-placeholder">Photo unavailable</div>'

    facts = "".join([
        _fact("Missing since", _format_date(person.get("missing_since", ""))),
        _fact("Missing from", person.get("missing_from", "")),
        _fact("County", f"{person.get('county','')} County" if person.get("county") else ""),
        _fact("Category", person.get("category", "")),
        _fact("Current age", person.get("current_age", "")),
        _fact("Age when missing", person.get("age_missing", "")),
        _fact("Sex", person.get("sex", "")),
        _fact("Race", person.get("race", "")),
        _fact("Hair", person.get("hair", "")),
        _fact("Eyes", person.get("eyes", "")),
        _fact("Height", person.get("height", "")),
        _fact("Weight", person.get("weight", "")),
    ])
    narrative = ""
    if person.get("narrative"):
        narrative = f'''<section class="missing-person-narrative"><h2>FDLE case notes</h2><p>{esc(person['narrative'])}</p></section>'''
    source_url = person.get("source_url") or SOURCE_HOME
    agency = person.get("agency_contact", "")
    agency_html = f'<p class="missing-person-agency"><strong>Investigating agency:</strong> {esc(agency)}</p>' if agency else ""
    return f'''<!DOCTYPE html>
<html lang="en"><head>
{head}
</head><body>
{_chrome_header()}
<main class="missing-person-profile-page">
  <nav class="tct-breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">›</span><a href="/missing-persons.html">Missing Persons</a><span aria-hidden="true">›</span><span aria-current="page">{esc(name)}</span></nav>
  <header class="missing-person-profile-head">
    <p class="missing-persons-kicker">FDLE missing-person record</p>
    <h1>{esc(name)}</h1>
    <p>Missing from <strong>{esc(person.get('missing_from',''))}</strong> since <strong>{esc(_format_date(person.get('missing_since','')))}</strong>.</p>
  </header>
  <div class="missing-person-profile-layout">
    <section>{gallery}</section>
    <section class="missing-person-profile-facts"><h2>Case details</h2><dl>{facts}</dl></section>
  </div>
  {narrative}
  <section class="missing-person-help-card">
    <h2>Have information about {esc(name)}?</h2>
    <p>Contact the investigating law-enforcement agency or call the FDLE Missing Persons Clearinghouse at <a href="tel:+18883564774">{FDLE_PHONE}</a>.</p>
    {agency_html}
    <a class="missing-person-source-button" href="{esc(source_url, quote=True)}" rel="noopener">View the official FDLE record</a>
  </section>
  <p class="missing-person-disclaimer">Source: Florida Department of Law Enforcement. TCT republishes this information as a public service. Case status and identifying details can change; the official FDLE record is authoritative.</p>
</main>
{_chrome_footer()}
</body></html>'''


def _reconcile_profiles(people: list[dict]) -> dict:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    active = {str(person.get("detail_url", "")).lstrip("/") for person in people}
    removed = 0
    for path in PROFILE_DIR.glob("*.html"):
        rel = path.relative_to(ROOT).as_posix()
        if rel not in active:
            path.unlink()
            removed += 1
    written = 0
    payload = _read_json(DATA_PATH, {})
    for person in people:
        rel = str(person.get("detail_url", "")).lstrip("/")
        if not rel:
            continue
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_profile_page(person, payload), encoding="utf-8")
        written += 1
    return {"written": written, "removed": removed}


def _reconcile_stale_images(people: list[dict]) -> int:
    if not IMAGE_DIR.exists():
        return 0
    active_keys = {re.sub(r"[^A-Za-z0-9_-]+", "-", str(p.get("record_key", ""))) for p in people}
    removed = 0
    for path in IMAGE_DIR.iterdir():
        if not path.is_file():
            continue
        stem = path.stem
        if not any(stem.startswith(key + "-") for key in active_keys):
            path.unlink()
            removed += 1
    return removed


def _reconcile_sitemap(people: list[dict], updated_at: str) -> dict:
    path = ROOT / "sitemap.xml"
    if not path.exists():
        return {"added": 0, "removed": 0}
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    tree = ET.parse(path)
    root = tree.getroot()
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    prefix = f"{SITE_URL}/missing-persons/"
    removed = 0
    for node in list(root.findall(f"{ns}url")):
        loc = node.find(f"{ns}loc")
        value = loc.text if loc is not None else ""
        if value and value.startswith(prefix) and value.endswith(".html"):
            root.remove(node)
            removed += 1
    existing = {node.text for node in root.findall(f"{ns}url/{ns}loc") if node.text}
    lastmod = str(updated_at or "")[:10]
    additions = [(f"{SITE_URL}/missing-persons.html", "daily", "0.7", lastmod)]
    additions += [(f"{SITE_URL}{p['detail_url']}", "weekly", "0.5", lastmod) for p in people if p.get("detail_url")]
    added = 0
    for loc, change, priority, lm in additions:
        if loc in existing:
            continue
        node = ET.SubElement(root, f"{ns}url")
        ET.SubElement(node, f"{ns}loc").text = loc
        ET.SubElement(node, f"{ns}changefreq").text = change
        ET.SubElement(node, f"{ns}priority").text = priority
        if lm:
            ET.SubElement(node, f"{ns}lastmod").text = lm
        existing.add(loc)
        added += 1
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return {"added": added, "removed": removed}


def render() -> dict:
    payload = _read_json(DATA_PATH, {})
    status = _read_json(STATUS_PATH, {})
    people = payload.get("people", []) if isinstance(payload, dict) else []
    if not isinstance(people, list):
        raise RuntimeError("data/missing-persons.json people must be a list")
    PAGE_PATH.write_text(_directory_page(payload, status), encoding="utf-8")
    profiles = _reconcile_profiles(people)
    removed_images = _reconcile_stale_images(people)
    sitemap = _reconcile_sitemap(people, payload.get("updated_at", ""))
    return {"people": len(people), "profiles": profiles, "removed_images": removed_images, "sitemap": sitemap}


def validate() -> dict:
    failures: list[str] = []
    payload = _read_json(DATA_PATH, {})
    people = payload.get("people", []) if isinstance(payload, dict) else []
    if not isinstance(people, list):
        raise RuntimeError("Missing-person validation FAILED: people is not a list")
    keys: set[str] = set()
    detail_paths: set[str] = set()
    for person in people:
        key = str(person.get("record_key") or "")
        if not key or key in keys:
            failures.append(f"duplicate/missing record key:{key}")
        keys.add(key)
        if person.get("county") not in COUNTIES:
            failures.append(f"county:{key}")
        for required in ("name", "missing_since", "missing_from", "detail_url"):
            if not person.get(required):
                failures.append(f"{required}:{key}")
        detail = str(person.get("detail_url") or "")
        if detail:
            detail_paths.add(detail)
            path = ROOT / detail.lstrip("/")
            if not path.exists():
                failures.append(f"profile missing:{detail}")
            else:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if f'<link rel="canonical" href="{SITE_URL}{detail}">' not in text:
                    failures.append(f"profile canonical:{detail}")
                if "View the official FDLE record" not in text:
                    failures.append(f"profile source:{detail}")
        for image in person.get("images") or []:
            if not (ROOT / str(image).lstrip("/")).exists():
                failures.append(f"image missing:{image}")
    if not PAGE_PATH.exists():
        failures.append("directory missing")
    else:
        text = PAGE_PATH.read_text(encoding="utf-8", errors="ignore")
        if text.count('class="missing-person-card"') != len(people):
            failures.append("directory card count")
        if "View more" in text or "Load more" in text:
            failures.append("directory pagination")

    sitemap_locs: set[str] = set()
    sitemap = ROOT / "sitemap.xml"
    if sitemap.exists():
        tree = ET.parse(sitemap)
        root = tree.getroot(); ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        sitemap_locs = {node.text for node in root.findall(f"{ns}url/{ns}loc") if node.text}
    if f"{SITE_URL}/missing-persons.html" not in sitemap_locs:
        failures.append("directory sitemap")
    expected_leaf = {f"{SITE_URL}{p}" for p in detail_paths}
    actual_leaf = {loc for loc in sitemap_locs if loc.startswith(f"{SITE_URL}/missing-persons/") and loc.endswith(".html")}
    if actual_leaf != expected_leaf:
        failures.append("profile sitemap reconciliation")

    unmanaged = {"/" + p.relative_to(ROOT).as_posix() for p in PROFILE_DIR.glob("*.html")} - detail_paths if PROFILE_DIR.exists() else set()
    if unmanaged:
        failures.append("stale profile files")
    if failures:
        raise RuntimeError("Missing-person validation FAILED: " + "; ".join(failures[:30]))
    print(f"Missing-person validation PASSED: {len(people)} active profiles")
    return {"people": len(people), "profiles": len(detail_paths)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate(); return
    if not args.render_only:
        result = refresh()
        print("FDLE refresh:", json.dumps(result, ensure_ascii=False))
    render_result = render()
    print("Missing-person render:", json.dumps(render_result, ensure_ascii=False))
    validate()


if __name__ == "__main__":
    main()
