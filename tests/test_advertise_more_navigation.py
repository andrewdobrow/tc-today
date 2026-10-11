"""Advertise must appear in the desktop More dropdown and mobile More drawer.

Navigation is built in scripts/generate.py, and the sitewide normalizer is
responsible for migrating retained story/standalone pages to that navigation.
"""

import ast
import html as html_lib
import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def _nav_helpers():
    tree = ast.parse((ROOT / "scripts" / "generate.py").read_text(encoding="utf-8"))
    categories = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CATEGORIES" for t in node.targets)
    )
    brief = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "MORNING_BRIEF_LANDING_URL" for t in node.targets)
    )
    names = {
        "_header_primary_cta_html", "_primary_navigation_html", "_mobile_navigation_html",
        "_masthead_newsletter_cta_html", "_live_masthead_script_html",
        "_site_header_html", "_normalize_primary_navigation_sitewide",
    }
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {
        "Path": Path,
        "re": re,
        "html_lib": html_lib,
        "CATEGORIES": ast.literal_eval(categories.value),
        "MEMBERSHIP_UI_ENABLED": True,
        "MEMBERSHIP_SUBSCRIBE_URL": "/subscribe.html",
    }
    exec(compile(ast.Module(body=[brief, *functions], type_ignores=[]), "generate.py", "exec"), namespace)
    return namespace


def _assert_links_and_active(header):
    doc = BeautifulSoup(header, "html.parser")
    desktop = doc.select_one("nav.category-nav--primary")
    mobile = doc.select_one("#tct-mobile-nav")
    assert desktop is not None and mobile is not None
    desktop_more = desktop.select_one(".nav-sections-menu .nav-sections-group:last-child")
    mobile_more = mobile.select_one(".mobile-nav-group--more")
    assert desktop_more is not None and mobile_more is not None
    for section in (desktop_more, mobile_more):
        links = section.select('a[href="/advertise.html"]')
        assert len(links) == 1
        assert links[0].get_text(strip=True) == "Advertise"
        assert links[0].get("aria-current") == "page"
    assert desktop.select_one(".nav-sections-toggle.active") is not None


def test_advertise_in_both_more_navigation_groups_with_active_state():
    helpers = _nav_helpers()
    _assert_links_and_active(helpers["_site_header_html"](active="advertise"))
    # On ordinary pages, same links are present but should not be marked active.
    doc = BeautifulSoup(helpers["_site_header_html"](active="news"), "html.parser")
    for link in doc.select('a[href="/advertise.html"]'):
        assert link.get("aria-current") is None


def test_advertise_page_retained_header_migrates_without_duplication(tmp_path):
    helpers = _nav_helpers()
    page = tmp_path / "advertise.html"
    page.write_text(
        '<html><head><link href="style.css" rel="stylesheet"></head><body>'
        '<header><nav class="category-nav"><a href="/">Top News</a>'
        '<a href="/events.html">Events</a></nav></header>'
        '<main><h1>Sponsorship opportunities</h1></main></body></html>',
        encoding="utf-8",
    )
    normalize = helpers["_normalize_primary_navigation_sitewide"]
    assert normalize(tmp_path) == {"scanned": 1, "updated": 1}
    rewritten = page.read_text(encoding="utf-8")
    assert "Sponsorship opportunities" in rewritten
    _assert_links_and_active(rewritten)
    assert normalize(tmp_path) == {"scanned": 1, "updated": 0}
