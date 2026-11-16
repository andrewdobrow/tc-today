"""Zoomed Android / in-app mobile masthead must not let Support obscure TCT."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_zoom_masthead_has_shrinkable_center_and_compact_support_fallback():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    section = css.split("Mobile masthead — screen zoom and enlarged-text containment", 1)[1]
    assert "grid-template-columns: max-content minmax(0, 1fr) max-content !important;" in section
    assert ".site-masthead .header-top" in section
    assert "overflow: hidden;" in section
    assert "@media (max-width: 440px)" in section
    assert 'content: "Support";' in section
    assert ".site-masthead .tct-donate-header .membership-subscribe-label" in section
    assert "display: none !important;" in section
    assert "@media (max-width: 315px)" in section
    assert "min-height: 44px !important;" in section
    assert "content: none;" in section
    assert "@media (max-width: 265px)" in section


def test_podcast_header_retains_accessible_full_support_label_and_correct_link():
    html = (ROOT / "podcast/index.html").read_text(encoding="utf-8")
    assert 'class="support-btn membership-subscribe-btn tct-donate-header"' in html
    assert 'aria-label="Support Treasure Coast Today"' in html
    assert 'href="https://donate.stripe.com/4gM5kw9LWfRb7uV6P34ZG01"' in html
    assert '<span class="membership-subscribe-label">Support TCT</span>' in html


def test_page_and_shared_asset_versions_refresh_zoom_styles():
    builder = (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8")
    assert 'ASSET_VERSION = "1.13.9.128"' in builder
    for path in ("index.html", "events.html", "news-tip.html", "podcast/index.html"):
        html = (ROOT / path).read_text(encoding="utf-8")
        assert '/style.css?v=1.13.9.128' in html
