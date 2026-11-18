"""Regression: the school-review article retains its original image, distinct from the budget story."""
from __future__ import annotations

import json
import re
from pathlib import Path
from scripts.sync_editorial_image_archive import sync_archive

ROOT = Path(__file__).resolve().parents[1]
SCHOOL = "2026-11-18-st-lucie-county-schools-close-wednesday-as-superintendent-pledges-flood-review"
BUDGET = "2026-11-18-st-lucie-county-estimates-60-million-shortfall-as-crews-prepare-for-flooding-thr"
ORIGINAL = "https://images.treasurecoast.today/articles/13/13e0138e0196f87b7eaabbad515b2ba572d063df8816f4318141e33086a0b25a.jpg"
EDITOR_SELECTED = "https://treasurecoast.today/images/st-lucie-flooding.jpg"


def test_image_overrides_are_distinct():
    data = json.loads((ROOT / "data/article-image-overrides.json").read_text(encoding="utf-8"))
    assert data["overrides"][SCHOOL]["image_url"] == ORIGINAL
    assert data["overrides"][BUDGET]["image_url"] == EDITOR_SELECTED


def test_superintendent_article_restores_original_hero_and_social_images():
    html = (ROOT / "articles" / f"{SCHOOL}.html").read_text(encoding="utf-8")
    assert f'<figure class="article-hero-image"><img src="{ORIGINAL}"' in html
    assert f'<meta property="og:image" content="{ORIGINAL}">' in html
    assert f'<meta name="twitter:image" content="{ORIGINAL}">' in html
    assert f'"image":["{ORIGINAL}"]' in html
    assert EDITOR_SELECTED not in html


def test_school_home_and_social_surfaces_show_original_photo():
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    anchors = re.findall(
        r'<a\b[^>]*href="[^"]*/articles/' + re.escape(SCHOOL) + r'\.html"[^>]*>.*?</a>',
        home, re.I | re.S,
    )
    assert anchors and all(ORIGINAL in x for x in anchors if "<img " in x)
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    def school_images(v):
        if isinstance(v, list):
            return [i for e in v for i in school_images(e)]
        if isinstance(v, dict):
            if v.get("headline") == "St. Lucie schools superintendent pledges review after bus flooding incident":
                return [v["image_url"]]
            return [i for e in v.values() for i in school_images(e)]
        return []
    images = school_images(data)
    assert images and all(v == ORIGINAL for v in images)
    feed = (ROOT / "feed.xml").read_text(encoding="utf-8")
    matching = [s for s in re.findall(r"<item\b[^>]*>.*?</item>", feed, flags=re.I | re.S)
                if f"/articles/{SCHOOL}.html" in s]
    assert matching and all(f'<media:content url="{ORIGINAL}"' in i for i in matching)
    authority = json.loads((ROOT / "data/rss-social-image-authority.json").read_text(encoding="utf-8"))
    assert next(i for i in authority["items"] if i["slug"] == SCHOOL)["image_url"] == ORIGINAL


def test_ios_archive_restores_original_without_affecting_budget(tmp_path):
    (tmp_path / "data").mkdir()
    ledger = json.loads((ROOT / "data/article-image-overrides.json").read_text(encoding="utf-8"))
    (tmp_path / "data/article-image-overrides.json").write_text(json.dumps(ledger), encoding="utf-8")
    (tmp_path / "archive.json").write_text(json.dumps([
        {"slug": SCHOOL, "image_url": EDITOR_SELECTED},
        {"slug": BUDGET, "image_url": EDITOR_SELECTED},
    ]), encoding="utf-8")
    assert sync_archive(tmp_path) == (2, 1)
    rows = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert rows[0]["image_url"] == ORIGINAL
    assert rows[1]["image_url"] == EDITOR_SELECTED
    assert sync_archive(tmp_path) == (2, 0)
