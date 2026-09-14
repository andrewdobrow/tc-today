from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_nextdoor_ios_detector_is_narrow_and_app_specific():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert "applyNextdoorIosMastheadCompatibility" in js
    assert r"/\bNextdoor(?:\/|\s|$)/i" in js
    assert r"/iPhone|iPad|iPod/i" in js
    assert 'platform === "MacIntel" && touchPoints > 1' in js
    assert 'classList.add("tct-nextdoor-ios")' in js
    # Do not broadly disable sticky headers for every iOS WKWebView.
    assert "-webkit-touch-callout" not in js


def test_only_nextdoor_ios_class_disables_sticky_masthead():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "v1.13.7.5v - Nextdoor iOS in-app browser sticky-header workaround" in css
    assert "html.tct-nextdoor-ios header.site-masthead" in css
    block = css.split("v1.13.7.5v - Nextdoor iOS in-app browser sticky-header workaround", 1)[1]
    assert "position: relative !important;" in block
    assert "top: auto !important;" in block
    # The failed .21 paint-shield approach is removed rather than stacked on top.
    assert "header.site-masthead::before" not in block
    assert "height: 220px" not in block


def test_standard_masthead_remains_sticky_everywhere_else():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "header.site-masthead {" in css
    standard = css.split("header.site-masthead {", 1)[1].split("}", 1)[0]
    assert "position: sticky;" in standard
    assert "top: 0;" in standard


def test_generated_and_retained_pages_cache_bust_nextdoor_fix():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/style.css?v=1.13.7.5v">' in source
    assert "'href=\"/style.css?v=1.13.7.5v\"'" in source
    assert 'src="/main.js?v=1.13.7.5v"' in source
