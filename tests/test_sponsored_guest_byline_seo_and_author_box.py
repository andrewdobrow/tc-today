"""Sponsored guest columns preserve client bylines, SEO copy and photo attribution.

No production custom article is enqueued by this test. The client's actual
photographs are separate binary inputs and must be attached before publishing.
"""
from __future__ import annotations

import json
import re

from tests.test_sponsored_custom_article_carousel_v99 import _load_generate


HEADLINE = (
    "Florida's Roof Age Law: The Roof Inspection Treasure Coast Homeowners "
    "Can Request Before Replacing a Roof Over 15 Years Old"
)
BYLINE = (
    "By Mike McGilvary, Florida's Roof Age Law and Tile Roof Preservation Expert, "
    "Owner of Mike McGilvary Roofing, Inc., Florida Certified Roofing Contractor CCC1331721"
)
SUBHEAD = (
    "Under Florida Statute 627.7011, a homeowner with a roof 15 years or older "
    "can have it inspected before an insurer requires replacement. Here is what "
    "Martin and St. Lucie County homeowners should know, and what a proper "
    "roof inspection documents."
)
BASE = "https://treasurecoast.today/images/"
NAMES = [
    "florida-roof-age-law-aerial-tile-roof-inspection-palm-beach-county.jpg",
    "oceanfront-tile-roof-restoration-highland-beach-5-year-roof-certification.jpg",
    "tile-roof-valley-rebuild-new-underlayment-repair-not-replacement.jpg",
    "tile-roof-preservation-aerial-inspection-south-florida-community.jpg",
    "mike-mcgilvary-roofing-crew-palm-beach-county-tile-roof-specialists.jpg",
    "mike-mcgilvary-florida-roof-age-law-tile-roof-preservation-expert.jpg",
    "mike-mcgilvary-headshot-florida-certified-roofing-contractor-ccc1331721.jpg",
]


def _item():
    return {
        "headline": HEADLINE,
        "teaser": SUBHEAD,
        "subhead": SUBHEAD,
        "guest_byline": BYLINE,
        "guest_author_name": "Mike McGilvary",
        "seo_title": "Florida Roof Age Law: Roof Inspection Before Replacement",
        "seo_description": (
            "Florida's roof age law lets Treasure Coast homeowners with roofs over 15 "
            "years old get a roof inspection before replacement. What s. 627.7011 "
            "says and what to ask."
        ),
        "body": (
            "This article preserves the original guest column and its five questions "
            "for homeowners along the Treasure Coast before they replace a roof. "
            "[Florida roof age law resource page](https://mmroofrepair.com/florida-roof-age-law/)."
            "\n\n## About the Author\n\n"
            "Mike McGilvary offers [published columns and media coverage]"
            "(https://mmroofrepair.com/in-the-news/) and [mmroofrepair.com]"
            "(https://mmroofrepair.com/)."
        ),
        "image_url": BASE + NAMES[0],
        "image_credit": "Mike McGilvary Roofing, Inc.",
        "carousel_images": [
            {"url": BASE + n, "alt": f"Roof restoration photo {i}", "caption": f"Photo {i}: restoration detail"}
            for i, n in enumerate(NAMES[:6], 1)
        ],
        "guest_author_headshot": {
            "url": BASE + NAMES[6],
            "alt": "Headshot of Mike McGilvary, owner of Mike McGilvary Roofing Inc",
            "caption": "Author headshot: Mike McGilvary, Florida Certified Roofing Contractor CCC1331721.",
        },
        "sponsored": True,
        "sponsor_name": "Mike McGilvary Roofing, Inc.",
        "sponsor_url": "https://mmroofrepair.com/",
        "is_custom": True,
        "authoritative_custom": True,
        "first_published": "Tue, 03 Nov 2026 13:00:00 -0500",
    }


def test_guest_sponsor_disclosure_and_exact_guest_byline():
    g = _load_generate()
    item = _item()
    g._normalize_custom_presentation_fields(item)
    page = g.render_article_page(item, "Business & Development", "business", "2026-11-03", "guest-test")
    assert BYLINE in page
    assert page.count("Sponsored by ") == 1
    assert page.count("This article was produced in partnership with") == 1
    assert 'By <a href="/author/andrew-dobrow.html"' not in page
    assert '<meta property="article:author" content="Mike McGilvary">' in page
    assert '"author": {"@type": "Person", "name": "Mike McGilvary"}' in page
    assert '"sponsor": {"@type": "Organization", "name": "Mike McGilvary Roofing, Inc."' in page


def test_guest_subhead_and_exact_seo_metadata():
    g = _load_generate()
    page = g.render_article_page(_item(), "Business & Development", "business", "2026-11-03", "guest-test")
    assert '<title>Florida Roof Age Law: Roof Inspection Before Replacement</title>' in page
    assert "Florida&#x27;s roof age law lets Treasure Coast homeowners" in page
    assert 'class="article-guest-subhead"' in page
    assert SUBHEAD in page
    assert HEADLINE in page
    assert 'href="https://mmroofrepair.com/florida-roof-age-law/"' in page
    assert 'href="https://mmroofrepair.com/in-the-news/"' in page
    assert 'href="https://mmroofrepair.com/"' in page


def test_client_gallery_includes_six_slides_not_author_headshot():
    g = _load_generate()
    page = g.render_article_page(_item(), "Business & Development", "business", "2026-11-03", "guest-test")
    assert page.count('data-carousel-slide=') == 6
    assert 'data-carousel-counter>1 / 6</div>' in page
    assert all(f'src="{BASE}{name}"' in page for name in NAMES)
    assert 'class="article-guest-author-photo"' in page
    assert page.count('Photo: Mike McGilvary Roofing, Inc.') == 2
    assert "Author headshot: Mike McGilvary" in page
    assert 'alt="Headshot of Mike McGilvary' in page
    assert "Photo 1: restoration detail" in page


def test_existing_sponsored_and_non_sponsored_bylines_stay_unchanged():
    g = _load_generate()
    item = _item()
    for key in ("guest_byline", "guest_author_name", "guest_author_headshot",
                "seo_title", "seo_description", "subhead"):
        item.pop(key)
    page = g.render_article_page(item, "Business & Development", "business", "2026-11-03", "guest-test")
    assert 'Sponsored by <a href="https://mmroofrepair.com/"' in page
    assert 'article-guest-subhead' not in page.split("</style>")[-1]
    assert 'article-guest-author-photo' not in page.split("</style>")[-1]
    assert '<meta property="article:author" content="Andrew Dobrow">' in page
    assert 'By Mike McGilvary' not in page


def test_custom_guest_metadata_survives_archive_fields():
    source = open("scripts/generate.py", encoding="utf-8").read()
    for key in ("guest_byline", "guest_author_name", "subhead", "seo_title",
                "seo_description", "guest_author_headshot", "focus_keywords"):
        assert f'"{key}"' in source
    assert "existing[\"guest_author_headshot\"]" in source
