#!/usr/bin/env python3
"""Prepare public article previews and an out-of-repo protected-content export.

This script is a no-op unless TCT_MEMBERSHIP_UI_ENABLED is true. The export path
must be outside the repository so protected article text can never be committed.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.membership_paywall import (
    add_paywall_schema,
    inject_membership_assets,
    is_public_service_exception,
    paywall_html,
    split_article_body,
)

ARTICLES = ROOT / "articles"
BODY_RE = re.compile(r'<div class="article-body">(.*?)</div>', re.I | re.S)
HEADLINE_RE = re.compile(r'<h1\b[^>]*class="[^"]*article-headline[^"]*"[^>]*>(.*?)</h1>', re.I | re.S)
TAG_RE = re.compile(r'<[^>]+>')


def enabled() -> bool:
    return os.getenv("TCT_MEMBERSHIP_UI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


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

    protected: list[dict[str, str]] = []
    rewritten = exempt = short = already = 0
    for path in sorted(ARTICLES.glob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if 'http-equiv="refresh"' in text or "window.location.replace" in text:
            continue
        if 'data-tct-paywall' in text:
            already += 1
            continue
        body_match = BODY_RE.search(text)
        if not body_match:
            continue
        headline_match = HEADLINE_RE.search(text)
        headline = TAG_RE.sub(" ", headline_match.group(1) if headline_match else "")
        body_html = body_match.group(1)
        if is_public_service_exception(headline, body_html):
            exempt += 1
            continue
        split = split_article_body(body_html)
        if not split:
            short += 1
            continue

        slug = path.stem
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
    print(f"Membership paywall prepared: {rewritten} protected, {exempt} public-service free, {short} too short, {already} already protected")
    print(f"Protected export written outside repo: {export_path}")


if __name__ == "__main__":
    main()
