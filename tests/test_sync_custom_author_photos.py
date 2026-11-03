"""Regression: editing the custom queue must update an already-published portrait."""
import json
from pathlib import Path

import pytest

from scripts.sync_custom_author_photos import main, sync_author_photo

OLD = "https://treasurecoast.today/images/old-author.jpg"
NEW = "https://treasurecoast.today/images/new-author.jpg"
SLUG = "sponsor-roof-inspection"


def _html(url):
    return (
        "<html><main><div class=\"article-carousel-slide\"><img src=\""
        + OLD
        + "\"></div><aside class=\"article-contributor-card\" aria-label=\"About the author\">"
        + "<figure class=\"article-contributor-portrait\"><img "
        + 'class="article-contributor-headshot" src="'
        + url
        + '" alt="Author" loading="lazy"></figure></aside>'
        + "<p>Approved client copy remains unchanged.</p></main></html>"
    )


def test_existing_custom_author_image_is_updated_without_altering_carousel_or_copy(tmp_path):
    folder = tmp_path / "articles"
    folder.mkdir()
    page = folder / f"{SLUG}.html"
    page.write_text(_html(OLD))
    item = {"slug": SLUG, "author_headshot_url": NEW}
    assert sync_author_photo(item, folder) is True
    updated = page.read_text()
    assert 'class="article-contributor-headshot" src="' + NEW + '"' in updated
    assert '<div class="article-carousel-slide"><img src="' + OLD + '"' in updated
    assert "Approved client copy remains unchanged." in updated
    assert sync_author_photo(item, folder) is False


def test_new_custom_article_not_yet_published_is_left_for_generator(tmp_path):
    assert sync_author_photo({"slug": SLUG, "author_headshot_url": NEW}, tmp_path) is False


def test_unexpected_author_card_fails_closed(tmp_path):
    page = tmp_path / f"{SLUG}.html"
    page.write_text("<html><p>Do not damage content</p></html>")
    with pytest.raises(ValueError, match="author card"):
        sync_author_photo({"slug": SLUG, "author_headshot_url": NEW}, tmp_path)
    assert page.read_text() == "<html><p>Do not damage content</p></html>"


def test_unsafe_image_urls_are_rejected(tmp_path):
    for url in ("https://evil.example/img.jpg", "https://treasurecoast.today/other.jpg"):
        with pytest.raises(ValueError, match="Unsafe author headshot"):
            sync_author_photo({"slug": SLUG, "author_headshot_url": url}, tmp_path)


def test_main_reconciles_live_custom_queue(tmp_path):
    folder = tmp_path / "articles"
    folder.mkdir()
    (folder / f"{SLUG}.html").write_text(_html(OLD))
    (tmp_path / "custom_articles.json").write_text(json.dumps([{"slug": SLUG, "author_headshot_url": NEW}]))
    assert main(tmp_path) == 1
    assert NEW in (folder / f"{SLUG}.html").read_text()
