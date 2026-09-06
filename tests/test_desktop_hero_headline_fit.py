from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STYLE_PATH = ROOT / "style.css"
GENERATOR_PATH = ROOT / "scripts" / "generate.py"

EXACT_LONG_HEADLINE = (
    "Three arrested in Fort Pierce after 3-month-old dies from dehydration "
    "and malnutrition in 'one of the worst cases' investigators have seen"
)


def _desktop_override() -> str:
    css = STYLE_PATH.read_text(encoding="utf-8")
    marker = "TCT v4.8 — natural desktop hero headline wrapping"
    assert marker in css
    return css.split(marker, 1)[1]


def test_exact_fort_pierce_headline_is_rendered_in_full():
    source = GENERATOR_PATH.read_text(encoding="utf-8")
    assert '<h1 class="hero-v3-headline">{hero["headline"]}</h1>' in source
    assert "headline[:" not in source[source.index("def hero_section"):source.index("heroes_html = hero_section")]
    assert len(EXACT_LONG_HEADLINE) > 120


def test_desktop_hero_is_content_height_driven_not_fixed_two_to_one():
    css = _desktop_override()
    assert "@media (min-width: 901px)" in css
    assert ".lead-primary" in css
    assert "aspect-ratio: auto !important" in css
    assert "height: auto !important" in css
    assert "max-height: none !important" in css
    assert "min-height: clamp(460px, 31vw, 600px) !important" in css


def test_desktop_headline_cannot_be_flex_shrunk_or_line_clamped():
    css = _desktop_override()
    headline_block = css.split(".hero-v3 .hero-v3-headline", 1)[1].split("}", 1)[0]
    assert "display: block !important" in headline_block
    assert "flex: 0 0 auto !important" in headline_block
    assert "overflow: visible !important" in headline_block
    assert "-webkit-line-clamp: unset !important" in headline_block
    assert "line-clamp: unset !important" in headline_block
    assert "text-overflow: clip !important" in headline_block


def test_desktop_copy_panel_can_expand_without_overlapping_media():
    css = _desktop_override()
    content_block = css.rsplit(".hero-v3-content {", 1)[1].split("}", 1)[0]
    assert "overflow: visible !important" in content_block
    assert "grid-template-columns" not in content_block
    assert ".hero-v3-media," in css
    assert "align-items: stretch !important" in css
    assert "min-height: 0 !important" in css


def test_stylesheet_url_is_cache_busted_for_release():
    source = GENERATOR_PATH.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/style.css?v=1.13.7.5q">' in source
