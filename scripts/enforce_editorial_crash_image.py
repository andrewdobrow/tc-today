#!/usr/bin/env python3
"""Enforce a specific editor-approved image replacement after news generation.

The generator can rewrite existing article pages after applying its image
override ledger. This final-stage guard ensures that an explicitly rejected
competitor-branded image cannot return to the article or its news surfaces.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SLUG = "2026-11-09-at-least-one-dead-in-crash-on-37th-street-in-indian-river-county"
REJECTED_IMAGE = (
    "https://images.treasurecoast.today/articles/1f/"
    "1f555a6ba1ffd67f5dd3e927d47b42b331985e8eae36531c29de8c6bbf12b615.jpg"
)
OVERRIDE_LEDGER = "data/article-image-overrides.json"
IMAGE_KEYS = ("image_url", "rss_social_image_url", "hosted_image_url")
OTHER_IMAGE_KEYS = ("image", "thumbnail", "thumbnail_url", "hero_image", "og_image", "og_image_url")


def approved_url(root: Path) -> str:
    ledger = json.loads((root / OVERRIDE_LEDGER).read_text(encoding="utf-8"))
    url = ledger["overrides"][SLUG]["image_url"]
    if not url.startswith("https://treasurecoast.today/images/editorial/"):
        raise ValueError("Crash photo override must point to a first-party TCT editorial image")
    return url


def rewrite_text(path: Path, approved: str, *, require_slug: bool = False) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8")
    if require_slug and SLUG not in content:
        return False
    revised = content.replace(REJECTED_IMAGE, approved)
    # Change a credit only when it immediately follows this precise image;
    # unrelated CBS12-sourced images must retain their accurate attribution.
    revised = re.sub(
        r'(<img\b[^>]*\bsrc="' + re.escape(approved) +
        r'"[^>]*>)(<figcaption class="img-credit">)Photo: CBS12(</figcaption>)',
        r"\1\2TCT illustrative image\3",
        revised,
    )
    if revised == content:
        return False
    path.write_text(revised, encoding="utf-8")
    return True


def rewrite_feed(path: Path, approved: str) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    def replace_item(match: re.Match[str]) -> str:
        item = match.group(0)
        return item.replace(REJECTED_IMAGE, approved) if SLUG in item else item
    revised = re.sub(r"<item>.*?</item>", replace_item, original, flags=re.S)
    if revised == original:
        return False
    path.write_text(revised, encoding="utf-8")
    return True


def rewrite_json(path: Path, approved: str) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    payload = json.loads(original)
    changed = False
    def visit(value):
        nonlocal changed
        if isinstance(value, dict):
            identity = any(SLUG in str(value.get(key) or "") for key in (
                "slug", "url", "canonical_url", "article_url", "link", "permalink"
            ))
            if identity:
                for key in IMAGE_KEYS + OTHER_IMAGE_KEYS:
                    if value.get(key) == REJECTED_IMAGE:
                        value[key] = approved
                        changed = True
            for child in value.values():
                if isinstance(child, (dict, list)):
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(payload)
    if changed:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def apply(root: Path = ROOT) -> list[str]:
    approved = approved_url(root)
    touched = []
    page = root / "articles" / (SLUG + ".html")
    if not page.is_file():
        raise FileNotFoundError(f"Editor-corrected article is missing: {page}")
    if rewrite_text(page, approved):
        touched.append(str(page.relative_to(root)))
    for path in root.glob("*.html"):
        if rewrite_text(path, approved, require_slug=True):
            touched.append(str(path.relative_to(root)))
    for folder in ("indian-river", "crime", "crime-safety", "vero-beach"):
        directory = root / folder
        if directory.is_dir():
            for path in directory.glob("*.html"):
                if rewrite_text(path, approved, require_slug=True):
                    touched.append(str(path.relative_to(root)))
    if rewrite_feed(root / "feed.xml", approved):
        touched.append("feed.xml")
    for name in ("archive.json", "data.json"):
        if rewrite_json(root / name, approved):
            touched.append(name)
    article = page.read_text(encoding="utf-8")
    if REJECTED_IMAGE in article or approved not in article:
        raise AssertionError("Final article image does not match editor-approved override")
    return touched


if __name__ == "__main__":
    changes = apply()
    print(f"Editor-approved crash image enforced; modified {len(changes)} surfaces: {changes}")
