from pathlib import Path


def _style_text():
    return (Path(__file__).resolve().parents[1] / "style.css").read_text(encoding="utf-8")


def test_article_lists_restore_padding_after_global_reset():
    css = _style_text()
    assert ".article-body ul," in css
    assert ".article-body ol {" in css
    assert "padding-inline-start: 1.6rem;" in css
    assert "list-style-position: outside;" in css


def test_mobile_article_lists_keep_markers_inside_viewport_gutter():
    css = _style_text()
    marker = "TCT v1.13.9.76 — article list gutter / mobile bullet fix"
    section = css[css.index(marker):]
    assert "@media (max-width: 760px)" in section
    assert "padding-inline-start: 1.55rem;" in section
    assert "margin-left: 0;" in section
    assert "margin-right: 0;" in section


def test_related_and_navigation_lists_are_not_targeted():
    css = _style_text()
    marker = "TCT v1.13.9.76 — article list gutter / mobile bullet fix"
    section = css[css.index(marker):]
    assert ".related-list" not in section
    assert ".nav" not in section
