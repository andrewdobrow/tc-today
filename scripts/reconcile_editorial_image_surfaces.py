#!/usr/bin/env python3
"""Reapply editor-approved image URLs to retained published pages and feeds.

The generator correctly applies overrides when it renders a story, but older
published HTML survives routine runs. Keep those pages, cards and RSS images
aligned without regenerating copy or changing unrelated stories.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlparse

try:
    from scripts.sync_editorial_image_archive import sync_archive
except ModuleNotFoundError:
    from sync_editorial_image_archive import sync_archive

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path("data/article-image-overrides.json")
META_IMAGE = re.compile(
    r'<meta\b[^>]*\b(?:property="og:image"|name="twitter:image")[^>]*'
    r'\bcontent="([^"]+)"', re.I
)
HERO_IMAGE = re.compile(
    r'<figure\b[^>]*\bclass="[^"]*\barticle-hero-image\b[^"]*"[^>]*>'
    r'\s*<img\b[^>]*\bsrc="([^"]+)"', re.I | re.S
)
IMG_SRC = re.compile(r'(<img\b[^>]*\bsrc=")[^"]+(")', re.I)
RSS_IMAGE = re.compile(
    r'(<(?:media:content|media:thumbnail|enclosure)\b[^>]*\burl=")[^"]+(")', re.I
)


def _write_if_changed(path: Path, before: str, after: str) -> bool:
    if after == before:
        return False
    path.write_text(after, encoding="utf-8")
    return True


def _fix_article(path: Path, approved: str) -> bool:
    if not path.is_file():
        return False
    before = path.read_text(encoding="utf-8")
    # Social metadata, visible lead image and JSON-LD all refer to the same
    # existing image. Replace only those known image URLs in this exact story.
    sources = set(META_IMAGE.findall(before))
    sources.update(HERO_IMAGE.findall(before))
    if not sources:
        return False  # Redirect stub, or no image-bearing article to repair.
    after = before
    for source in sources:
        if source and source != approved:
            after = after.replace(source, approved)
    return _write_if_changed(path, before, after)


def _fix_card_page(path: Path, slug: str, approved: str) -> bool:
    if not path.is_file():
        return False
    before = path.read_text(encoding="utf-8")
    if slug not in before:
        return False
    # Only touch image tags nested inside links to the exact selected story.
    # This prevents another article's image from being replaced on news grids.
    target = re.compile(
        r'<a\b[^>]*\bhref="[^"]*/articles/'
        + re.escape(slug)
        + r'\.html(?:[?#][^"]*)?"[^>]*>.*?</a>',
        re.I | re.S,
    )

    def fix_anchor(match: re.Match[str]) -> str:
        return IMG_SRC.sub(lambda m: m.group(1) + approved + m.group(2), match.group(0))

    after = target.sub(fix_anchor, before)
    return _write_if_changed(path, before, after)


def _fix_feed(path: Path, slug: str, approved: str) -> bool:
    if not path.is_file():
        return False
    before = path.read_text(encoding="utf-8")
    if slug not in before:
        return False

    def fix_item(match: re.Match[str]) -> str:
        item = match.group(0)
        if f"/articles/{slug}.html" not in item:
            return item
        return RSS_IMAGE.sub(lambda m: m.group(1) + approved + m.group(2), item)

    after = re.sub(r"<item\b[^>]*>.*?</item>", fix_item, before, flags=re.I | re.S)
    return _write_if_changed(path, before, after)


def reconcile(root: Path = ROOT) -> list[str]:
    root = Path(root)
    payload = json.loads((root / LEDGER).read_text(encoding="utf-8"))
    overrides = payload.get("overrides") or {}
    touched: set[str] = set()

    cards = list(root.glob("*.html")) + list(root.glob("*/index.html"))
    for slug, data in overrides.items():
        if not isinstance(data, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
            continue
        approved = str(data.get("image_url") or "").strip()
        parsed = urlparse(approved)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"Invalid HTTPS image override for {slug}")
        article_path = root / "articles" / (slug + ".html")
        if _fix_article(article_path, approved):
            touched.add(str(article_path.relative_to(root)))
        for page in cards:
            if _fix_card_page(page, slug, approved):
                touched.add(str(page.relative_to(root)))
        if _fix_feed(root / "feed.xml", slug, approved):
            touched.add("feed.xml")

    # iOS reads archive.json, not the website HTML. Keep its native thumbnail
    # pinned to the same editorial selection, even on deploy-only runs.
    archive_path = root / "archive.json"
    if archive_path.is_file():
        before = archive_path.read_bytes()
        sync_archive(root)
        if archive_path.read_bytes() != before:
            touched.add("archive.json")
    return sorted(touched)


if __name__ == "__main__":
    changed = reconcile()
    print(f"Editor-approved image surfaces reconciled: {len(changed)} changed: {changed}")
