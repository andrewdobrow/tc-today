"""Published-article prose policy helpers.

These guards keep source/news-outlet provenance out of Treasure Coast Today copy
and remove outreach/no-comment boilerplate. Source provenance belongs in internal
metadata, not in reader-facing article prose, unless a media organization is
itself the subject of the story.
"""
from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

# Local/source outlets that commonly appear verbatim inside source copy. The
# dynamic source-host/source-title markers below extend this beyond this list.
_KNOWN_OUTLET_RE = re.compile(
    r"\b(?:"
    r"wpbf(?:\s+(?:news\s*)?25)?|"
    r"wptv(?:\s+newschannel\s*5)?|"
    r"wpec|cbs\s*12|cbs12|"
    r"tcpalm|treasure\s+coast\s+newspapers?|"
    r"wflx|fox\s*29|"
    r"the\s+palm\s+beach\s+post"
    r")\b",
    re.IGNORECASE,
)

# Reporting/process verbs that make an outlet reference provenance rather than
# story substance. If an outlet itself is the subject, ordinary substantive verbs
# such as "acquired", "laid off", "announced" etc. do not trigger this guard.
_REPORTING_PROCESS_RE = re.compile(
    r"\b(?:"
    r"according\s+to|reported(?:\s+by)?|reports?|"
    r"told|spoke\s+(?:to|with)|said\s+to|confirmed\s+to|"
    r"provided\s+to|shared\s+with|obtained\s+by|reviewed\s+by|"
    r"learned\s+by|asked\s+by|interviewed\s+by|"
    r"reached\s+out\s+to|contacted"
    r")\b",
    re.IGNORECASE,
)

# Outreach/no-comment boilerplate is never useful TCT prose, regardless of
# whether the source outlet is named explicitly.
_OUTREACH_ABSENCE_RE = re.compile(
    r"(?:"
    r"\bdeclined\s+to\s+(?:comment|talk|speak|be\s+interviewed|give\s+an\s+interview)\b|"
    r"\brefused\s+to\s+(?:comment|talk|speak|be\s+interviewed|give\s+an\s+interview)\b|"
    r"\bwould\s+not\s+(?:comment|talk|speak)\b|"
    r"\bdid\s+not\s+return\s+(?:a\s+)?(?:call|calls|message|messages|email|emails|request|requests)\b|"
    r"\b(?:did\s+not|has\s+not|have\s+not)\s+respond(?:ed)?\s+to\s+"
    r"(?:a\s+|the\s+)?(?:request|requests|inquiry|inquiries|call|calls|message|messages|email|emails)"
    r"(?:\s+for\s+comment)?\b|"
    r"\b(?:reporters?|the\s+station|the\s+outlet|the\s+newsroom)\s+"
    r"(?:reached\s+out|contacted|asked)\b|"
    r"\breached\s+out\s+to\b.*\bfor\s+comment\b|"
    r"\bcontacted\b.*\bfor\s+comment\b"
    r")",
    re.IGNORECASE,
)

_TAG_RE = re.compile(r"<[^>]+>")
_P_RE = re.compile(r"<p\b([^>]*)>(.*?)</p>", re.IGNORECASE | re.DOTALL)

# Protect common abbreviations before sentence splitting. The guard only needs
# editorially safe sentence boundaries; it is not intended as a general NLP parser.
_ABBREVIATION_RE = re.compile(
    r"\b(?:St|Mt|Mr|Mrs|Ms|Dr|Gov|Sen|Rep|Lt|Sgt|Capt|No|Inc|Co|Corp|Dept|Ave|Blvd|Rd|Fla)\.",
    re.IGNORECASE,
)
_DOTTED_ABBREVIATION_RE = re.compile(r"\b(?:U\.S|U\.S\.A|a\.m|p\.m)\.", re.IGNORECASE)
_DOT_SENTINEL = "\uFFF0"


def _plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", fragment or ""))).strip()


