"""Regression: editor-selected flood photo for the Nov. 18 school review.

The native iOS app gets its thumbnail from archive.json; article HTML alone
is insufficient. The same photo must survive subsequent news regenerations.
"""
from __future__ import annotations

import json
from pathlib import Path
from scripts.sync_editorial_image_archive import sync_archive

ROOT = Path(__file__).resolve().parents[1]
SLUG = "2026-11-18-st-lucie-county-schools-close-wednesday-as-superintendent-pledges-flood-review"
IMAGE = "https://treasurecoast.today/images/st-lucie-flooding.jpg"
OLD_IMAGE = (
    "https://images.treasurecoast.today/articles/13/"
    "13e0138e0196f87b7eaabbad515b2ba572d063df8816f4318141e33086a0b25a.jpg"
)


def test_photo_exists_and_override_survives_news_generation():
    assert (ROOT / "images" / "st-lucie-flooding.jpg").is_file()
    payload = json.loads((ROOT / "data/article-image-overrides.json").read_text())
    assert payload["overrides"][SLUG]["image_url"] == IMAGE


def test_published_article_hero_schema_and_social_images_agree():
    article = (ROOT / "articles" / (SLUG + ".html")).read_text()
    assert f'<figure class="article-hero-image"><img src="{IMAGE}"' in article
    assert f'<meta property="og:image" content="{IMAGE}">' in article
    assert f'<meta name="twitter:image" content="{IMAGE}">' in article
    assert f'"image":["{IMAGE}"]' in article
    assert OLD_IMAGE not in article


def test_current_news_surfaces_use_editor_photo():
    home = (ROOT / "index.html").read_text()
    assert IMAGE in home
    assert OLD_IMAGE not in home
    data = json.loads((ROOT / "data.json").read_text())
    assert IMAGE in json.dumps(data)
    assert OLD_IMAGE not in json.dumps(data)
    feed = (ROOT / "feed.xml").read_text()
    item = next(x for x in feed.split("<item>") if f"/articles/{SLUG}.html" in x)
    assert f'<media:content url="{IMAGE}"' in item
    authority = json.loads((ROOT / "data/rss-social-image-authority.json").read_text())
    row = next(x for x in authority["items"] if x["slug"] == SLUG)
    assert row["image_url"] == IMAGE


def test_native_ios_archive_sync_applies_override(tmp_path):
    (tmp_path / "data").mkdir()
    ledger = json.loads((ROOT / "data/article-image-overrides.json").read_text())
    (tmp_path / "data/article-image-overrides.json").write_text(json.dumps(ledger))
    archive = [
        {"slug": SLUG, "image_url": OLD_IMAGE, "source_image_url": OLD_IMAGE},
        {"slug": "another-story", "image_url": "https://example.com/other.jpg"},
    ]
    (tmp_path / "archive.json").write_text(json.dumps(archive))
    found, changed = sync_archive(tmp_path)
    assert found == 1
    assert changed == 1
    rows = json.loads((tmp_path / "archive.json").read_text())
    assert rows[0]["image_url"] == IMAGE
    assert rows[0]["rss_social_image_url"] == IMAGE
    assert rows[0]["article_image_override"] is True
    assert rows[1] == archive[1]
    assert sync_archive(tmp_path) == (1, 0)
