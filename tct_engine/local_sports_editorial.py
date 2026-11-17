"""Editorial sports discovery and publication pacing for Treasure Coast Today.

The target is four to six worthwhile local sports articles per Eastern calendar
week, never four to six compulsory articles. These helpers do not write sports
recaps from scores and do not bypass any existing source/publication safeguards.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SPORTS_EDITORIAL_VERSION = "curated-local-sports-v1-2026-11-17"
SPORTS_WEEKLY_TARGET_LOW = 4
SPORTS_WEEKLY_MAX = 6
SPORTS_PER_RUN_MAX = 2
EASTERN = ZoneInfo("America/New_York")

SPORTS_ASSIGNMENT_RULE = (
    "This beat covers ALL genuinely local competitive sports, not just basketball "
    "or golf. Include boys and girls high school sports in season; Indian River "
    "State College, youth/junior, amateur and local professional teams; and athletes "
    "with a substantial Treasure Coast connection. Favor verified game or meet "
    "outcomes with news value, district/regional/state competition, playoffs, "
    "meaningful rivalries, upsets, records, tournament placements, exceptional "
    "performances, and consequential team/athlete developments. Ordinary local "
    "game recaps are welcome when the result matters and the source establishes "
    "at least two useful supporting facts beyond the final score (such as key "
    "performances, a decisive sequence, verified standings/record impact, or "
    "sourced comments). Never treat one bare box score as a reporting assignment. "
    "Do not publish each game's recap by default. Omit merely routine, repetitive, "
    "commercial, event-listing, national-without-local-connection or poorly sourced "
    "material. Publishing fewer stories is better than filling a quota. Target "
    "four to six worthwhile sports stories per week, subject to real newsworthiness."
)

SPORTS_WRITER_RULE = (
    "For local sports, a concise 150-250-word game recap is preferable when that "
    "is all the sourced detail warrants; do not pad to a generic four-paragraph "
    "350-word article. State the verified teams/athletes, result, date, and "
    "meaningful performance or stakes accurately. Include only verified scorers, "
    "times, records, rankings, and turning points. A final score alone is not "
    "permission to invent a game narrative, quotes, context, or season impact."
)

_GENERIC_SCOREBOARD_TITLE = re.compile(
    r"(?i)\b(?:box[\s-]?score|scoreboard|live[\s-]?scores?|"
    r"game[\s-]?log|weekly[\s-]?schedule|all[\s-]?scores|"
    r"team[\s-]?stats|score[\s-]?updates?)\b"
)
_SCORE_ONLY_TITLE = re.compile(
    r"(?i)^\s*[a-z][a-z0-9 .&'’()-]{2,65}\s+\d{1,3}\s*"
    r"[,;–-]\s*[a-z][a-z0-9 .&'’()-]{2,65}\s+\d{1,3}\s*$"
)
_LISTING_ROUTE = re.compile(
    r"(?i)/(?:scores?|scoreboard|schedule|standings|stats|box-score)(?:/|$)"
)


def _local_date(value):
    """Parse canonical publication receipts conservatively, as Eastern dates."""
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=EASTERN)).astimezone(EASTERN).date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            try:
                return date.fromisoformat(raw[:10])
            except ValueError:
                return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=EASTERN)).astimezone(EASTERN).date()


def sports_weekly_budget(archive, now=None):
    """Count canonical Sports-primary publications since Monday in ET.

    Do not count incidental/mistagged sports memberships on crime and county
    stories. Count a canonical article only once even when repeated in the archive.
    """
    now = now or datetime.now(timezone.utc)
    today = _local_date(now)
    monday = today - timedelta(days=today.weekday())
    seen = set()
    for row in archive or []:
        if not isinstance(row, dict) or row.get("category_key") != "sports":
            continue
        issued = (
            row.get("canonical_first_published_at")
            or row.get("first_published")
            or row.get("date")
            or str(row.get("canonical_slug") or row.get("slug") or "")[:10]
        )
        issued_date = _local_date(issued)
        if not issued_date or not (monday <= issued_date <= today):
            continue
        canonical = str(
            row.get("canonical_publication_id")
            or row.get("canonical_slug")
            or row.get("slug")
            or ""
        )
        if canonical:
            seen.add(canonical)
    published = len(seen)
    return {
        "week_start_et": monday.isoformat(),
        "published": published,
        "weekly_target_low": SPORTS_WEEKLY_TARGET_LOW,
        "weekly_max": SPORTS_WEEKLY_MAX,
        "remaining_week": max(0, SPORTS_WEEKLY_MAX - published),
        "available_this_run": min(SPORTS_PER_RUN_MAX, max(0, SPORTS_WEEKLY_MAX - published)),
    }


def sports_source_decision(item):
    """Only reject unambiguous scoreboard/listing inputs before editorial review.

    The model decides significance. This deterministic gate deliberately avoids
    making a rigid list of sports or blocking ordinary well-reported game recaps.
    """
    source = item if isinstance(item, dict) else {}
    title = str(source.get("title") or source.get("source_title") or "").strip()
    article = str(source.get("article_text") or source.get("summary") or "").strip()
    raw_url = str(source.get("link") or source.get("source_url") or "").strip()
    if not title:
        return {"eligible": False, "reason": "no_title"}
    if _GENERIC_SCOREBOARD_TITLE.search(title):
        return {"eligible": False, "reason": "scoreboard_or_statistics_listing"}
    if _LISTING_ROUTE.search(urlsplit(raw_url).path):
        return {"eligible": False, "reason": "scoreboard_schedule_statistics_page"}
    if _SCORE_ONLY_TITLE.fullmatch(title) and len(article.split()) < 180:
        return {"eligible": False, "reason": "score_only_without_reporting"}
    return {"eligible": True, "reason": "eligible_for_editorial_judgment"}


def filter_sports_sources(category_key, candidates):
    """Return original source objects unchanged, preserving source-index mapping."""
    if category_key != "sports":
        return list(candidates or []), []
    eligible, rejected = [], []
    for row in candidates or []:
        decision = sports_source_decision(row)
        if decision["eligible"]:
            eligible.append(row)
        else:
            rejected.append({
                "title": str((row or {}).get("title") or "")[:150],
                "reason": decision["reason"],
            })
    return eligible, rejected
