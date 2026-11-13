#!/usr/bin/env python3
"""Keep the native iOS news archive aligned with editor-approved article photos.

TCT's SwiftUI app reads archive.json.image_url, not the article's og:image,
RSS media:content or the website's thumbnail. This fast, local-only step
runs both before a full Update commit and before any Pages deploy (including
Deploy Only), so image corrections reach the app without rebuilding the iOS app.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path("data/article-image-overrides.json")
ARCHIVE = Path("archive.json")


def sync_archive(root: Path = ROOT) -> tuple[int, int]:
    ledger = json.loads((root / LEDGER).read_text(encoding="utf-8"))
    overrides = ledger.get("overrides") or {}
    archive_path = root / ARCHIVE
    rows = json.loads(archive_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("archive.json must be an array of news articles")
    changed = 0
    found = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("canonical_slug") or row.get("slug") or "").strip()
        override = overrides.get(slug)
        if not isinstance(override, dict):
            continue
        url = str(override.get("image_url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"Image override for {slug} must have a full HTTPS URL")
        found += 1
        # Preserve source_image_url and hosted_image_url as provenance of the
        # original feed/mirror. Only the displayed and social URLs are pinned.
        if row.get("image_url") != url:
            row["image_url"] = url
            changed += 1
        if row.get("rss_social_image_url") != url:
            row["rss_social_image_url"] = url
        row["article_image_override"] = True
        if row.get("rss_social_image_source") != "manual_article_image_override":
            row["rss_social_image_source"] = "manual_article_image_override"

    if changed:
        # Do not rewrite the multi-megabyte archive unnecessarily on every
        # deploy. JSON output is deterministic and preserves article order.
        archive_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return found, changed


if __name__ == "__main__":
    found, changed = sync_archive()
    print(f"iOS archive image overrides: {found} articles checked; {changed} corrected")
