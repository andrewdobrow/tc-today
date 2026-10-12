"""Mirror the PUBLISHED homepage's hero + Top Stories order for native clients.

Additional feed cards are supplementary recent archive entries, never promoted to
hero or inserted ahead of the homepage's chosen editorial deck.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
MIN_DESIRED_CARDS = 20
MAX_CARDS = 24
SUPPLEMENT_MAX_AGE_DAYS = 7

# A historic or expired alert must not become 'more news' just because it is recent.
# Current emergency warnings are only ever allowed through the primary editorial
# deck after the site's separate authoritative verification guards.
_UNVERIFIED_WARNING = re.compile(
    r"\b(?:flash flood|flood|tornado|severe thunderstorm|storm surge)\s+"
    r"(?:warning|watch|advisory)\b|\bunder (?:a |an )?"
    r"(?:flash flood|flood|tornado|severe thunderstorm|storm surge)\s+"
    r"(?:warning|watch|advisory)\b", re.I,
)


def _safe_slug(value: str) -> str:
    value = str(value or "").strip()
    if not value or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", value):
        return ""
    return value


def slug_from_url(url: str) -> str:
    try:
        path = urlsplit(str(url or "")).path
    except ValueError:
        return ""
    if not path.startswith("/articles/") or not path.endswith(".html"):
        return ""
    return _safe_slug(path[len("/articles/"):-len(".html")])


def build_top_news_app_feed(*, hero_slug, top_story_slugs, homepage_other_slugs,
                            archive, now=None, is_publishable=None):
    """Build from homepage final choices, not rank recommendations or archive date.

    Exclude aliases, retired or ineligible records and duplicate publication IDs.
    Fill only the *supplemental* section from safe articles <= 7 days old.
    """
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date()
    entries = {}
    for entry in archive:
        slug = _safe_slug(entry.get("slug"))
        if not slug or entry.get("canonical_slug", slug) != slug:
            continue
        if entry.get("ranking_eligible") is not True:
            continue
        if callable(is_publishable) and not is_publishable(entry):
            continue
        entries[slug] = entry

    hero_slug = _safe_slug(hero_slug)
    if hero_slug not in entries:
        raise ValueError("Homepage hero missing from canonical publishable archive; refusing out-of-sync app feed")

    seen_ids = set()

    def append_unique(slug, output, *, supplement=False):
        slug = _safe_slug(slug)
        record = entries.get(slug)
        if not record:
            return False
        publication_id = record.get("canonical_publication_id") or slug
        if publication_id in seen_ids:
            return False
        if supplement:
            title = str(record.get("headline") or "")
            if _UNVERIFIED_WARNING.search(title):
                return False
            date_text = str(record.get("date") or "")[:10]
            try:
                published = date.fromisoformat(date_text)
            except ValueError:
                return False
            age = (today - published).days
            if not 0 <= age <= SUPPLEMENT_MAX_AGE_DAYS:
                return False
        seen_ids.add(publication_id)
        output.append({"slug": slug})
        return True

    hero = []
    append_unique(hero_slug, hero)
    top = []
    for slug in top_story_slugs:
        append_unique(slug, top)
    more = []
    for slug in homepage_other_slugs:
        if len(hero) + len(top) + len(more) >= MAX_CARDS:
            break
        append_unique(slug, more, supplement=True)

    # Only backfill below the editor's current picks; even 4 Top Stories still
    # result in a useful native feed on weekends without promoting stale leads.
    archive_newest_first = sorted(
        entries.values(),
        key=lambda e: (str(e.get("date") or ""), str(e.get("lastmod") or "")),
        reverse=True,
    )
    for item in archive_newest_first:
        if len(hero) + len(top) + len(more) >= MIN_DESIRED_CARDS:
            break
        append_unique(item["slug"], more, supplement=True)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "hero": hero[0],
        "top_stories": top,
        "more_news": more,
        "policy": "homepage_final_hero_then_visible_top_stories; recent_archive_supplement_only",
    }


def write_top_news_app_feed(output_root, **kwargs):
    result = build_top_news_app_feed(**kwargs)
    destination = Path(output_root) / "data" / "top-news-app-feed.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
