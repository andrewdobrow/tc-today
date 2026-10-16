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



def _published_short_brief_on_disk(entry, output_root):
    """Recognize a *finished* short brief without reapplying the draft word floor.

    Publication has already authorized and stamped the row.  This exception is
    narrowly limited to a legitimate canonical publication with a real article
    file, a verified external source, and at least 60 words in two paragraphs.
    It must never turn a missing, retired, or quarantined hero into a feed card.
    """
    if not isinstance(entry, dict) or entry.get("ranking_eligible") is not True:
        return False
    slug = _safe_slug(entry.get("slug"))
    if not slug or entry.get("canonical_slug", slug) != slug:
        return False
    if entry.get("legacy_identity_status") != "identified":
        return False
    if any(entry.get(key) for key in (
        "identity_quarantine_reason", "exclude_from_live_recovery",
        "retired_custom", "_section_placeholder",
    )):
        return False
    if entry.get("is_weather_alert") or entry.get("is_custom"):
        return False
    if not (entry.get("canonical_publication_id") and entry.get("first_published")):
        return False
    source = str(entry.get("source_url") or "").strip()
    if urlsplit(source).scheme not in ("http", "https") or not urlsplit(source).netloc:
        return False
    try:
        words = int(entry.get("article_word_count") or 0)
        paragraphs = int(entry.get("article_paragraph_count") or 0)
    except (TypeError, ValueError):
        return False
    if not 60 <= words < 120 or paragraphs < 2:
        return False
    article = Path(output_root) / "articles" / f"{slug}.html"
    if not article.is_file():
        return False
    # A redirect file is not a publishable article, even if its archive metadata
    # hasn't yet been reconciled.  Normal published article HTML is preserved.
    try:
        article_text = article.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(article_text.strip()) and not re.search(
        r'<meta\s+[^>]*http-equiv\s*=\s*["\']?refresh\b',
        article_text, re.I,
    )


def _postpublication_checker(output_root, original_checker):
    """Honor normal eligibility; allow only verified published short briefs.

    The generator's `_archive_entry_publishable` callback has a generic 120-word
    archive recovery floor. The *earlier publication gate* intentionally permits
    verified short breaking briefs.  Once such a brief has been safely published,
    the iOS mirror must not reject it solely for falling below that generic floor.
    """
    def check(entry):
        if callable(original_checker) and original_checker(entry):
            return True
        return _published_short_brief_on_disk(entry, output_root)
    return check


def write_top_news_app_feed(output_root, **kwargs):
    # Adjust the pre-publication depth checker at the writer boundary, where the
    # actual article file can be verified. The pure builder remains strict and
    # retains its documented callback semantics for other callers.
    checker = kwargs.get("is_publishable")
    if callable(checker) and getattr(checker, "__name__", "") == "_archive_entry_publishable":
        # Only adapt TCT's known generic *archive-recovery* depth callback.
        # Other callers' explicit eligibility callbacks remain authoritative.
        kwargs["is_publishable"] = _postpublication_checker(output_root, checker)
    result = build_top_news_app_feed(**kwargs)
    destination = Path(output_root) / "data" / "top-news-app-feed.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
