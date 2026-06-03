"""
cleanup_archive.py — run once from the repo root to deduplicate archive.json
and delete the redundant article HTML files.

Usage:
  python cleanup_archive.py

Safe to re-run — it's idempotent.
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT    = Path(__file__).parent
ARCHIVE_PATH = REPO_ROOT / "archive.json"
ARTICLES_DIR = REPO_ROOT / "articles"


def normalize(headline):
    return re.sub(r"\s+", " ", headline.lower().strip())


def main():
    if not ARCHIVE_PATH.exists():
        print("archive.json not found — nothing to clean.")
        return

    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(archive)} entries from archive.json")

    seen_headlines = {}  # normalized headline -> first entry seen
    to_delete      = []  # entries to remove
    to_keep        = []  # entries to keep

    # Sort by date ascending so we keep the EARLIEST version of each story
    archive_sorted = sorted(archive, key=lambda e: e.get("date", ""))

    for entry in archive_sorted:
        norm = normalize(entry.get("headline", ""))
        if not norm:
            to_keep.append(entry)
            continue
        if norm in seen_headlines:
            to_delete.append(entry)
        else:
            seen_headlines[norm] = entry
            to_keep.append(entry)

    print(f"Keeping {len(to_keep)} unique articles")
    print(f"Removing {len(to_delete)} duplicates:")

    deleted_files  = 0
    missing_files  = 0

    for entry in to_delete:
        slug = entry.get("slug", "")
        headline = entry.get("headline", "")[:60]
        html_path = ARTICLES_DIR / f"{slug}.html"
        if html_path.exists():
            html_path.unlink()
            deleted_files += 1
            print(f"  Deleted: {slug}.html  ({headline}...)")
        else:
            missing_files += 1
            print(f"  Already gone: {slug}.html  ({headline}...)")

    # Write cleaned archive.json
    ARCHIVE_PATH.write_text(json.dumps(to_keep, indent=2), encoding="utf-8")
    print(f"\narchive.json updated: {len(to_keep)} entries")
    print(f"Files deleted: {deleted_files}, already missing: {missing_files}")
    print("\nDone. Run the pipeline once to regenerate archive.html and sitemap.xml.")


if __name__ == "__main__":
    main()
