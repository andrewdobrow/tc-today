from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_homepage_lead_stack_contains_hero_and_newsletter_before_latest_rail():
    source = _read("scripts/generate.py")
    homepage = source.index('<main class="homepage-v2">')
    stack = source.index('<div class="lead-stack">', homepage)
    hero = source.index('<div class="lead-primary">{heroes_html}</div>', stack)
    newsletter = source.index('{_newsletter_inline_embed("category-hero")}', hero)
    rail = source.index('<aside class="latest-rail">', newsletter)
    layout_end = source.index('</div>\n    <section class="top-stories-v2">', rail)
    assert stack < hero < newsletter < rail < layout_end


def test_desktop_latest_rail_stretches_beside_hero_and_newsletter_stack():
    css = _read("style.css")
    assert "grid-template-columns: minmax(0, 1fr) 352px !important" in css
    assert ".lead-stack > .newsletter-inline-slot--category-hero" in css
    assert "align-self: stretch !important" in css
    assert "height: 100% !important" in css
    assert "overflow-y: auto !important" in css


def test_inline_newsletter_remains_without_sitewide_popup():
    js = _read("main.js")
    source = _read("scripts/generate.py")
    assert "be625cadfe" not in js
    assert "loadSitewideKitModal" not in js
    assert "_newsletter_inline_embed" in source
    assert "4edef44197" not in js


def test_kit_modal_overlay_is_not_styled_by_tct():
    css = _read("style.css")
    # Kit manages its popup layout, visibility and dismissal. Sitewide
    # overrides could capture touches over unrelated header controls.
    assert ".formkit-modal" not in css
    assert ".formkit-overlay" not in css
    assert '.formkit-form[data-format="modal"]' not in css


def test_retired_sticky_bar_does_not_shift_site_masthead():
    css = _read("style.css")
    js = _read("main.js")
    assert "kit-sticky-visible" not in js
    assert "--kit-sticky-height" not in js
