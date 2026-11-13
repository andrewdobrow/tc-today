"""Regression: editor photo overrides persist on already-published pages."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.reconcile_editorial_image_surfaces import reconcile

SLUG = "2026-11-13-sheriff-seeks-help-identifying-suspect-in-fort-pierce-store-burglary"
APPROVED = "https://treasurecoast.today/images/fort-pierce-mlk.jpg"
OLD = "https://images.treasurecoast.today/old-image.jpg"
OTHER = "https://images.treasurecoast.today/unrelated.jpg"


def test_reconciles_retained_article_cards_rss_and_ios_archive_without_touching_other_stories():
    with TemporaryDirectory() as folder:
        root = Path(folder)
        (root / "data").mkdir()
        (root / "articles").mkdir()
        (root / "fort-pierce").mkdir()
        (root / "data/article-image-overrides.json").write_text(
            json.dumps({"overrides": {SLUG: {"image_url": APPROVED}}})
        )
        (root / "archive.json").write_text(json.dumps([
            {"slug": SLUG, "image_url": OLD, "source_image_url": OLD},
            {"slug": "unrelated", "image_url": OTHER}
        ]))
        article = root / "articles" / (SLUG + ".html")
        article.write_text(
            '<meta property="og:image" content="' + OLD + '">'
            '<meta name="twitter:image" content="' + OLD + '">'
            '<script type="application/ld+json">{"image":["' + OLD + '"]}</script>'
            '<figure class="article-hero-image"><img src="' + OLD + '" alt=""></figure>'
            '<p>Preserve every word of the published article.</p>'
        )
        card = '<a href="/articles/' + SLUG + '.html"><img src="' + OLD + '"></a>'
        other_card = '<a href="/articles/another-story.html"><img src="' + OTHER + '"></a>'
        (root / "index.html").write_text(card + other_card)
        (root / "fort-pierce/index.html").write_text(card)
        (root / "feed.xml").write_text(
            "<rss><item><link>https://treasurecoast.today/articles/" + SLUG +
            '.html</link><media:content url="' + OLD + '"/></item>'
            '<item><link>https://treasurecoast.today/articles/unrelated.html</link>'
            '<media:content url="' + OTHER + '"/></item></rss>'
        )

        touched = reconcile(root)
        assert set(touched) == {
            "articles/" + SLUG + ".html", "index.html", "fort-pierce/index.html",
            "feed.xml", "archive.json",
        }
        html = article.read_text()
        assert f'<meta property="og:image" content="{APPROVED}">' in html
        assert f'<meta name="twitter:image" content="{APPROVED}">' in html
        assert f'<figure class="article-hero-image"><img src="{APPROVED}"' in html
        assert f'"image":["{APPROVED}"]' in html
        assert "Preserve every word of the published article." in html
        assert APPROVED in (root / "index.html").read_text()
        assert OTHER in (root / "index.html").read_text()
        assert APPROVED in (root / "fort-pierce/index.html").read_text()
        assert APPROVED in (root / "feed.xml").read_text()
        assert OTHER in (root / "feed.xml").read_text()
        rows = json.loads((root / "archive.json").read_text())
        assert rows[0]["image_url"] == APPROVED
        assert rows[1]["image_url"] == OTHER
        assert reconcile(root) == []
