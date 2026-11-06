#!/usr/bin/env python3
"""Send all website donation links directly to the existing Stripe checkout.

Post-generation reconciliation applies to retained article/event pages and
static chrome without changing the /donate.html document's canonical or other
non-link metadata. A second pass changes nothing.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STRIPE_DONATION_URL = "https://donate.stripe.com/4gM5kw9LWfRb7uV6P34ZG01"
# Anchors only; never alter page canonicals, metadata, legal documents or forms.
ANCHOR = re.compile(r"<a\b[^>]*>", re.I)
LINK = re.compile(r"""(?P<attr>\bhref\s*=\s*)(?P<quote>["'])(?P<href>[^"']+)(?P=quote)""", re.I)


def direct_donation_links(html: str) -> str:
    def rewrite_tag(match: re.Match[str]) -> str:
        tag = match.group(0)

        def rewrite_href(hit: re.Match[str]) -> str:
            href = hit.group("href")
            if href not in ("/donate.html", "https://treasurecoast.today/donate.html"):
                return hit.group(0)
            return f'{hit.group("attr")}{hit.group("quote")}{STRIPE_DONATION_URL}{hit.group("quote")}'

        return LINK.sub(rewrite_href, tag, count=1)

    return ANCHOR.sub(rewrite_tag, html)


def reconcile(root: Path = ROOT) -> dict[str, int]:
    scanned = updated = 0
    for path in root.rglob("*.html"):
        # Only publishable HTML, not hidden build caches or virtual environments.
        if any(part.startswith(".") or part in ("node_modules", "venv", "__pycache__") for part in path.relative_to(root).parts):
            continue
        scanned += 1
        before = path.read_text(encoding="utf-8")
        after = direct_donation_links(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            updated += 1
    print(f"Stripe donation links: scanned={scanned}, updated={updated}")
    return {"scanned": scanned, "updated": updated}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    reconcile(args.root)
