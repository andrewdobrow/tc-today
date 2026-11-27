"""Tests for the current advertising page and its retained workflow template."""
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "advertise.html"
TEMPLATE = ROOT / "content" / "advertise-page.html"
PACKARD_PATH = "/articles/2026-10-04-three-generations-later-packard-roofing-remains-rooted-on-the-treasure-coast.html"


def _check_sales_page(html: str):
    doc = BeautifulSoup(html, "html.parser")
    main = doc.select_one("main")
    assert main is not None
    sales = main.get_text(" ", strip=True)
    assert "Reach local readers. Grow your business." in sales
    assert "approximately 40,000 monthly website users" in sales
    assert "Your first Morning Brief newsletter sponsorship" in sales
    for item in (
        "$65", "$125", "$275", "$150", "$450", "$75", "$360",
        "Morning Brief Newsletter Sponsorship",
        "Sponsored Business Feature",
        "Website Display Advertising",
        "Podcast Sponsorship",
        "Featured Package",
        "We make advertising easy",
        "Email Andrew Dobrow",
    ):
        assert item in sales, item
    assert "Share your business's story in a dedicated sponsored article." in sales
    assert "clearly labeled" not in sales.lower()
    assert "clearly identified" not in sales.lower()
    assert "Sponsored content and paid placements are" not in sales
    assert "Sponsorship does not influence editorial coverage" not in sales
    assert "Scheduling and placement are subject to availability." not in sales
    assert doc.select_one('a[href^="mailto:andrew@treasurecoast.today?subject=Advertising"]') is not None
    assert doc.select_one('a[href^="mailto:andrew@treasurecoast.today?subject=Morning"]') is not None
    assert doc.select_one(f'a[href="{PACKARD_PATH}"]') is not None
    assert doc.select_one('a[href="/podcast/"]') is not None
    assert doc.select_one("form#advForm") is None


def test_public_and_retained_advertising_pages_match_current_offer():
    public = PAGE.read_text(encoding="utf-8")
    retained = TEMPLATE.read_text(encoding="utf-8")
    for html in (public, retained):
        _check_sales_page(html)
    # Any nav normalization can alter the page chrome, but sales content must match.
    public_main = BeautifulSoup(public, "html.parser").select_one("main")
    retained_main = BeautifulSoup(retained, "html.parser").select_one("main")
    assert str(public_main) == str(retained_main)


def test_workflow_restores_current_advertising_page_from_template():
    workflow = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
    assert "cp content/advertise-page.html advertise.html" in workflow
    assert workflow.index("python -u scripts/run_generator_fail_fast.py") < workflow.index(
        "cp content/advertise-page.html advertise.html"
    ) < workflow.index("python -u scripts/build_audience_features.py")


def test_sponsored_example_is_a_real_article():
    assert (ROOT / PACKARD_PATH.lstrip("/")).is_file()
