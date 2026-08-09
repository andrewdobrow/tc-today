#!/usr/bin/env python3
"""Securely sync protected article remainders to Supabase through an Edge Function."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from tct_engine.membership_paywall import is_public_service_exception, split_article_body
BODY_RE = re.compile(r'<div class="article-body">(.*?)</div>', re.I | re.S)
HEADLINE_RE = re.compile(r'<h1\b[^>]*class="[^"]*article-headline[^"]*"[^>]*>(.*?)</h1>', re.I | re.S)
TAG_RE = re.compile(r'<[^>]+>')


def scan_public_articles() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((ROOT / "articles").glob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if 'http-equiv="refresh"' in text or "window.location.replace" in text or 'data-tct-paywall' in text:
            continue
        match = BODY_RE.search(text)
        if not match:
            continue
        headline_match = HEADLINE_RE.search(text)
        headline = TAG_RE.sub(" ", headline_match.group(1) if headline_match else "")
        if is_public_service_exception(headline, match.group(1)):
            continue
        split = split_article_body(match.group(1))
        if split:
            rows.append({"slug": path.stem, "protected_body": split.protected_html})
    return rows


def load_export(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("Protected export has invalid shape")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-file")
    parser.add_argument("--scan-public", action="store_true")
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()

    base = os.getenv("TCT_SUPABASE_URL", "").strip().rstrip("/")
    secret = os.getenv("TCT_CONTENT_SYNC_SECRET", "").strip()
    if not base or not secret:
        message = "Protected article sync skipped: TCT_SUPABASE_URL or TCT_CONTENT_SYNC_SECRET missing"
        if args.required:
            raise RuntimeError(message)
        print(message)
        return

    if args.export_file:
        rows = load_export(Path(args.export_file))
    elif args.scan_public:
        rows = scan_public_articles()
    else:
        raise RuntimeError("Choose --export-file or --scan-public")
    if not rows:
        print("Protected article sync: nothing to sync")
        return

    url = f"{base}/functions/v1/sync-protected-articles"
    total = 0
    for start in range(0, len(rows), 75):
        batch = rows[start:start + 75]
        response = requests.post(
            url,
            headers={"X-TCT-Content-Sync": secret, "Content-Type": "application/json"},
            json={"articles": batch},
            timeout=45,
        )
        if response.status_code >= 300:
            raise RuntimeError(f"Protected article sync failed ({response.status_code}): {response.text[:300]}")
        total += len(batch)
    print(f"Protected article sync complete: {total} article remainder(s)")


if __name__ == "__main__":
    main()
