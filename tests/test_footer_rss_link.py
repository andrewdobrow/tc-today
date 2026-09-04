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
    spec = importlib.util.spec_from_file_location("generate_footer_rss_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_standard_footer_exposes_existing_rss_feed_after_archive():
    g = _load_generate()
    footer = g._page_footer()
    archive = '<a href="/archive.html">Archive</a>'
    rss = '<a href="/feed.xml" type="application/rss+xml">RSS Feed</a>'
    assert footer.count(rss) == 1
    assert footer.index(archive) < footer.index(rss)
    assert (ROOT / "feed.xml").exists()


def test_retained_footer_migration_covers_modern_legacy_and_membership_footers(tmp_path):
    g = _load_generate()
    pages = {
        "modern.html": (
            '<html><body><footer><div class="footer-links">'
            '<a href="/archive.html">Archive</a><a href="/privacy.html">Privacy</a>'
            '</div></footer></body></html>'
        ),
        "legacy.html": (
            '<html><body><footer><div class="footer-links">'
            '<a href="https://treasurecoast.today/archive.html">Archive</a>'
            '<a href="https://treasurecoast.today/privacy.html">Privacy</a>'
            '</div></footer></body></html>'
        ),
        "membership.html": (
            '<html><body><footer class="membership-landing-footer"><nav>'
            '<a href="/corrections-policy.html">Corrections</a>'
            '<a href="/privacy.html">Privacy</a><a href="/contact.html">Contact</a>'
            '</nav></footer></body></html>'
        ),
    }
    for name, text in pages.items():
        (tmp_path / name).write_text(text, encoding="utf-8")

    result = g._normalize_footer_rss_link_sitewide(tmp_path)
    assert result == {"scanned": 3, "updated": 3}

    for name in pages:
        text = (tmp_path / name).read_text(encoding="utf-8")
        footer = text[text.index("<footer"):text.index("</footer>")]
        assert footer.count('href="/feed.xml"') == 1
        assert footer.count("RSS Feed") == 1

    second = g._normalize_footer_rss_link_sitewide(tmp_path)
    assert second == {"scanned": 3, "updated": 0}


def test_footer_migration_does_not_treat_nonfooter_feed_link_as_sufficient(tmp_path):
    g = _load_generate()
    page = tmp_path / "page.html"
    page.write_text(
        '<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head>'
        '<body><a href="/feed.xml">RSS elsewhere</a>'
        '<footer><div class="footer-links"><a href="/archive.html">Archive</a></div></footer>'
        '</body></html>',
        encoding="utf-8",
    )
    result = g._normalize_footer_rss_link_sitewide(tmp_path)
    assert result == {"scanned": 1, "updated": 1}
    text = page.read_text(encoding="utf-8")
    footer = text[text.index("<footer"):text.index("</footer>")]
    assert footer.count('href="/feed.xml"') == 1
    assert "RSS Feed" in footer
