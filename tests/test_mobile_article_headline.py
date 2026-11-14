"""Prevent oversized, cramped article headlines on narrow phones."""
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "style.css").read_text(encoding="utf-8")


def test_mobile_article_headline_has_proportional_size_and_relaxed_line_height():
    section = CSS.split("/* TCT mobile article headline rhythm — 2026-11-14 */", 1)[1]
    assert "@media (max-width: 600px)" in section
    assert ".article-wrap .article-headline {" in section
    assert "font-size: clamp(29px, 7.5vw, 32px) !important;" in section
    assert "font-weight: 700 !important;" in section
    assert "line-height: 1.14 !important;" in section
    assert "text-wrap: pretty !important;" in section


def test_mobile_fix_does_not_mutate_desktop_article_headlines():
    section = CSS.split("/* TCT mobile article headline rhythm — 2026-11-14 */", 1)[1]
    assert section.count("@media (max-width: 600px)") == 1
    assert "@media (min-width:" not in section
