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


def _rewrite_approved_credit(text: str, approved: str) -> str:
    pattern = (
        r'(<img\b[^>]*\bsrc="' + re.escape(approved) +
        r'"[^>]*>\s*<figcaption class="img-credit">)Photo: CBS12(</figcaption>)'
    )
    return re.sub(pattern, r"\1TCT illustrative image\2", text)


def rewrite_text(path: Path, approved: str, *, require_slug: bool = False) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8")
    if require_slug and SLUG not in content:
        return False
    revised = content
    if path.name == SLUG + ".html":
        # Generation may select an entirely NEW image URL. Never assume the
        # rejected 1f... screenshot is the only possible replacement candidate.
        sources = set(re.findall(
            r'<meta\s+(?:property="og:image"|name="twitter:image")\s+content="([^"]+)"',
            revised, flags=re.I,
        ))
        sources.update(re.findall(
            r'<figure\b[^>]*class="[^"]*\barticle-hero-image\b[^"]*"[^>]*>\s*'
            r'<img\b[^>]*\bsrc="([^"]+)"',
            revised, flags=re.I | re.S,
        ))
        if not sources:
            raise AssertionError("Crash article has no social or hero image metadata")
        for source in sources:
            if source != approved:
                revised = revised.replace(source, approved)
        revised = _rewrite_approved_credit(revised, approved)
        if REJECTED_IMAGE in revised:
            revised = revised.replace(REJECTED_IMAGE, approved)
    else:
        # Limit modifications on home, archive and category pages to the exact
        # crash-story link; never rewrite imagery belonging to other articles.
        target = re.compile(
            r'<a\b[^>]*\bhref="[^"]*' + re.escape(SLUG) +
            r'\.html[^"]*"[^>]*>.*?</a>',
            flags=re.I | re.S,
        )
        def fix_card(match: re.Match[str]) -> str:
            fragment = match.group(0)
            fragment = re.sub(
                r'(<img\b[^>]*\bsrc=")[^"]+(")',
                lambda m: m.group(1) + approved + m.group(2),
                fragment,
                flags=re.I,
            )
            return _rewrite_approved_credit(fragment, approved)
        revised = target.sub(fix_card, revised)
    if revised != content:
        path.write_text(revised, encoding="utf-8")
        return True
    return False


def rewrite_feed(path: Path, approved: str) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    def fix_item(match: re.Match[str]) -> str:
        item = match.group(0)
        if SLUG not in item:
            return item
        item = re.sub(
            r'(<media:content\b[^>]*\burl=")[^"]+(")',
            lambda m: m.group(1) + approved + m.group(2),
            item,
        )
        item = re.sub(
            r'(<enclosure\b[^>]*\burl=")[^"]+(")',
            lambda m: m.group(1) + approved + m.group(2),
            item,
        )
        return item
    revised = re.sub(r"<item>.*?</item>", fix_item, original, flags=re.S)
    if revised != original:
        path.write_text(revised, encoding="utf-8")
        return True
    return False


def rewrite_json(path: Path, approved: str) -> bool:
    if not path.is_file():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    def visit(value):
        nonlocal changed
        if isinstance(value, dict):
            is_target = any(SLUG in str(value.get(key) or "") for key in (
                "slug", "url", "canonical_url", "article_url", "link", "permalink",
            ))
            if is_target:
                # Keep source_image_url as original-source provenance.
                for key in ("image_url", "rss_social_image_url", "thumbnail_url", "hero_image"):
                    if key in value and value[key] != approved:
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
    required = (
        f'<meta property="og:image" content="{approved}">',
        f'<meta name="twitter:image" content="{approved}">',
    )
    if any(tag not in article for tag in required) or (
        f'src="{approved}"' not in article
    ):
        raise AssertionError("Crash article social tags or visible hero disagree with editorial override")
    return touched


if __name__ == "__main__":
    changes = apply()
    print(f"Editor-approved crash image enforced; modified {len(changes)} surfaces: {changes}")
