#!/usr/bin/env python3
"""Securely sync or snapshot protected article content through Supabase."""
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

from tct_engine.membership_paywall import split_article_body
BODY_RE = re.compile(r'<div class="article-body">(.*?)</div>', re.I | re.S)
# Keep this exact: data-tct-paywall-newsletter is a dormant newsletter slot,
# not the membership paywall itself.
ACTUAL_PAYWALL_MARKER_RE = re.compile(r'(?<![\w-])data-tct-paywall(?![\w-])', re.I)


def scan_public_articles() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((ROOT / "articles").glob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if (
            'http-equiv="refresh"' in text
            or "window.location.replace" in text
            or ACTUAL_PAYWALL_MARKER_RE.search(text)
        ):
            continue
        match = BODY_RE.search(text)
        if not match:
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


def _request(url: str, secret: str, payload: dict) -> requests.Response:
    response = requests.post(
        url,
        headers={"X-TCT-Content-Sync": secret, "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    if response.status_code >= 300:
        if (
            payload.get("action") == "snapshot"
            and response.status_code == 400
            and "Batch must contain 1-100 articles" in response.text
        ):
            raise RuntimeError(
                "Protected article snapshot is not supported by the deployed "
                "sync-protected-articles function. Deploy the current membership backend first."
            )
        raise RuntimeError(f"Protected article sync failed ({response.status_code}): {response.text[:300]}")
    return response


def snapshot_store(url: str, secret: str, output: Path) -> int:
    rows: list[dict[str, str]] = []
    offset = 0
    while True:
        response = _request(url, secret, {"action": "snapshot", "offset": offset, "limit": 200})
        payload = response.json()
        batch = payload.get("articles") if isinstance(payload, dict) else None
        if not isinstance(batch, list):
            raise RuntimeError("Protected article snapshot returned invalid shape")
        rows.extend(batch)
        next_offset = payload.get("next_offset")
        if next_offset is None:
            break
        offset = int(next_offset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"articles": rows}, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-file")
    parser.add_argument("--scan-public", action="store_true")
    parser.add_argument("--snapshot-file")
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

    selected = sum(bool(value) for value in (args.export_file, args.scan_public, args.snapshot_file))
    if selected != 1:
        raise RuntimeError("Choose exactly one of --export-file, --scan-public, or --snapshot-file")

    url = f"{base}/functions/v1/sync-protected-articles"
    if args.snapshot_file:
        total = snapshot_store(url, secret, Path(args.snapshot_file))
        print(f"Protected article snapshot complete: {total} article(s)")
        return

    if args.export_file:
        rows = load_export(Path(args.export_file))
    else:
        rows = scan_public_articles()
    if not rows:
        print("Protected article sync: nothing to sync")
        return

    total = 0
    for start in range(0, len(rows), 75):
        batch = rows[start:start + 75]
        _request(url, secret, {"articles": batch})
        total += len(batch)
    print(f"Protected article sync complete: {total} article payload(s)")


if __name__ == "__main__":
    main()
