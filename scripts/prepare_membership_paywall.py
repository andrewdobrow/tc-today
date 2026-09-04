#!/usr/bin/env python3
"""Prepare consistent public article teasers and a protected-content export.

This script is a no-op unless TCT_MEMBERSHIP_UI_ENABLED is true. The export path
must be outside the repository so protected article text can never be committed.
When a protected-store snapshot is supplied, already-paywalled legacy pages are
rehydrated first and then re-split using the current teaser contract.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.membership_paywall import (
    FULL_BODY_MARKER,
    add_paywall_schema,
    inject_membership_assets,
    paywall_html,
    split_article_body,
)

ARTICLES = ROOT / "articles"
BODY_RE = re.compile(
    r'<div class="article-body">(.*?)</div>'
    r'(?=\s*(?:<aside class="newsletter-inline-slot[^>]*>.*?</aside>\s*)?'
    r'(?:<aside class="event-link-box"[^>]*>.*?</aside>\s*)?'
    r'<div class="article-share">)',
    re.I | re.S,
)
TAG_RE = re.compile(r'<[^>]+>')
PAYWALLED_RE = re.compile(
    r'<div class="article-body tct-member-preview">(.*?)</div>\s*'
    r'<div class="tct-member-only">.*?'
    r'<div id="tct-protected-content"[^>]*></div>\s*</div>',
    re.I | re.S,
)
# ``data-tct-paywall-newsletter`` is a dormant newsletter-slot marker, not the
# membership paywall itself. Keep this exact so the newsletter attribute can never
# make an unprotected full article look like an already-paywalled page.
ACTUAL_PAYWALL_MARKER_RE = re.compile(r'(?<![\w-])data-tct-paywall(?![\w-])', re.I)
PAYWALL_NEWSLETTER_SLOT_RE = re.compile(
    r'\s*<aside\b(?=[^>]*data-tct-paywall-newsletter)[^>]*>.*?</aside>',
    re.I | re.S,
)
CURRENT_PREVIEW_P_RE = re.compile(
    r'<p([^>]*)data-tct-preview-paragraph="true"([^>]*)>(.*?)</p>', re.I | re.S
)
CURRENT_CONTINUATION_P_RE = re.compile(
    r'<p([^>]*)data-tct-first-paragraph-continuation="true"([^>]*)>(.*?)</p>', re.I | re.S
)


def enabled() -> bool:
    return os.getenv("TCT_MEMBERSHIP_UI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", fragment or ""))).strip()


def _load_snapshot() -> dict[str, str]:
    raw = os.getenv("TCT_PROTECTED_SNAPSHOT_PATH", "").strip()
    if not raw:
        return {}
    path = Path(raw)
    if not path.exists():
        raise RuntimeError(f"Protected-content snapshot is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("Protected-content snapshot has invalid shape")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "").strip()
        protected_body = str(row.get("protected_body") or "")
        if slug and protected_body:
            result[slug] = protected_body
    return result


def _rehydrate_legacy_body(preview_html: str, protected_body: str) -> str:
    """Reconstruct full article HTML from either current or legacy protected rows."""
    protected_body = str(protected_body or "")
    if protected_body.startswith(FULL_BODY_MARKER):
        return protected_body[len(FULL_BODY_MARKER):].strip()

    # v1.13.5.4 split the first paragraph itself. Rejoin that shape exactly.
    preview_match = CURRENT_PREVIEW_P_RE.search(preview_html)
    continuation_match = CURRENT_CONTINUATION_P_RE.search(protected_body)
    if preview_match and continuation_match:
        preview_text = _plain(preview_match.group(3)).rstrip(" …")
        continuation_text = _plain(continuation_match.group(3))
        attrs = (preview_match.group(1) or "") + (preview_match.group(2) or "")
        attrs = re.sub(r'\s*data-tct-preview-paragraph="true"', "", attrs, flags=re.I)
        first_paragraph = f'<p{attrs}>{html.escape((preview_text + " " + continuation_text).strip())}</p>'
        preview_prefix = preview_html[:preview_match.start()]
        preview_suffix = preview_html[preview_match.end():]
        protected_without_continuation = (
            protected_body[:continuation_match.start()] + protected_body[continuation_match.end():]
        )
        return (preview_prefix + first_paragraph + preview_suffix + protected_without_continuation).strip()

    # v1.13.4 exposed paragraph one plus part of paragraph two. The protected row
    # contains the remainder. Concatenating preserves every word; at worst an old
    # split sentence remains separated by a paragraph break until this migration.
    return (preview_html.strip() + protected_body.strip()).strip()


def _rehydrate_paywalled_page(page_html: str, protected_body: str, slug: str = "") -> str:
    match = PAYWALLED_RE.search(page_html)
    if not match:
        raise RuntimeError(f"Existing paywall markup could not be rehydrated safely: {slug or 'unknown slug'}")
    full_body = _rehydrate_legacy_body(match.group(1), protected_body)
    replacement = '<div class="article-body">' + full_body + '</div>'
    return page_html[:match.start()] + replacement + page_html[match.end():]


def main() -> None:
    if not enabled():
        print("Membership paywall preparation skipped: UI disabled")
        return
    export_raw = os.getenv("TCT_PROTECTED_EXPORT_PATH", "").strip()
    if not export_raw:
        raise RuntimeError("TCT_PROTECTED_EXPORT_PATH is required when membership UI is enabled")
    export_path = Path(export_raw).resolve()
    root_resolved = ROOT.resolve()
    if root_resolved == export_path or root_resolved in export_path.parents:
        raise RuntimeError("Protected-content export must be outside the public repository")

    snapshot = _load_snapshot()
    snapshot_expected = bool(os.getenv("TCT_PROTECTED_SNAPSHOT_PATH", "").strip())
    protected: list[dict[str, str]] = []
    rewritten = short = already = rehydrated = 0
    for path in sorted(ARTICLES.glob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        original_text = text
        was_rehydrated = False
        if 'http-equiv="refresh"' in text or "window.location.replace" in text:
            continue

        slug = path.stem
        if ACTUAL_PAYWALL_MARKER_RE.search(text):
            stored = snapshot.get(slug)
            if stored:
                text = _rehydrate_paywalled_page(text, stored, slug=slug)
                rehydrated += 1
                was_rehydrated = True
            elif snapshot_expected:
                raise RuntimeError(f"Protected store is missing existing paywalled article: {slug}")
            else:
                already += 1
                continue

        body_match = BODY_RE.search(text)
        if not body_match:
            continue
        body_html = body_match.group(1)
        split = split_article_body(body_html)
        if not split:
            short += 1
            # If this was a rehydrated legacy page, leave the original paywall on
            # disk rather than accidentally publishing the full article. Otherwise
            # remove the dormant paywall-only newsletter slot from a genuinely
            # unprotected short article so it has no post-article signup surface.
            if was_rehydrated:
                assert path.read_text(encoding="utf-8", errors="ignore") == original_text
            else:
                cleaned = PAYWALL_NEWSLETTER_SLOT_RE.sub("", text)
                if cleaned != original_text:
                    path.write_text(cleaned, encoding="utf-8")
            continue

        protected.append({"slug": slug, "protected_body": split.protected_html})
        replacement = (
            '<div class="article-body tct-member-preview">'
            + split.preview_html
            + '</div>\n<div class="tct-member-only">'
            + paywall_html(slug)
            + '</div>'
        )
        text = text[: body_match.start()] + replacement + text[body_match.end() :]
        text = add_paywall_schema(text)
        text = inject_membership_assets(text, slug)
        path.write_text(text, encoding="utf-8")
        rewritten += 1

    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps({"articles": protected}, ensure_ascii=False), encoding="utf-8")
    print(
        f"Membership paywall prepared: {rewritten} protected, {rehydrated} legacy/current pages rehydrated, "
        f"{short} too short, {already} already protected without snapshot"
    )
    print(f"Protected export written outside repo: {export_path}")


if __name__ == "__main__":
    main()
