#!/usr/bin/env python3
"""Place a voluntary reader-support appeal just before each article newsletter form.

Run after article generation and after the existing newsletter-normalization
pass. Only the article's presentation is changed; source copy, URLs, event
identity, and subscription state are untouched. Works with retained pages.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- TCT_ARTICLE_READER_SUPPORT_START -->"
END = "<!-- TCT_ARTICLE_READER_SUPPORT_END -->"
EXISTING = re.compile(re.escape(START) + r"[\s\S]*?" + re.escape(END) + r"\s*", re.I)
ARTICLE_NEWSLETTER = re.compile(
    r'(?P<indent>^[ \t]*)<aside\b(?=[^>]*\bnewsletter-inline-slot--article\b)[^>]*>',
    re.I | re.M,
)
REDIRECT = re.compile(r'<meta\s+[^>]*http-equiv=["\']refresh["\']', re.I)
DONATE_HTML = """<!-- TCT_ARTICLE_READER_SUPPORT_START -->
<section class="tct-article-reader-support" aria-label="Support free local news">
  <div class="tct-article-reader-support__copy">
    <span class="tct-article-reader-support__eyebrow">A NOTE TO OUR READERS</span>
    <h2>Local news needs local support.</h2>
    <p>From local government decisions and public safety updates to the events bringing our communities together, Treasure Coast Today helps you stay connected to the place you call home.</p>
    <p>Every story is free to read. If TCT is part of your day, your contribution helps keep it that way.</p>
  </div>
  <div class="tct-article-reader-support__action">
    <a href="/donate.html" class="tct-article-reader-support__button"><span aria-hidden="true">&#9829;</span> Support TCT Today <span aria-hidden="true">&rarr;</span></a>
    <small>Give any amount. No subscription required.</small>
  </div>
</section>
<!-- TCT_ARTICLE_READER_SUPPORT_END -->"""


def update_article(html: str) -> str:
    if REDIRECT.search(html) or 'name="robots" content="noindex,follow"' in html:
        return html
    # Remove a previously generated instance, then insert exactly once above
    # the article newsletter signup. This also repairs prior wrong placement.
    without_old = EXISTING.sub("", html)
    candidates = list(ARTICLE_NEWSLETTER.finditer(without_old))
    if len(candidates) != 1:
        if not candidates and START not in html:
            return html  # pages not carrying a newsletter are out of scope
        raise ValueError(f"Expected exactly one article newsletter slot, found {len(candidates)}")
    match = candidates[0]
    indent = match.group("indent")
    appeal = "\n".join(indent + line if line else "" for line in DONATE_HTML.split("\n"))
    result = without_old[:match.start()] + appeal + "\n" + without_old[match.start():]
    return result


def normalize(root: Path = ROOT) -> dict[str, int]:
    directory = root / "articles"
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    scanned = updated = 0
    for path in directory.glob("*.html"):
        scanned += 1
        before = path.read_text(encoding="utf-8")
        after = update_article(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            updated += 1
    print(f"Article reader-support appeal: scanned={scanned}, updated={updated}")
    return {"scanned": scanned, "updated": updated}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    normalize(args.root)
