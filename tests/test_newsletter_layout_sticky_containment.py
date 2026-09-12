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


def test_desktop_kit_modal_and_mobile_subscription_modal_replace_sticky_bar():
    js = _read("main.js")
    assert "RESPONSIVE ACQUISITION MODAL" in js
    assert 'uid: "be625cadfe"' in js
    assert 'mode: "desktop-newsletter-modal"' in js
    assert 'const MOBILE_DELAY_MS = 5000' in js
    assert "showMobileSubscriptionModal" in js
    assert "4edef44197" not in js
    assert "KIT STICKY BAR LAYERING" not in js
    assert "--kit-sticky-height" not in js


def test_mobile_subscription_modal_is_bounded_with_dismissible_backdrop_space():
    css = _read("style.css")
    responsive = css.index("TCT v1.13.8.9 - simple mobile subscription modal")
    tail = css[responsive:]
    assert '@media (max-width:680px)' in tail
    assert '.tct-mobile-subscription-modal' in tail
    assert 'width:min(100%,390px)' in tail
    assert 'padding:54px 22px 24px' in tail
    assert '.tct-mobile-subscription-close' in tail


def test_modal_layer_is_above_masthead_without_page_offset():
    css = _read("style.css")
    js = _read("main.js")
    assert "z-index: 2147483000 !important" in css
    assert "kit-sticky-visible" not in js
    assert "padding-top: var(--kit-sticky-height)" not in css[css.index("TCT v1.12.2.9"):]
