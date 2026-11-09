"""Kit owns the sitewide popup on desktop and mobile; inline signups remain."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sitewide_popup_is_html_embedded_not_manually_triggered():
    main = (ROOT / "main.js").read_text(encoding="utf-8")
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "be625cadfe" not in main
    assert "loadSitewideKitModal" not in main
    assert "showMobileSubscriptionModal" not in main
    assert ".tct-mobile-subscription-overlay" not in css
    assert ".tct-mobile-subscription-modal" not in css
    assert ".formkit-modal" not in css
    assert ".formkit-overlay" not in css


def test_newsletter_inline_signup_is_still_available():
    homepage = (ROOT / "index.html").read_text(encoding="utf-8")
    source = (ROOT / "scripts/generate.py").read_text(encoding="utf-8")
    assert 'data-uid="30e15672d3"' in homepage
    assert "_newsletter_inline_embed" in source


def test_generated_pages_include_official_kit_embed():
    audience = (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8")
    assert 'data-uid="be625cadfe"' in audience
    assert "NEWSLETTER_URL" in audience
