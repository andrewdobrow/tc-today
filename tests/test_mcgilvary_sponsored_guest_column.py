"""Client-ordered McGilvary guest column and sponsored presentation contract.

Image binaries are supplied separately; this regression guards the editorial
payload, image filenames, captions, page metadata and author credit.
"""
from __future__ import annotations
from html import unescape
import importlib
import json
import os
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG = "florida-roof-age-law-roof-inspection-treasure-coast-homeowners"
PREFIX = "https://treasurecoast.today/images/"
HEADLINE = (
    "Florida's Roof Age Law: The Roof Inspection Treasure Coast Homeowners "
    "Can Request Before Replacing a Roof Over 15 Years Old"
)
BYLINE = (
    "By Mike McGilvary, Florida's Roof Age Law and Tile Roof Preservation Expert, "
    "Owner of Mike McGilvary Roofing, Inc., Florida Certified Roofing Contractor CCC1331721"
)
GALLERY = [
    "florida-roof-age-law-aerial-tile-roof-inspection-palm-beach-county.jpg",
    "oceanfront-tile-roof-restoration-highland-beach-5-year-roof-certification.jpg",
    "tile-roof-valley-rebuild-new-underlayment-repair-not-replacement.jpg",
    "tile-roof-preservation-aerial-inspection-south-florida-community.jpg",
    "mike-mcgilvary-roofing-crew-palm-beach-county-tile-roof-specialists.jpg",
    "mike-mcgilvary-florida-roof-age-law-tile-roof-preservation-expert.jpg",
]
HEADSHOT = "mike-mcgilvary-headshot-florida-certified-roofing-contractor-ccc1331721.jpg"


def _article():
    queue = json.loads((ROOT / "custom_articles.json").read_text(encoding="utf-8"))
    matches = [row for row in queue if row.get("custom_id") == "mike-mcgilvary-florida-roof-age-law-sponsored-2026-11-03"]
    assert len(matches) == 1
    assert len(queue) == 1, "only the newly requested custom article belongs in the queue"
    return matches[0]


def _generator():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: None
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_exact_headline_subhead_byline_and_guest_column_copy():
    item = _article()
    assert item["slug"] == SLUG
    assert item["unique_slug"] is True
    assert item["headline"] == HEADLINE
    assert item["subhead"].startswith("Under Florida Statute 627.7011")
    assert item["byline"] == BYLINE
    assert item["seo_title"] == "Florida Roof Age Law: Roof Inspection Before Replacement"
    assert item["meta_description"].startswith("Florida's roof age law lets Treasure Coast homeowners")
    assert item["category"] == "business"
    assert item["sponsored"] is True
    assert item["sponsor_name"] == "Mike McGilvary Roofing, Inc."
    assert item["sponsor_url"] == "https://mmroofrepair.com/"
    assert item["publish_on"] == "2026-11-03"
    assert item["force_hero"] is False
    assert "What Florida's Roof Age Law Actually Says" in item["body"]
    assert "What a Proper Roof Inspection and Five-Year Roof Certification Should Document" in item["body"]
    assert "When Roof Replacement Is the Right Answer" in item["body"]
    assert "A certification is not a warranty" in item["body"]
    assert "more than 100 five-year roof certifications" in item["body"]
    assert "a [ten-page photographic record](https://treasurecoast.today/images/highland-beach-5-year-roof-certification-example-mike-mcgilvary-roofing.pdf)" in item["body"]
    assert "Learn more about the Florida roof age law at" in item["author_bio"]
    assert not re.search(r"\b(?:561|772)[-. ]\d{3}[-. ]\d{4}\b", item["body"])


def test_gallery_is_client_order_with_exact_captions_alt_text_and_separate_headshot():
    item = _article()
    assert item["image_url"] == PREFIX + GALLERY[0]
    assert [x["url"] for x in item["carousel_images"]] == [PREFIX + name for name in GALLERY]
    assert all(x["caption"] and x["alt"] for x in item["carousel_images"])
    assert item["image_credit"] == "Mike McGilvary Roofing, Inc."
    assert item["author_headshot_url"] == PREFIX + HEADSHOT
    assert HEADSHOT not in [x["url"] for x in item["carousel_images"]]
    assert "The original tiles are catalogued and reinstalled" in item["carousel_images"][2]["caption"]


def test_sponsored_guest_page_displays_authorship_seo_links_and_photo_box():
    g = _generator()
    item = _article()
    g._normalize_custom_presentation_fields(item)
    item["is_custom"] = True
    item["authoritative_custom"] = True
    item["first_published"] = "Tue, 03 Nov 2026 12:00:00 -0500"
    page = g.render_article_page(item, "Business & Development", "business", "2026-11-03", SLUG)
    assert '<title>Florida Roof Age Law: Roof Inspection Before Replacement</title>' in page
    assert '<meta name="description" content="Florida&#x27;s roof age law' in page or (
        '<meta name="description" content="Florida\'s roof age law' in page
    )
    assert "<h1 class=\"article-headline\">" + HEADLINE + "</h1>" in page
    assert item["subhead"] in page
    assert BYLINE in unescape(page)
    assert '"name": "Mike McGilvary"' in page
    assert 'content="Mike McGilvary"' in page
    assert 'class="article-contributor-card"' in page
    assert HEADSHOT in page
    assert page.count('data-carousel-slide=') == 6
    assert 'href="https://treasurecoast.today/images/highland-beach-5-year-roof-certification-example-mike-mcgilvary-roofing.pdf"' in page
    assert 'data-carousel-counter>1 / 6</div>' in page
    assert page.count('Sponsored by <a href="https://mmroofrepair.com/"') == 1
    assert page.count("This article was produced in partnership with") == 1
    assert page.count('rel="sponsored nofollow noopener noreferrer external"') >= 3
    for link in (
        "https://mmroofrepair.com/",
        "https://mmroofrepair.com/in-the-news/",
        "https://mmroofrepair.com/florida-roof-age-law/",
    ):
        assert 'href="' + link + '"' in page
    assert g.validate_custom_body_fidelity(item, page) is True


def test_old_sponsored_article_without_guest_fields_keeps_existing_byline_and_seo():
    g = _generator()
    example = json.loads(
        (ROOT / "tests/fixtures/packard_sponsored_2026_10_04.json").read_text()
    )
    example.update(is_custom=True, authoritative_custom=True, first_published="Sun, 04 Oct 2026 09:00:00 -0400")
    html = g.render_article_page(example, "Business & Development", "business", "2026-10-04", example["slug"])
    assert 'Sponsored by <a href="https://www.packardroofing.com/"' in html
    assert "article-contributor-card" in html  # class definition is harmless
    assert '<aside class="article-contributor-card"' not in html
    assert "<title>Three generations later" in html
    assert html.count("This article was produced in partnership with") == 1
