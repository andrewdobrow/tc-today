"""Reader-support message must precede the article-end Kit signup, exactly once."""
from __future__ import annotations

from pathlib import Path

from scripts.sync_article_reader_support import START, END, normalize, update_article


NEWSLETTER = (
    '<aside class="newsletter-inline-slot newsletter-inline-slot--article" '
    'aria-label="Subscribe to the Morning Brief">'
    '<script async data-uid="30e15672d3" src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script>'
    '</aside>'
)


def _article(body="Ordinary news reporting."):
    return (
        '<html><head><title>Local reporting</title></head><body>'
        '<main class="article-main-column">'
        '<div class="article-body"><p>' + body + '</p></div>\n'
        '  ' + NEWSLETTER
        + '<div class="article-share">Share story</div></main></body></html>'
    )


def test_inserts_clear_one_time_support_appeal_before_newsletter():
    before = _article()
    after = update_article(before)
    assert START in after and END in after
    assert "Local news needs local support." in after
    assert "Support TCT Today" in after
    assert "Give any amount. No subscription required." in after
    assert after.index(START) < after.index('newsletter-inline-slot--article')
    assert after.index('newsletter-inline-slot--article') < after.index('article-share')
    assert after.count(NEWSLETTER) == 1
    assert "Ordinary news reporting." in after
    assert update_article(after) == after


def test_replaces_outdated_appeal_without_duplication():
    old = update_article(_article()).replace(
        "Local news needs local support.", "Old fundraising message"
    )
    updated = update_article(old)
    assert "Old fundraising message" not in updated
    assert updated.count(START) == 1
    assert updated.count(END) == 1
    assert update_article(updated) == updated


def test_redirect_and_page_without_article_newsletter_untouched():
    redirect = (
        '<html><head><meta http-equiv="refresh" content="0; url=/moved"></head>'
        '<body>' + NEWSLETTER + '</body></html>'
    )
    assert update_article(redirect) == redirect
    other = '<html><body><div class="article-body">Story</div></body></html>'
    assert update_article(other) == other


def test_sitewide_normalization_is_idempotent_and_preserves_articles(tmp_path):
    folder = tmp_path / "articles"
    folder.mkdir()
    (folder / "one.html").write_text(_article("One article."))
    (folder / "two.html").write_text(_article("Another article."))
    (folder / "redirect.html").write_text(
        '<html><head><meta http-equiv="refresh" content="0; url=/new"></head>'
        '<body>' + NEWSLETTER + '</body></html>'
    )
    assert normalize(tmp_path) == {"scanned": 3, "updated": 2}
    assert normalize(tmp_path) == {"scanned": 3, "updated": 0}
    for name in ("one", "two"):
        html = (folder / f"{name}.html").read_text()
        assert html.count('tct-article-reader-support"') == 1
        assert html.index(START) < html.index('newsletter-inline-slot--article')


def test_main_production_workflow_reconciles_after_generation_and_before_deploy():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/update.yml").read_text()
    assert workflow.index("- name: Generate news") < workflow.index(
        "python scripts/sync_article_reader_support.py"
    )
    assert workflow.index("python scripts/sync_article_reader_support.py") < workflow.index(
        "- name: Commit and push"
    )


def test_current_article_styles_contain_responsive_module():
    css = (Path(__file__).resolve().parents[1] / "style.css").read_text()
    assert ".tct-article-reader-support" in css
    assert ".tct-article-reader-support__button" in css
    assert "@media (max-width: 700px)" in css
