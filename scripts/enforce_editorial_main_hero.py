"""Keep advertiser-funded articles out of the main homepage news hero.

The production generator may carry a sponsored custom article forward as the
freshest general hero while the urgency ranker remains observe-only. This
post-generation guard uses the *published* article sponsor disclosure, then
selects the highest-ranked existing editorial category hero from the current
Top Stories report. It doesn't rewrite copy, imagery, or category placement.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
HERO = re.compile(r'<section class="hero[^"]*" data-cat-hero="(?P<category>[^"]+)"[^>]*>[\s\S]*?</section>')
HERO_URL = re.compile(r'<a\s+class="hero-v3-link"\s+href="([^"]+)"')
HEADING_LABEL = re.compile(r'^\s*<div class="(?:county-section-label|topic-section-label)">[\s\S]*?</div>')
SLUG = re.compile(r'^/articles/([a-z0-9][a-z0-9-]*)\.html$')


def _slug_of(section: str) -> str | None:
    link = HERO_URL.search(section)
    if not link:
        return None
    parsed = urlparse(link.group(1))
    if parsed.scheme not in ("https", "") or parsed.netloc not in ("treasurecoast.today", ""):
        return None
    matched = SLUG.fullmatch(parsed.path)
    return matched.group(1) if matched else None


def _is_sponsored(slug: str | None, root: Path, queue: list[dict]) -> bool:
    if not slug:
        return False
    if any(row.get("slug") == slug and row.get("sponsored") for row in queue):
        return True
    page = root / "articles" / f"{slug}.html"
    if not page.exists():
        return False
    content = page.read_text(encoding="utf-8")
    return "This article was produced in partnership with" in content or "Sponsored by <a" in content


def ensure_editorial_main_hero(root: Path = ROOT) -> bool:
    home = root / "index.html"
    report = root / "data" / "top-stories-ranking-report.json"
    queue_path = root / "custom_articles.json"
    if not home.exists() or not report.exists():
        raise FileNotFoundError("Homepage or Top Stories rank report missing")
    html = home.read_text(encoding="utf-8")
    heroes = list(HERO.finditer(html))
    primary = [hero for hero in heroes if hero.group("category") == "all"]
    if len(primary) != 1:
        raise RuntimeError(f"Expected exactly one general news hero; found {len(primary)}")
    current_slug = _slug_of(primary[0].group())
    queue = json.loads(queue_path.read_text(encoding="utf-8")) if queue_path.exists() else []
    if not isinstance(queue, list):
        raise ValueError("Custom queue must be a JSON list")
    if not _is_sponsored(current_slug, root, queue):
        return False

    ranked = json.loads(report.read_text(encoding="utf-8"))
    sections_by_slug = {}
    for section in heroes:
        if section.group("category") == "all":
            continue
        slug = _slug_of(section.group())
        if slug and not _is_sponsored(slug, root, queue):
            sections_by_slug.setdefault(slug, section.group())

    replacement = None
    for story in ranked.get("selected", []):
        if not story.get("primary_eligible", True):
            continue
        replacement = sections_by_slug.get(story.get("slug"))
        if replacement:
            break
    if replacement is None:
        raise RuntimeError("Sponsored general hero found, but no eligible ranked editorial category hero exists")

    # Reuse the complete image, headline, URL, and timestamp of an existing
    # already-rendered category hero. Strip its county/topic heading, which
    # isn't part of the top-level hero's markup.
    inner = replacement[replacement.index(">") + 1:replacement.rfind("</section>")]
    inner = HEADING_LABEL.sub("", inner, count=1)
    open_tag = primary[0].group()[:primary[0].group().index(">") + 1]
    updated_section = open_tag + inner + "</section>"
    target = primary[0]
    revised_html = html[:target.start()] + updated_section + html[target.end():]
    if _is_sponsored(_slug_of(updated_section), root, queue):
        raise RuntimeError("Selected replacement homepage hero is sponsored")
    home.write_text(revised_html, encoding="utf-8")
    print(f"Editorial homepage hero restored: {_slug_of(updated_section)}")
    return True


if __name__ == "__main__":
    changed = ensure_editorial_main_hero()
    print(f"Sponsored hero policy: {'updated' if changed else 'already compliant'}")
