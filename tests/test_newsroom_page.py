from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    if "json_repair" not in sys.modules:
        json_repair = types.ModuleType("json_repair")
        json_repair.repair_json = lambda value, *args, **kwargs: value
        sys.modules["json_repair"] = json_repair
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = ROOT / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_newsroom_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_footer_points_to_newsroom_not_person_profile():
    g = _load_generate()
    footer = g._page_footer()
    assert '<a href="/newsroom.html">Newsroom</a>' in footer
    assert '>Author</a>' not in footer
    assert '<a href="/author/andrew-dobrow.html">Author</a>' not in footer


def test_newsroom_page_is_scalable_staff_directory_and_links_profile():
    g = _load_generate()
    page = g.render_newsroom_page()
    assert '<h1 class="newsroom-headline">Meet the Treasure Coast Today newsroom.</h1>' in page
    assert '<h2>Andrew Dobrow</h2>' in page
    assert 'Founder and Publisher' in page
    assert 'href="/author/andrew-dobrow.html"' in page
    assert 'View Andrew Dobrow\'s profile' in page
    assert '"@type": "CollectionPage"' in page or '"@type":"CollectionPage"' in page


def test_author_profile_links_back_to_newsroom_but_keeps_person_author_schema():
    g = _load_generate()
    page = g.render_author_page()
    assert 'href="/newsroom.html">&larr; Back to Newsroom</a>' in page
    assert '<span class="author-eyebrow">Newsroom</span>' in page
    assert 'Founder and Publisher, Treasure Coast Today' in page
    assert '"@type": "Person"' in page or '"@type":"Person"' in page


def test_retained_footers_are_migrated_from_author_to_newsroom(tmp_path):
    g = _load_generate()
    page = tmp_path / "legacy.html"
    page.write_text(
        '<html><body><footer><div class="footer-links">'
        '<a href="/about.html">About</a>'
        '<a href="/author/andrew-dobrow.html">Author</a>'
        '<a href="/archive.html">Archive</a>'
        '</div></footer></body></html>',
        encoding="utf-8",
    )
    result = g._normalize_footer_newsroom_link_sitewide(tmp_path)
    assert result == {"scanned": 1, "updated": 1}
    text = page.read_text(encoding="utf-8")
    assert '<a href="/newsroom.html">Newsroom</a>' in text
    assert '>Author</a>' not in text
    second = g._normalize_footer_newsroom_link_sitewide(tmp_path)
    assert second == {"scanned": 1, "updated": 0}


def test_newsroom_is_in_desktop_mobile_navigation_and_sitemap():
    g = _load_generate()
    desktop = g._primary_navigation_html(active="newsroom")
    mobile = g._mobile_navigation_html(active="newsroom")
    sitemap = g.update_sitemap([])
    assert 'href="/newsroom.html"' in desktop
    assert 'href="/newsroom.html"' in mobile
    assert 'https://treasurecoast.today/newsroom.html' in sitemap
    assert 'aria-current="page"' in desktop
    assert 'aria-current="page"' in mobile


def test_old_footer_without_author_gets_newsroom_inserted_after_about(tmp_path):
    g = _load_generate()
    page = tmp_path / "legacy-no-author.html"
    page.write_text(
        '<html><body><footer><div class="footer-links">'
        '<a href="about.html">About</a>'
        '<a href="archive.html">Archive</a>'
        '<a href="/feed.xml">RSS Feed</a>'
        '<a href="privacy.html">Privacy</a>'
        '</div></footer></body></html>',
        encoding="utf-8",
    )
    result = g._normalize_footer_newsroom_link_sitewide(tmp_path)
    assert result == {"scanned": 1, "updated": 1}
    text = page.read_text(encoding="utf-8")
    assert text.count('<a href="/newsroom.html">Newsroom</a>') == 1
    assert text.index('>About</a>') < text.index('>Newsroom</a>') < text.index('>Archive</a>')
    second = g._normalize_footer_newsroom_link_sitewide(tmp_path)
    assert second == {"scanned": 1, "updated": 0}


def test_very_old_footer_without_about_gets_newsroom_before_archive(tmp_path):
    g = _load_generate()
    page = tmp_path / "legacy-no-about.html"
    page.write_text(
        '<html><body><footer><div class="footer-links">'
        '<a href="https://treasurecoast.today/archive.html">Archive</a>'
        '<a href="/feed.xml">RSS Feed</a>'
        '<a href="https://treasurecoast.today/privacy.html">Privacy</a>'
        '</div></footer></body></html>',
        encoding="utf-8",
    )
    result = g._normalize_footer_newsroom_link_sitewide(tmp_path)
    assert result == {"scanned": 1, "updated": 1}
    text = page.read_text(encoding="utf-8")
    assert text.count('<a href="/newsroom.html">Newsroom</a>') == 1
    assert text.index('>Newsroom</a>') < text.index('>Archive</a>')
