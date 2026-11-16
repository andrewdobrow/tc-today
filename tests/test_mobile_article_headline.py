"""Ensure mobile article headlines use the full available line width."""
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "style.css").read_text(encoding="utf-8")
MARKER = "/* TCT mobile article headline natural wrapping — 2026-11-14 */"


def test_mobile_article_headlines_do_not_balance_short_lines():
    assert MARKER in CSS
    rule = CSS.split(MARKER, 1)[1].split("/*", 1)[0]
    assert "@media (max-width: 600px)" in rule
    assert ".article-wrap .article-headline {" in rule
    assert "text-wrap: normal !important;" in rule


def test_mobile_fix_preserves_existing_typography():
    rule = CSS.split(MARKER, 1)[1].split("/*", 1)[0]
    for style in ("font-size:", "font-weight:", "line-height:", "letter-spacing:", "margin-bottom:"):
        assert style not in rule
    assert rule.count("@media") == 1