def _protect_abbreviation_dots(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return match.group(0).replace(".", _DOT_SENTINEL)

    text = _DOTTED_ABBREVIATION_RE.sub(repl, text)
    return _ABBREVIATION_RE.sub(repl, text)


def _split_sentences(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    protected = _protect_abbreviation_dots(raw)
    pieces = re.split(r"(?<=[.!?])\s+(?=[\"'“‘(\[]*[A-Z0-9])", protected)
    return [piece.replace(_DOT_SENTINEL, ".").strip() for piece in pieces if piece.strip()]


def _source_marker_terms(source_url: str = "", source_headline: str = "") -> set[str]:
    """Return conservative literal outlet markers derived from source metadata."""
    markers: set[str] = set()
    try:
        host = (urlsplit(str(source_url or "")).hostname or "").lower()
    except Exception:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    if host:
        first = host.split(".", 1)[0]
        if first and first not in {"news", "google", "feeds", "feed", "rss", "www"} and len(first) >= 3:
            markers.add(first)

    title = str(source_headline or "").strip()
    # Google News/local source titles commonly append the publisher after a dash.
    for separator in (" - ", " | "):
        if separator in title:
            suffix = title.rsplit(separator, 1)[-1].strip().lower()
            suffix = re.sub(r"[^a-z0-9 ]+", " ", suffix)
            suffix = re.sub(r"\s+", " ", suffix).strip()
            if 2 <= len(suffix) <= 40:
                markers.add(suffix)
    return markers


def _has_outlet_marker(sentence: str, source_url: str = "", source_headline: str = "") -> bool:
    if _KNOWN_OUTLET_RE.search(sentence or ""):
        return True
    normalized = re.sub(r"\s+", " ", str(sentence or "").lower())
    for marker in _source_marker_terms(source_url, source_headline):
        if re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", normalized):
            return True
    return False


def sentence_violates_article_prose_policy(
    sentence: str,
    *,
    source_url: str = "",
    source_headline: str = "",
) -> bool:
    """Return True for outreach boilerplate or source-outlet reporting prose."""
    sentence = str(sentence or "").strip()
    if not sentence:
        return False
    if _OUTREACH_ABSENCE_RE.search(sentence):
        return True
    return bool(
        _has_outlet_marker(sentence, source_url, source_headline)
        and _REPORTING_PROCESS_RE.search(sentence)
    )


def sanitize_article_text(
    text: str,
    *,
    source_url: str = "",
    source_headline: str = "",
) -> str:
    """Remove prohibited reader-facing reporting-process sentences from plain text."""
    raw = str(text or "")
    if not raw:
        return raw

    parts = re.split(r"(\n\s*\n)", raw)
    cleaned_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"\n\s*\n", part):
            cleaned_parts.append("\n\n")
            continue
        sentences = _split_sentences(part)
        kept = [
            sentence
            for sentence in sentences
            if not sentence_violates_article_prose_policy(
                sentence,
                source_url=source_url,
                source_headline=source_headline,
            )
        ]
        if kept:
            cleaned_parts.append(" ".join(kept).strip())

    result = "".join(cleaned_parts)
    result = re.sub(r"\n\s*\n(?:\s*\n)+", "\n\n", result)
    return result.strip()


def sanitize_article_body_html(
    body_html: str,
    *,
    source_url: str = "",
    source_headline: str = "",
) -> tuple[str, int]:
    """Sanitize generated article paragraphs without touching surrounding page chrome.

    Returns ``(html, changed_paragraph_count)``. Generated TCT prose paragraphs are
    plain text inside ``<p>`` tags, so rebuilding only paragraphs that actually
    violate policy avoids changing unaffected HTML, links, headings, or layout.
    """
    raw = str(body_html or "")
    if not raw:
        return raw, 0

    changed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        attrs = match.group(1) or ""
        inner = match.group(2) or ""
        plain = _plain(inner)
        if not plain:
            return match.group(0)
        cleaned = sanitize_article_text(
            plain,
            source_url=source_url,
            source_headline=source_headline,
        )
        if cleaned == plain:
            return match.group(0)
        changed += 1
        if not cleaned:
            return ""
        return f"<p{attrs}>{html.escape(cleaned)}</p>"

    return _P_RE.sub(repl, raw), changed
