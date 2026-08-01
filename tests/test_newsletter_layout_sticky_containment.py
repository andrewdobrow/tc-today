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


def test_sticky_bar_promotes_outermost_kit_wrapper_above_masthead():
    css = _read("style.css")
    assert "body > .tct-kit-sticky-layer" in css
    assert "z-index: 2147483000 !important" in css
    assert ".tct-kit-sticky-form" in css
    assert "max-height: 58px !important" in css
    assert "grid-template-columns: minmax(0, 1fr) auto !important" in css


def test_sticky_bar_runtime_promotes_top_level_layer_and_reserves_space():
    js = _read("main.js")
    assert "function findTopLevelLayer(node)" in js
    assert 'layer.parentElement !== document.body' in js
    assert 'layer.classList.add("tct-kit-sticky-layer")' in js
    assert 'shell.classList.add("tct-kit-sticky-shell")' in js
    assert 'form.classList.add("tct-kit-sticky-form")' in js
    assert '"z-index": "2147483000"' in js
    assert 'root.classList.add("kit-sticky-visible")' in js
    assert 'root.classList.remove("kit-sticky-visible")' in js
    assert '--kit-sticky-height' in js
    assert "new MutationObserver(mutations =>" in js
    assert "new ResizeObserver(scheduleSync)" in js


def test_header_and_reading_progress_are_offset_below_visible_bar():
    css = _read("style.css")
    assert "html.kit-sticky-visible body" in css
    assert "html.kit-sticky-visible header" in css
    assert "html.kit-sticky-visible .article-reading-progress" in css


def test_sticky_layer_restores_kits_original_inline_styles_when_closed():
    js = _read("main.js")
    assert "const originalInlineStyles = new WeakMap()" in js
    assert "const promotedElements = new Set()" in js
    assert "snapshot.set(property" in js
    assert "element.style.setProperty(property, value, priority)" in js
    assert "originalInlineStyles.delete(element)" in js
