#!/usr/bin/env python3
"""Replace the retired masthead Morning Brief promo with the official App Store badge.

Runs after article/event generation and also in deploy-only, so archived pages,
regional landing pages, and untouched pages all receive the same masthead.
This intentionally leaves Kit's newsletter signup forms and modal alone.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
APP_URL = "https://apps.apple.com/us/app/treasure-coast-today/id6821545564"
BADGE_URL = "https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg"

APP_BADGE = (
    f'<a class="masthead-app-store" href="{APP_URL}" '
    'aria-label="Download Treasure Coast Today on the App Store" rel="noopener">'
    f'<img src="{BADGE_URL}" alt="Download on the App Store" '
    'width="135" height="40" decoding="async"></a>'
)
MOBILE_LINK = (
    f'<a href="{APP_URL}" class="mobile-nav-link" data-tct-app-store-link>'
    'Get the TCT iPhone App</a>'
)
LEGACY_MASTHEAD = re.compile(
    r'<a\b[^>]*\bclass="masthead-newsletter"[^>]*>.*?</a>',
    re.I | re.S,
)
MOBILE_EVENTS_LINK = re.compile(r'<a href="/events\.html" class="mobile-nav-link[^"]*"[^>]*>Events</a>', re.I)


CSS_ASSET_VERSION = re.search(
    r'ASSET_VERSION = "([^"]+)"',
    (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8"),
)
if CSS_ASSET_VERSION is None:
    raise RuntimeError("Unable to resolve TCT shared CSS version")
CSS_ASSET_VERSION = CSS_ASSET_VERSION.group(1)
CSS_REFERENCE = re.compile(r'(/style\.css\?v=)\d+(?:\.\d+)+')

def replace_header_promo(html: str) -> str:
    # Only replace the header promo, not the independent newsletter signups.
    updated = LEGACY_MASTHEAD.sub(APP_BADGE, html)
    if ('id="tct-mobile-nav"' in updated
            and 'data-tct-app-store-link' not in updated):
        updated = MOBILE_EVENTS_LINK.sub(
            lambda match: MOBILE_LINK + "\n          " + match.group(0),
            updated,
            count=1,
        )
    if 'class="masthead-app-store"' in updated:
        # Older archives may still reference cached CSS that doesn't know the
        # new badge. Ensure every served page gets the current mobile layout.
        updated = CSS_REFERENCE.sub(
            lambda match: match.group(1) + CSS_ASSET_VERSION, updated
        )
    return updated


def reconcile(root: Path = ROOT) -> dict[str, int]:
    scanned = updated = 0
    for path in root.rglob("*.html"):
        if any(part.startswith(".") or part in ("node_modules", "venv", "__pycache__")
               for part in path.relative_to(root).parts):
            continue
        scanned += 1
        before = path.read_text(encoding="utf-8")
        after = replace_header_promo(before)
        if before != after:
            path.write_text(after, encoding="utf-8")
            updated += 1
    print(f"App Store masthead: scanned={scanned}, updated={updated}")
    return {"scanned": scanned, "updated": updated}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    reconcile(args.root)
