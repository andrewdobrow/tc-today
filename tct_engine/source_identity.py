"""Deterministic source-article URL identity.

The same publisher article can appear under multiple evolving headlines while
retaining one stable article URL.  Exact article-URL identity is therefore a
strong persistent-story anchor, but feed and search URLs are explicitly
excluded because many unrelated articles share them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import re

SOURCE_IDENTITY_VERSION = "1.0"

_TRACKING_QUERY_KEYS = frozenset(
    {
        "oc", "output", "utm_campaign", "utm_content", "utm_medium",
        "utm_source", "utm_term", "fbclid", "gclid", "mc_cid", "mc_eid",
    }
)
_FEED_FILE_RE = re.compile(r"\.(?:rss|xml|atom)(?:/)?$", re.IGNORECASE)
_FEED_SEGMENTS = frozenset({"feed", "feeds", "rss"})


def normalize_source_identity_url(value: object) -> str:
    """Return a stable article identity URL or an empty string for non-articles."""

    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return ""

    scheme = parsed.scheme.casefold()
    host = parsed.hostname.casefold()
    port = parsed.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    folded_path = path.casefold()
    segments = [segment for segment in folded_path.split("/") if segment]

    # Google News article URLs are stable article identities. Search/feed URLs
    # are shared containers and must never join stories.
    is_google_article = host == "news.google.com" and folded_path.startswith("/rss/articles/")
    if host == "news.google.com" and not is_google_article:
        return ""

    if not is_google_article:
        if _FEED_FILE_RE.search(folded_path):
            return ""
        if any(segment in _FEED_SEGMENTS for segment in segments):
            return ""
        # A bare homepage/domain is not an article identity.
        if len(segments) < 2:
            return ""

    kept_query = [] if is_google_article else [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    query = urlencode(sorted(kept_query))
    normalized_path = path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, normalized_path, query, ""))


def story_source_identity_urls(story: Mapping[str, Any]) -> frozenset[str]:
    """Collect safe article identities from a persisted story record."""

    values: list[object] = list(story.get("sources", ()) or ())
    values.extend(
        candidate.get("source", "")
        for candidate in story.get("title_candidates", ()) or ()
        if isinstance(candidate, Mapping)
    )
    return frozenset(
        normalized
        for normalized in (normalize_source_identity_url(value) for value in values)
        if normalized
    )


@dataclass(frozen=True, slots=True)
class SourceIdentityMatch:
    matched: bool
    story_id: str | None
    normalized_url: str
    confidence: float
    reason: str
    decision_trace: tuple[str, ...]


def find_matching_source_story(
    source: object,
    stories: Iterable[Mapping[str, Any]],
) -> SourceIdentityMatch:
    """Find a story containing the exact same safe article identity URL."""

    normalized = normalize_source_identity_url(source)
    if not normalized:
        return SourceIdentityMatch(
            False, None, "", 0.0,
            "Source URL is not a safe article identity",
            ("Exact source article identity: false",),
        )

    matches = [
        str(story.get("story_id", "")).strip()
        for story in stories
        if normalized in story_source_identity_urls(story)
        and str(story.get("story_id", "")).strip()
    ]
    if not matches:
        return SourceIdentityMatch(
            False, None, normalized, 0.0,
            "No existing story contains this article URL",
            (
                "Exact source article identity: false",
                f"Normalized source URL: {normalized}",
            ),
        )

    story_id = sorted(matches)[0]
    return SourceIdentityMatch(
        True, story_id, normalized, 1.0,
        "Exact source article URL already belongs to this story",
        (
            "Exact source article identity: true",
            f"Normalized source URL: {normalized}",
            "Confidence: 1.00",
        ),
    )
