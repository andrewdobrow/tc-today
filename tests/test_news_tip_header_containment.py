from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_news_tip_semantic_header_is_not_sticky():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    marker = "v1.13.9.93 — News Tip semantic-header containment"
    assert marker in css
    block = css.split(marker, 1)[1].split("event-detail-facts", 1)[0]
    assert ".news-tip-page > .news-tip-shell > .news-tip-hero" in block
    assert "position: static;" in block
    assert "top: auto;" in block
    assert "z-index: auto;" in block


def test_real_site_masthead_stays_sticky():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "header.site-masthead {" in css
    masthead = css.split("header.site-masthead {", 1)[1].split("}", 1)[0]
    assert "position: sticky;" in masthead
    assert "z-index: 100;" in masthead


def test_news_tip_page_uses_fresh_asset_version():
    html = (ROOT / "news-tip.html").read_text(encoding="utf-8")
    builder = (ROOT / "scripts" / "build_audience_features.py").read_text(encoding="utf-8")
    assert '/style.css?v=1.13.9.44' in html
    assert '/main.js?v=1.13.9.44' in html
    assert 'ASSET_VERSION = "1.13.9.44"' in builder


def test_news_tip_generator_keeps_semantic_header_contract():
    builder = (ROOT / "scripts" / "build_audience_features.py").read_text(encoding="utf-8")
    assert '<header class="news-tip-hero">' in builder
