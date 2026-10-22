"""Regression protection for TCT's October 21 Comcast sponsored custom story."""
from __future__ import annotations

import json
import re
import pytest
from pathlib import Path

from tests.test_sponsored_custom_article_carousel_v99 import _load_generate
from tct_engine.membership_paywall import is_paywall_exempt_slug, FULL_BODY_MARKER

ROOT = Path(__file__).resolve().parents[1]
CUSTOM_ID = "xfinity-stuart-comcast-sponsored-2026-10-21"
SLUG = "2026-10-21-new-xfinity-store-opens-in-stuart-comcast-announces-35000-grant-for-martin-county-pal"
URL_ROOT = "https://treasurecoast.today/images/xfinity-stuart"


def _article():
    matches = [row for row in json.loads((ROOT / "custom_articles.json").read_text(encoding="utf-8")) if row.get("custom_id") == CUSTOM_ID]
    # A sponsored custom release can leave the rotating queue after publishing.
    # Its published page remains in the archive; do not block future releases.
    if not matches:
        pytest.skip("Xfinity sponsored release has left the active editor queue")
    assert len(matches) == 1
    return matches[0]


def test_xfinity_sponsored_identity_date_and_dedicated_martin_category():
    item = _article()
    assert item["slug"] == SLUG
    # Keep the permanent story identity stable without freezing editable headline copy.
    # An approved sponsor headline may change while its canonical URL stays unchanged.
    headline = str(item.get("headline") or "").casefold()
    assert "xfinity" in headline and "stuart" in headline
    assert item["publish_on"] == "2026-10-21"
    assert item["category"] == "business"
    assert item["sponsored"] is True
    assert item["sponsor_name"] == "Comcast"
    assert item["sponsor_url"] == "https://www.xfinity.com/overview"
    assert not item["force_hero"]
    assert item["image_url"] == URL_ROOT + "1.jpg"
    assert [x["url"] for x in item["carousel_images"]] == [URL_ROOT + str(i) + ".jpg" for i in range(1,5)]


def test_xfinity_sponsored_story_keeps_exact_product_and_store_links():
    body = _article()["body"]
    urls = re.findall(r"\]\((https?://[^)]+)\)", body)
    assert len(urls) == 24
    for url in [
        "https://www.xfinity.com/overview",
        "https://www.xfinity.com/learn/internet-service",
        "https://www.xfinity.com/mobile/",
        "https://business.comcast.com/learn/mobile",
        "https://www.xfinity.com/learn/digital-cable-tv/x1",
        "https://www.xfinity.com/learn/home-solutions",
        "https://business.comcast.com/",
        "https://www.xfinity.com/support/contact-us",
        "https://www.xfinity.com/local/fl/stuart/3955-southeast-federal-highway.html",
        "https://www.xfinity.com/local/fl/stuart/2830-nw-federal-highway.html",
        "https://www.xfinity.com/local/fl/port-st--lucie/277-sw-port-st-lucie-blvd.html",
        "https://www.xfinity.com/local/fl/vero-beach/5840-20th-street.html",
    ]:
        assert url in urls
    for key in ["$35,000", "12 underserved", "200 people annually", "Project UP", "3955 Southeast Federal Highway", "9 a.m. – 8 p.m.", "10 a.m. – 6 p.m.", "**About Comcast Corporation**"]:
        assert key in body


def test_xfinity_native_page_has_four_slide_carousel_sponsor_disclosures_and_full_body():
    g = _load_generate()
    item = _article()
    g._normalize_custom_presentation_fields(item)
    item["is_custom"] = True
    item["authoritative_custom"] = True
    item["first_published"] = "Wed, 21 Oct 2026 12:00:00 -0400"
    page = g.render_article_page(item, "Business & Development", "business", "2026-10-21", item["slug"])
    assert page.count("data-carousel-slide=") == 4
    assert all(f'src="{URL_ROOT}{i}.jpg"' in page for i in range(1,5))
    assert "data-carousel-prev" in page and "data-carousel-next" in page
    assert 'data-carousel-counter>1 / 4</div>' in page
    assert page.count('Sponsored by <a href="https://www.xfinity.com/overview"') == 1
    assert page.count("This article was produced in partnership with") == 1
    assert '"sponsor": {"@type": "Organization", "name": "Comcast"' in page
    assert 'rel="sponsored nofollow noopener noreferrer external"' in page
    assert 'href="https://www.xfinity.com/local/fl/vero-beach/5840-20th-street.html"' in page
    assert g.validate_custom_body_fidelity(item, page) is True


def test_xfinity_is_freely_readable_like_packard_but_ordinary_articles_are_not():
    assert is_paywall_exempt_slug(SLUG)
    assert is_paywall_exempt_slug("2026-10-04-three-generations-later-packard-roofing-remains-rooted-on-the-treasure-coast")
    assert not is_paywall_exempt_slug("ordinary-editorial-story")


def test_membership_pipeline_does_not_paywall_xfinity_and_keeps_full_body(tmp_path, monkeypatch):
    import importlib.util
    g = _load_generate()
    item = _article()
    g._normalize_custom_presentation_fields(item)
    item["is_custom"] = True
    item["first_published"] = "Wed, 21 Oct 2026 12:00:00 -0400"
    articles = tmp_path / "articles"
    articles.mkdir()
    file = articles / f"{SLUG}.html"
    file.write_text(g.render_article_page(item, "Business & Development", "business", "2026-10-21", SLUG), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("prepare_membership_xfinity_test", ROOT / "scripts/prepare_membership_paywall.py")
    assert spec and spec.loader
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    monkeypatch.setattr(prepare, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(tmp_path / "protected.json"))
    monkeypatch.delenv("TCT_PROTECTED_SNAPSHOT_PATH", raising=False)
    prepare.main()
    public = file.read_text(encoding="utf-8")
    assert "data-tct-paywall" not in public
    assert "tct-member-preview" not in public
    assert "digital literacy and workforce skills" in public
    assert "9 a.m." in public and "8 p.m." in public
    assert json.loads((tmp_path / "protected.json").read_text(encoding="utf-8")) == {"articles": []}
