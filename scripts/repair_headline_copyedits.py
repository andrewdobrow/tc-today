"""Apply exact-match headline copyedits without locking future editorial updates.

This small idempotent repair runs in both regular Update and Deploy Only, so
the archived story, its canonical HTML and the front page/news surfaces agree.
Only an exact *old* headline is replaced; a subsequent material update with a
different headline will not be overwritten.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "data/headline-copyedits.json"


def repair(root: Path = ROOT) -> dict[str, int]:
    root = Path(root)
    config = root / CONFIG
    if not config.is_file():
        return {"scanned": 0, "updated": 0}
    payload = json.loads(config.read_text(encoding="utf-8"))
    corrections = payload.get("corrections", [])
    paths = {
        root / "archive.json",
        root / "data.json",
        root / "index.html",
        root / "feed.xml",
        root / "news-sitemap.xml",
    }
    for entry in corrections:
        slug = str(entry["slug"]).strip()
        if not slug or "/" in slug or "\\" in slug or ".." in slug:
            raise ValueError("Invalid article slug in headline copyedit")
        paths.add(root / "articles" / (slug + ".html"))
    scanned = updated = 0
    for path in sorted(paths):
        if not path.is_file():
            continue
        scanned += 1
        before = path.read_text(encoding="utf-8")
        after = before
        for entry in corrections:
            old = str(entry["from"])
            new = str(entry["to"])
            if not old or not new or old == new:
                raise ValueError("Invalid headline copyedit mapping")
            after = after.replace(old, new)
        if after != before:
            path.write_text(after, encoding="utf-8")
            updated += 1
    print(f"Headline copyedits: scanned={scanned}, updated={updated}")
    return {"scanned": scanned, "updated": updated}


if __name__ == "__main__":
    repair()
