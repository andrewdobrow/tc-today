"""Contract for paid Mike McGilvary roof-age-law guest column.

All media are URL references; the client uploads each asset separately.
The headshot is a distinct author-box asset, not a seventh carousel slide.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests.test_sponsored_custom_article_carousel_v99 import _load_generate

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = "https://treasurecoast.today/images/"
PDF_NAME = "highland-beach-5-year-roof-certification-example-mike-mcgilvary-roofing.pdf"
SLUG = "florida-roof-age-law-roof-inspection-treasure-coast-homeowners"
HEADLINE = (
    "Florida's Roof Age Law: The Roof Inspection Treasure Coast Homeowners "
    "Can Request Before Replacing a Roof Over 15 Years Old"
)
BYLINE = (
    "By Mike McGilvary, Florida's Roof Age Law and Tile Roof Preservation Expert, "
    "Owner of Mike McGilvary Roofing, Inc., Florida Certified Roofing Contractor CCC1331721"
)
IMAGES = [
    "florida-roof-age-law-aerial-tile-roof-inspection-palm-beach-county.jpg",
    "oceanfront-tile-roof-restoration-highland-beach-5-year-roof-certification.jpg",
    "tile-roof-valley-rebuild-new-underlayment-repair-not-replacement.jpg",
    "tile-roof-preservation-aerial-inspection-south-florida-community.jpg",
    "mike-mcgilvary-roofing-crew-palm-beach-county-tile-roof-specialists.jpg",
    "mike-mcgilvary-florida-roof-age-law-tile-roof-preservation-expert.jpg",
]
HEADSHOT = "mike-mcgilvary-headshot-florida-certified-roofing-contractor-ccc1331721.jpg"


def _payload():
    data = json.loads((ROOT / "custom_articles.json").read_text(encoding="utf-8"))
    assert len(data) == 1, "Custom queue should contain only the newly requested article"
    return data[0]


def _page():
    g = _load_generate()
    payload = _payload()
    g._normalize_custom_presentation_fields(payload)
    payload["is_custom"] = True
    payload["authoritative_custom"] = True
    payload["first_published"] = "Tue, 03 Nov 2026 12:30:00 -0500"
    return g, payload, g.render_article_page(payload, "Business & Development", "business", "2026-11-03", SLUG)


def test_exact_client_headline_subhead_guest_byline_and_sponsored_disclosure():
    g, payload, page = _page()
    assert payload["headline"] == HEADLINE
    assert payload["byline"] == BYLINE
    assert payload["subhead"].startswith("Under Florida Statute 627.7011")
    assert "<h1 class=\"article-headline\">" + HEADLINE + "</h1>" in page
    assert '<p class="article-guest-byline">' + BYLINE.replace("'", "'") + '</p>' in page
    assert payload["subhead"] in page
    assert page.count("Sponsored by <a href=") == 1
    assert page.count("This article was produced in partnership with ") == 1
    assert '<meta property="article:author" content="Mike McGilvary">' in page
    assert '"name": "Mike McGilvary"' in page
    assert g.validate_custom_body_fidelity(payload, page) is True


def test_six_client_images_in_exact_order_and_headshot_not_in_carousel():
    _, payload, page = _page()
    assert payload["image_url"] == IMAGE_ROOT + IMAGES[0]
    assert [p["url"] for p in payload["carousel_images"]] == [IMAGE_ROOT + file for file in IMAGES]
    assert all(p["alt"] and p["caption"] for p in payload["carousel_images"])
    assert page.count('data-carousel-slide=') == 6
    assert 'data-carousel-counter>1 / 6</div>' in page
    assert page.count('class="article-carousel-caption"') == 6
    carousel_urls = re.findall(r'<div class="article-carousel-slide[^>]*>.*?<img src="([^"]+)"', page, flags=re.S)
    assert carousel_urls == [IMAGE_ROOT + file for file in IMAGES]
    assert payload["author_headshot_url"] == IMAGE_ROOT + HEADSHOT
    assert f'<img src="{IMAGE_ROOT}{HEADSHOT}"' in page
    assert payload["author_headshot_url"] not in carousel_urls
    assert page.count('class="article-guest-author-box"') == 1
    assert "Author headshot: Mike McGilvary, Florida Certified Roofing Contractor CCC1331721." in page
    assert "Photo: Mike McGilvary Roofing, Inc." in page


def test_pdf_and_all_three_sponsor_links_live_with_no_call_to_action():
    _, payload, page = _page()
    pdf_url = IMAGE_ROOT + PDF_NAME
    assert f'href="{pdf_url}"' in page
    assert '<a href="' + pdf_url + '" target="_blank" rel="noopener">ten-page photographic record</a>' in page
    for url in (
        "https://mmroofrepair.com/florida-roof-age-law/",
        "https://mmroofrepair.com/in-the-news/",
        "https://mmroofrepair.com/",
    ):
        assert f'href="{url}"' in page
    assert "## About the Author" in payload["body"]
    assert "The McGilvary family has worked in roofing since 1974." in payload["body"]
    assert not re.search(r"\b(?:call now|call today|free estimate|coupon)\b", payload["body"], re.I)
    assert not re.search(r"\b(?:\d{3}[-.) ]+\d{3}[-. ]+\d{4})\b", payload["body"])


def test_exact_seo_title_description_and_focus_keywords():
    _, payload, page = _page()
    assert payload["slug"] == SLUG
    assert "<title>Florida Roof Age Law: Roof Inspection Before Replacement</title>" in page
    assert f'<meta name="description" content="{payload["meta_description"]}">' in page
    assert 'content="Florida roof age law, Florida Statute 627.7011, 15-year roof rule' in page
    assert f'<link rel="canonical" href="https://treasurecoast.today/articles/{SLUG}.html">' in page
    assert "Florida's roof age law lets Treasure Coast homeowners" in payload["meta_description"]
