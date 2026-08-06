#!/usr/bin/env python3
"""Retire the exact false-jurisdiction Indian River publication from public surfaces."""
from __future__ import annotations
import argparse, json, os, re, tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SLUG = "2026-08-06-indian-river-county-sheriffs-deputies-shoot-kill-18-year-old-attacking-father-wi"
ARTICLE_PATH = f"/articles/{SLUG}.html"
ARTICLE_URL = f"https://treasurecoast.today{ARTICLE_PATH}"
SAFE_TARGET = "/indian-river/"

REDIRECT_HTML = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow">
<meta http-equiv="refresh" content="0; url=/indian-river/">
<link rel="canonical" href="https://treasurecoast.today/indian-river/">
<title>Article withdrawn | Treasure Coast Today</title></head>
<body><main><h1>Article withdrawn</h1><p>This article was withdrawn because its location was incorrectly attributed to Indian River County.</p><p><a href="/indian-river/">Return to Indian River County news</a></p></main>
<script>window.location.replace('/indian-river/');</script></body></html>
'''

_REMOVED = object()

def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)

def record_matches(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    candidates = []
    for key in ("slug", "canonical_slug", "permalink", "url", "href", "link", "article_url"):
        raw = value.get(key)
        if raw not in (None, ""):
            candidates.append(str(raw))
    return any(SLUG in raw or ARTICLE_PATH in raw or ARTICLE_URL in raw for raw in candidates)

def clean_json(value: Any) -> Any:
    if record_matches(value):
        return _REMOVED
    if isinstance(value, list):
        result = []
        for item in value:
            cleaned = clean_json(item)
            if cleaned is not _REMOVED:
                result.append(cleaned)
        return result
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            cleaned = clean_json(item)
            if cleaned is _REMOVED:
                if key == "hero":
                    result[key] = {}
                elif key in {"cards", "articles", "items", "stories"}:
                    result[key] = []
                continue
            result[key] = cleaned
        return result
    return value

def repair_json_file(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    cleaned = clean_json(payload)
    if cleaned is _REMOVED:
        cleaned = {} if isinstance(payload, dict) else []
    if cleaned == payload:
        return False
    atomic_write(path, json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n")
    return True

def repair_generation_cache(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    categories = payload.get("categories") if isinstance(payload, dict) else None
    if not isinstance(categories, dict):
        return False
    changed = False
    for key, entry in list(categories.items()):
        blob = json.dumps(entry, ensure_ascii=False).lower()
        false_ir = SLUG in blob or (
            "indian river county" in blob
            and "attacking father" in blob
            and ("palm beach" in blob or "emerald dunes" in blob)
        )
        shark_drift = (
            "/florida-sharks-caught-on-video-off-shore" in blob
            and any(term in blob for term in ("commissioners", "ordinance", "state order", "state directive"))
        )
        if false_ir or shark_drift:
            categories.pop(key, None)
            changed = True
    if changed:
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return changed

def _remove_matching_blocks(raw: str, tag: str) -> str:
    """Remove only sibling blocks that contain the withdrawn slug.

    The tempered body prevents a match from crossing an earlier closing tag.
    This is critical for RSS and sitemap files: a plain ``.*?`` can start at
    the first item and consume every sibling up to the target item.
    """
    pattern = re.compile(
        rf"\s*<{tag}\b[^>]*>(?:(?!</{tag}>).)*?</{tag}>\s*",
        re.I | re.S,
    )

    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        return "\n" if SLUG.lower() in block.lower() else block

    return pattern.sub(replace, raw)

def repair_xml(path: Path, tag: str) -> bool:
    if not path.exists():
        return False
    raw = path.read_text(encoding="utf-8", errors="ignore")
    updated = _remove_matching_blocks(raw, tag)
    if updated == raw:
        return False
    atomic_write(path, updated)
    return True

def strip_bad_blocks(raw: str) -> str:
    updated = raw
    for tag in ("section", "article", "li", "a"):
        updated = _remove_matching_blocks(updated, tag)
    return updated

def ensure_homepage_hero(raw: str) -> str:
    if 'data-cat-hero="all"' in raw or "data-cat-hero='all'" in raw:
        return raw
    match = re.search(r"<section\b[^>]*class=[\"'][^\"']*\bhero\b[^\"']*[\"'][^>]*data-cat-hero=[\"'](?!all)[^\"']+[\"'][^>]*>.*?</section>", raw, re.I | re.S)
    if not match:
        return raw
    clone = re.sub(r"data-cat-hero=[\"'][^\"']+[\"']", 'data-cat-hero="all"', match.group(0), count=1, flags=re.I)
    clone = re.sub(r"\sstyle=[\"'][^\"']*display\s*:\s*none;?[^\"']*[\"']", "", clone, count=1, flags=re.I)
    marker = re.search(r"<main\b[^>]*>", raw, re.I)
    if marker:
        return raw[:marker.end()] + "\n" + clone + raw[marker.end():]
    return raw

def repair_html_surfaces(root: Path) -> int:
    changed = 0
    for path in root.glob("*.html"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if SLUG not in raw:
            continue
        updated = strip_bad_blocks(raw)
        if path.name == "index.html":
            updated = ensure_homepage_hero(updated)
        if updated != raw:
            atomic_write(path, updated)
            changed += 1
    return changed

def verify(root: Path) -> None:
    article = root / "articles" / f"{SLUG}.html"
    page = article.read_text(encoding="utf-8", errors="ignore")
    if "noindex" not in page or "Article withdrawn" not in page:
        raise SystemExit("False-jurisdiction repair verification failed: withdrawn page missing")
    for name in ("archive.json", "data.json", "feed.xml", "sitemap.xml", "news-sitemap.xml", "index.html"):
        path = root / name
        if path.exists() and SLUG in path.read_text(encoding="utf-8", errors="ignore"):
            raise SystemExit(f"False-jurisdiction repair verification failed: {name} still references bad slug")

def repair(root: Path) -> dict[str, int | bool]:
    root = Path(root)
    json_changed = sum(repair_json_file(root / name) for name in ("archive.json", "data.json"))
    cache_changed = repair_generation_cache(root / "data" / "generation-cache.json")
    xml_changed = int(repair_xml(root / "feed.xml", "item"))
    xml_changed += int(repair_xml(root / "sitemap.xml", "url"))
    xml_changed += int(repair_xml(root / "news-sitemap.xml", "url"))
    html_changed = repair_html_surfaces(root)
    article = root / "articles" / f"{SLUG}.html"
    article_changed = not article.exists() or article.read_text(encoding="utf-8", errors="ignore") != REDIRECT_HTML
    if article_changed:
        atomic_write(article, REDIRECT_HTML)
    verify(root)
    return {"json_changed": json_changed, "cache_changed": bool(cache_changed), "xml_changed": xml_changed, "html_changed": html_changed, "article_changed": article_changed}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    args = parser.parse_args()
    result = repair(args.root)
    print("False-jurisdiction publication repair: " + json.dumps(result, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
