from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ios_inapp_browser_masthead_has_solid_offscreen_bleed_shield():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "v1.13.7.5u - iOS in-app browser masthead bleed shield" in css
    assert "@supports (-webkit-touch-callout: none)" in css
    assert "header.site-masthead::before" in css
    assert "bottom: 100%;" in css
    assert "height: 220px;" in css
    assert "background: var(--bg);" in css
    assert "pointer-events: none;" in css


def test_ios_bleed_fix_does_not_use_layout_offset_or_transform_hacks():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    block = css.split("v1.13.7.5u - iOS in-app browser masthead bleed shield", 1)[1]
    # The workaround must not push the page down or create a transformed sticky
    # ancestor; either can cause additional WKWebView sticky-position failures.
    assert "padding-top:" not in block
    assert "margin-top:" not in block
    assert "translateZ" not in block
    assert "backdrop-filter" not in block


def test_generated_and_retained_pages_cache_bust_the_bleed_fix():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/style.css?v=1.13.7.5u">' in source
    assert "'href=\"/style.css?v=1.13.7.5u\"'" in source
    # Existing pages without main.js are normalized with the same release token,
    # keeping the masthead assets on one coherent browser-cache generation.
    assert 'src="/main.js?v=1.13.7.5u"' in source
