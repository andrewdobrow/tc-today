from __future__ import annotations

import importlib
import json
import os
import sys
import types
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ROOT / "custom_articles.json"


def _queue(_g=None):
    return json.loads(CUSTOM.read_text(encoding="utf-8"))


def _packard_item(g):
    # A historic sponsored release is an immutable regression fixture, not a
    # required member of the rotating live custom-article publication queue.
    item = json.loads((ROOT / "tests" / "fixtures" / "packard_sponsored_2026_10_04.json").read_text(encoding="utf-8"))
    item = dict(item)
    g._normalize_custom_presentation_fields(item)
    item["is_custom"] = True
    item["authoritative_custom"] = True
    item["first_published"] = "Sun, 04 Oct 2026 09:00:00 -0400"
    return item


def test_current_custom_queue_contains_only_weekend_article():
    queue = _queue()
    assert [row.get("custom_id") for row in queue] == ["treasure-coast-top-five-weekend-2026-10-10-11"]


def test_packard_article_is_scheduled_for_october_4_eastern():
    g = _load_generate()
    before = datetime(2026, 10, 3, 23, 59, tzinfo=ZoneInfo("America/New_York"))
    opening = datetime(2026, 10, 4, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    assert g._custom_publish_on_ready("2026-10-04", now_et=before) is False
    assert g._custom_publish_on_ready("2026-10-04", now_et=opening) is True


def test_packard_queue_payload_has_four_image_carousel_and_first_image_is_hero():
    g = _load_generate()
    item = _packard_item(g)
    assert item["sponsored"] is True
    assert item["sponsor_name"] == "Packard Roofing & Waterproofing"
    assert item["sponsor_url"] == "https://www.packardroofing.com/"
    assert item["image_url"] == "https://treasurecoast.today/images/packard1.jpg"
    assert [row["url"] for row in item["carousel_images"]] == [
        "https://treasurecoast.today/images/packard1.jpg",
        "https://treasurecoast.today/images/packard2.jpg",
        "https://treasurecoast.today/images/packard3.jpg",
        "https://treasurecoast.today/images/packard4.jpg",
    ]


def test_packard_page_uses_clean_two_disclosure_treatment_and_carousel():
    g = _load_generate()
    item = _packard_item(g)
    page = g.render_article_page(
        item,
        "Business & Development",
        "business",
        "2026-10-04",
        item["slug"],
    )

    assert '<span class="article-sponsored-badge">Sponsored</span>' not in page
    assert "Sponsored content is produced in partnership with the advertiser." not in page
    assert "<strong>Sponsored content</strong>" not in page
    assert page.count("Sponsored by <a href=\"https://www.packardroofing.com/\"") == 1
    assert page.count("This article was produced in partnership with ") == 1
    assert page.count("Packard Roofing &amp; Waterproofing") >= 2
    assert '"sponsor": {"@type": "Organization", "name": "Packard Roofing & Waterproofing"' in page
    assert page.count('rel="sponsored nofollow noopener noreferrer external"') >= 5

    assert page.count('data-carousel-slide=') == 4
    assert 'data-carousel-slide="0" aria-hidden="false"' in page
    assert 'src="https://treasurecoast.today/images/packard1.jpg"' in page
    assert 'src="https://treasurecoast.today/images/packard2.jpg"' in page
    assert 'src="https://treasurecoast.today/images/packard3.jpg"' in page
    assert 'src="https://treasurecoast.today/images/packard4.jpg"' in page
    assert 'data-carousel-prev' in page
    assert 'data-carousel-next' in page
    assert 'data-carousel-counter>1 / 4</div>' in page


def test_non_sponsored_article_keeps_standard_byline_and_single_hero():
    g = _load_generate()
    item = {
        "headline": "Ordinary custom article",
        "teaser": "Ordinary custom article teaser.",
        "body": "This is an ordinary custom article body with enough copy to render normally.",
        "image_url": "https://treasurecoast.today/images/example.jpg",
        "is_custom": True,
        "authoritative_custom": True,
        "first_published": "Sun, 04 Oct 2026 09:00:00 -0400",
    }
    page = g.render_article_page(item, "Business & Development", "business", "2026-10-04", "ordinary-custom")
    assert "Sponsored by" not in page
    assert "This article was produced in partnership with" not in page
    assert 'By <a href="/author/andrew-dobrow.html" rel="author">Andrew Dobrow</a>' in page
    assert '<figure class="article-hero-image article-image-carousel"' not in page
    assert '<figure class="article-hero-image"><img src="https://treasurecoast.today/images/example.jpg"' in page


def test_packard_render_passes_custom_body_fidelity_gate():
    g = _load_generate()
    item = _packard_item(g)
    page = g.render_article_page(
        item,
        "Business & Development",
        "business",
        "2026-10-04",
        item["slug"],
    )
    assert g.validate_custom_body_fidelity(item, page) is True


def test_packard_fidelity_is_independent_of_post_body_modules_and_extra_body_class():
    g = _load_generate()
    item = _packard_item(g)
    page = g.render_article_page(
        item,
        "Business & Development",
        "business",
        "2026-10-04",
        item["slug"],
    )
    page = page.replace(
        '<div class="article-body">',
        '<div class="article-body tct-member-preview">',
        1,
    )
    page = page.replace(
        '<p class="article-sponsored-partnership">',
        '<div class="tct-post-body-module" data-production-compat="true"></div>\n          <p class="article-sponsored-partnership">',
        1,
    )
    assert g.validate_custom_body_fidelity(item, page) is True
