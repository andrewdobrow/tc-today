"""Nov. 18 St. Lucie flood-preparation image editor override regression."""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.sync_editorial_image_archive import sync_archive

ROOT = Path(__file__).resolve().parents[1]
SLUG = "2026-11-18-st-lucie-county-estimates-60-million-shortfall-as-crews-prepare-for-flooding-thr"
IMAGE = "https://treasurecoast.today/images/st-lucie-flooding.jpg"
OLD = "https://images.treasurecoast.today/articles/4e/4e9944c6dc9760304b3772bf20727510b42d7d12f371e5110f821b4067307d5c.jpg"


def test_ledger_pins_editor_selected_photo():
    ledger = json.loads((ROOT / "data/article-image-overrides.json").read_text(encoding="utf-8"))
    assert ledger["overrides"][SLUG]["image_url"] == IMAGE


def test_article_hero_and_search_social_metadata_use_photo():
    article = (ROOT / "articles" / (SLUG + ".html")).read_text(encoding="utf-8")
    assert OLD not in article
    assert f'<meta property="og:image" content="{IMAGE}">' in article
    assert f'<meta name="twitter:image" content="{IMAGE}">' in article
    assert f'<figure class="article-hero-image"><img src="{IMAGE}"' in article
    assert f'"image":["{IMAGE}"]' in article


def test_rotating_home_and_feed_use_selected_image_only_when_story_is_present():
    # Homepage, feed, and data.json are finite rotating editorial surfaces.
    # An article may legitimately rotate off; only assert its image if selected.
    homepage = (ROOT / "index.html").read_text(encoding="utf-8")
    anchors = re.findall(
        r'<a\b[^>]*href="[^"]*/articles/' + re.escape(SLUG)
        + r'\.html"[^>]*>.*?</a>',
        homepage, re.I | re.S,
    )
    assert all(IMAGE in anchor for anchor in anchors if "<img " in anchor)
    feed = (ROOT / "feed.xml").read_text(encoding="utf-8")
    matching = [
        m.group(0) for m in re.finditer(r"<item\b[^>]*>.*?</item>", feed, flags=re.I | re.S)
        if f"/articles/{SLUG}.html" in m.group(0)
    ]
    assert all(IMAGE in item for item in matching)
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    def walk(value):
        if isinstance(value, dict):
            if value.get("headline") == "St. Lucie County estimates $60 million shortfall as crews prepare for flooding threat":
                assert value["image_url"] == IMAGE
                return 1
            return sum(walk(item) for item in value.values())
        if isinstance(value, list):
            return sum(walk(item) for item in value)
        return 0
    # A missing story is expected after editorial rotation; wrong photo is not.
    walk(data)


def test_ios_archive_override_sync_works_idempotently(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/article-image-overrides.json").write_text(
        json.dumps({"overrides": {SLUG: {"image_url": IMAGE}}}), encoding="utf-8"
    )
    (tmp_path / "archive.json").write_text(
        json.dumps([
            {"slug": SLUG, "image_url": OLD},
            {"slug": "unrelated", "image_url": OLD},
        ]), encoding="utf-8"
    )
    assert sync_archive(tmp_path) == (1, 1)
    rows = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert rows[0]["image_url"] == IMAGE
    assert rows[0]["rss_social_image_url"] == IMAGE
    assert rows[1]["image_url"] == OLD
    assert sync_archive(tmp_path) == (1, 0)
