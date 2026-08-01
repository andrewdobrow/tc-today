from pathlib import Path


def _newsletter_rule(css: str) -> str:
    start = css.index(".newsletter-inline-slot {")
    end = css.index("}", start)
    return css[start:end]


def test_inline_newsletter_wrapper_uses_standard_module_border_and_shadow():
    root = Path(__file__).resolve().parents[1]
    css = (root / "style.css").read_text()
    rule = _newsletter_rule(css)

    assert "border: 1px solid #e6e8e4;" in rule
    assert "box-shadow: var(--tct-shadow" in rule
    assert "overflow: hidden;" in rule
    assert "border-radius: 14px;" in rule


def test_inline_newsletter_border_is_shared_by_both_placements():
    root = Path(__file__).resolve().parents[1]
    css = (root / "style.css").read_text()
    rule = _newsletter_rule(css)

    # Both placements use the shared wrapper class rather than duplicating
    # border declarations in placement-specific selectors.
    assert "border: 1px solid #e6e8e4;" in rule
    assert ".lead-stack > .newsletter-inline-slot--category-hero" in css
    assert ".article-main-column > .newsletter-inline-slot" in css
    assert "newsletter-inline-slot newsletter-inline-slot--" in (
        root / "scripts" / "generate.py"
    ).read_text()
