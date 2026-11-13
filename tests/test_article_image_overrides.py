from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG = '2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-missing-14-year-old-auti'
IMAGE = 'https://treasurecoast.today/images/ethan-boyd.png'


def _load_generate():
    spec = importlib.util.spec_from_file_location("tct_generate_image_override", ROOT / "scripts" / "generate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_override_ledger_contains_breaking_story():
    payload = json.loads((ROOT / "data" / "article-image-overrides.json").read_text())
    assert payload["overrides"][SLUG]["image_url"] == IMAGE


def test_override_applies_to_exact_slug_and_social_fields():
    generate = _load_generate()
    item = {"slug": SLUG, "image_url": "https://treasurecoast.today/og-martin.png"}
    assert generate._apply_article_image_override(item) is True
    assert item["image_url"] == IMAGE
    assert item["source_image_url"] == IMAGE
    assert item["rss_social_image_url"] == IMAGE
    assert item["social_image_is_source"] is True


def test_unrelated_article_is_untouched():
    generate = _load_generate()
    item = {"slug": "2026-08-06-unrelated-story", "image_url": "https://example.com/photo.jpg"}
    assert generate._apply_article_image_override(item) is False
    assert item["image_url"] == "https://example.com/photo.jpg"


def test_current_surfaces_use_selected_image():
    archive = json.loads((ROOT / "archive.json").read_text())
    row = next(row for row in archive if row.get("slug") == SLUG)
    assert row["image_url"] == IMAGE
    assert row["source_image_url"] == IMAGE

    article = (ROOT / "articles" / f"{SLUG}.html").read_text()
    assert f'<meta property="og:image" content="{IMAGE}">' in article
    assert f'<meta name="twitter:image" content="{IMAGE}">' in article
    assert f'<figure class="article-hero-image"><img src="{IMAGE}"' in article

    homepage = (ROOT / "index.html").read_text()
    target_path = re.escape(f"/articles/{SLUG}.html")
    placements = re.findall(
        rf'<a\b(?=[^>]*href="(?:https://treasurecoast\.today)?{target_path}")[^>]*>.*?</a>',
        homepage,
        flags=re.DOTALL,
    )
    # Homepage membership is intentionally transient. If this historical
    # story is currently placed there, any placement that renders an image
    # must use the selected override; rotating off the homepage is not an
    # image-regression failure.
    image_placements = [placement for placement in placements if re.search(r"<img\b", placement)]
    assert all(IMAGE in placement for placement in image_placements)

    # RSS is also a rolling surface. Preserve the same contract when the
    # story is present without requiring an old article to remain in the
    # current feed forever.
    feed = (ROOT / "feed.xml").read_text()
    feed_items = re.findall(r"<item>.*?</item>", feed, flags=re.DOTALL)
    targets = [
        item
        for item in feed_items
        if f"/articles/{SLUG}.html" in item
    ]
    assert all(IMAGE in item for item in targets)


BURGLARY_SLUG = "2026-11-13-sheriff-seeks-help-identifying-suspect-in-fort-pierce-store-burglary"
BURGLARY_IMAGE = "https://treasurecoast.today/images/fort-pierce-mlk.jpg"


def test_fort_pierce_burglary_image_override_survives_regeneration():
    payload = json.loads((ROOT / "data" / "article-image-overrides.json").read_text())
    assert payload["overrides"][BURGLARY_SLUG]["image_url"] == BURGLARY_IMAGE
    generate = _load_generate()
    item = {"slug": BURGLARY_SLUG, "image_url": "https://example.com/old.jpg"}
    assert generate._apply_article_image_override(item) is True
    assert item["image_url"] == BURGLARY_IMAGE
    assert item["source_image_url"] == BURGLARY_IMAGE
    assert item["rss_social_image_url"] == BURGLARY_IMAGE


def test_fort_pierce_burglary_live_article_and_social_surfaces_use_approved_image():
    article = (ROOT / "articles" / f"{BURGLARY_SLUG}.html").read_text()
    assert f'<meta property="og:image" content="{BURGLARY_IMAGE}">' in article
    assert f'<meta name="twitter:image" content="{BURGLARY_IMAGE}">' in article
    assert f'<figure class="article-hero-image"><img src="{BURGLARY_IMAGE}"' in article

    homepage = (ROOT / "index.html").read_text()
    items = re.findall(
        r'<a\b[^>]*href="[^"]*'
        + re.escape(f"/articles/{BURGLARY_SLUG}.html")
        + r'"[^>]*>.*?</a>',
        homepage,
        re.DOTALL,
    )
    assert all(BURGLARY_IMAGE in item for item in items if "<img " in item)
    city = (ROOT / "fort-pierce" / "index.html").read_text()
    assert BURGLARY_IMAGE in city
    feed = (ROOT / "feed.xml").read_text()
    entries = re.findall(r"<item>.*?</item>", feed, re.DOTALL)
    assert all(BURGLARY_IMAGE in item for item in entries if BURGLARY_SLUG in item)

