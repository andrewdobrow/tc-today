import importlib.util
import os
import re
import sys
import types
from pathlib import Path


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(
                create=lambda *a, **k: (_ for _ in ()).throw(
                    RuntimeError("AI calls disabled in RSS image tests")
                )
            )
        )
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_rss_social_image_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


generate = _load_generate()


def _media_urls(feed_xml: str):
    return re.findall(r'<media:content url="([^"]+)" medium="image" />', feed_xml)


def test_social_image_resolver_prefers_verified_source_image_from_any_publisher_cdn():
    source = (
        "https://kubrick.htvapps.com/htv-prod/images/story-photo.jpg"
        "?crop=0.5xw&resize=1200:*"
    )
    item = {
        "category_key": "indian_river",
        "image_url": source,
    }

    assert generate._social_syndication_image_url(item) == source


def test_social_image_resolver_rejects_article_editorial_placeholder_for_category_og():
    item = {
        "category_key": "crime",
        "image_url": (
            "https://treasurecoast.today/images/editorial/"
            "cities/port-st-lucie/port-st-lucie-beautiful.webp"
        ),
    }

    assert generate._social_syndication_image_url(item) == (
        "https://treasurecoast.today/og-crime.png"
    )


def test_social_image_resolver_uses_category_og_when_image_is_missing_or_branded():
    assert generate._social_syndication_image_url(
        {"category_key": "martin", "image_url": ""}
    ) == "https://treasurecoast.today/og-martin.png"

    assert generate._social_syndication_image_url(
        {
            "category_key": "st_lucie",
            "image_url": "https://treasurecoast.today/og-image.png",
        }
    ) == "https://treasurecoast.today/og-st_lucie.png"


def test_rss_always_emits_explicit_source_or_category_og_image(tmp_path, monkeypatch):
    archive = [
        {
            "slug": "source-story",
            "headline": "Source image story",
            "teaser": "A story with a verified publisher image.",
            "category_key": "indian_river",
            "first_published": "Fri, 31 Jul 2026 09:00:00 -0400",
            "image_url": "https://kubrick.htvapps.com/htv-prod/images/source.jpg?resize=1200:*",
        },
        {
            "slug": "editorial-placeholder-story",
            "headline": "Editorial placeholder story",
            "teaser": "A story using a reusable on-page editorial image.",
            "category_key": "crime",
            "first_published": "Fri, 31 Jul 2026 08:00:00 -0400",
            "image_url": (
                "https://treasurecoast.today/images/editorial/"
                "topics/crime-public-safety/police-lights.webp"
            ),
        },
        {
            "slug": "missing-image-story",
            "headline": "Missing image story",
            "teaser": "A story with no source image.",
            "category_key": "martin",
            "first_published": "Fri, 31 Jul 2026 07:00:00 -0400",
            "image_url": "",
        },
    ]
    (tmp_path / "archive.json").write_text(
        __import__("json").dumps(archive), encoding="utf-8"
    )
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)

    feed = generate.render_rss_feed([], {}, max_items=10)
    urls = _media_urls(feed)

    assert len(urls) == 3
    assert any(url.startswith("https://kubrick.htvapps.com/") for url in urls)
    assert "https://treasurecoast.today/og-crime.png" in urls
    assert "https://treasurecoast.today/og-martin.png" in urls
    assert not any("/images/editorial/" in url for url in urls)
    assert not any("/images/fallback/" in url for url in urls)


def test_article_open_graph_uses_same_authoritative_social_image_policy():
    source_url = "https://kubrick.htvapps.com/htv-prod/images/source-story.jpg"
    source_page = generate.render_article_page(
        {
            "headline": "Publisher source image remains social image",
            "teaser": "A verified source image should appear in social metadata.",
            "body": "This is the confirmed article body with enough context for rendering.",
            "image_url": source_url,
            "first_published": "Fri, 31 Jul 2026 09:00:00 -0400",
        },
        "Indian River County",
        "indian_river",
        "2026-07-31",
        "source-image-story",
    )
    assert f'<meta property="og:image" content="{source_url}">' in source_page

    placeholder_page = generate.render_article_page(
        {
            "headline": "Editorial placeholder stays out of social metadata",
            "teaser": "The reusable article image must not become a social preview.",
            "body": "This is the confirmed article body with enough context for rendering.",
            "image_url": (
                "https://treasurecoast.today/images/editorial/"
                "cities/port-st-lucie/port-st-lucie-beautiful.webp"
            ),
            "first_published": "Fri, 31 Jul 2026 09:00:00 -0400",
        },
        "Crime & Safety",
        "crime",
        "2026-07-31",
        "placeholder-image-story",
    )
    assert (
        '<meta property="og:image" content="https://treasurecoast.today/og-crime.png">'
        in placeholder_page
    )


def test_runtime_rss_social_image_contract_passes_and_reports_counts(tmp_path, monkeypatch):
    archive = [
        {
            "slug": "verified-source",
            "headline": "Verified source",
            "teaser": "Verified source image story.",
            "category_key": "indian_river",
            "first_published": "Fri, 31 Jul 2026 09:00:00 -0400",
            "image_url": "https://kubrick.htvapps.com/htv-prod/images/source.jpg",
        },
        {
            "slug": "category-fallback",
            "headline": "Category fallback",
            "teaser": "Editorial placeholder story.",
            "category_key": "crime",
            "first_published": "Fri, 31 Jul 2026 08:00:00 -0400",
            "image_url": "https://treasurecoast.today/images/editorial/cities/stuart/stuart.webp",
        },
    ]
    import json

    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    (tmp_path / "feed.xml").write_text(
        generate.render_rss_feed([], {}, max_items=10), encoding="utf-8"
    )

    report = generate.validate_rss_social_image_contract(tmp_path)

    assert report["status"] == "passed"
    assert report["rss_items"] == 2
    assert report["source_images"] == 1
    assert report["category_og_images"] == 1
    assert (tmp_path / "data" / "rss-social-image-contract.json").exists()


def test_runtime_rss_social_image_contract_rejects_editorial_placeholder_leak(tmp_path):
    import json
    import pytest

    archive = [
        {
            "slug": "bad-image",
            "headline": "Bad image",
            "teaser": "This feed item is intentionally invalid.",
            "category_key": "crime",
            "first_published": "Fri, 31 Jul 2026 08:00:00 -0400",
            "image_url": "https://treasurecoast.today/images/editorial/cities/stuart/stuart.webp",
        }
    ]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (tmp_path / "feed.xml").write_text(
        """<?xml version="1.0"?><rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
        <item><guid>https://treasurecoast.today/articles/bad-image.html</guid>
        <media:content url="https://treasurecoast.today/images/editorial/cities/stuart/stuart.webp" medium="image" />
        </item></channel></rss>""",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="RSS social image contract FAILED"):
        generate.validate_rss_social_image_contract(tmp_path)

    report = json.loads(
        (tmp_path / "data" / "rss-social-image-contract.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "failed"
    assert report["issue_count"] >= 1


def test_live_source_enrichment_is_persisted_before_contract_validation(tmp_path, monkeypatch):
    import json

    source = "https://kubrick.htvapps.com/htv-prod/images/live-source.jpg"
    archive = [
        {
            "slug": "live-source-story",
            "headline": "Live source story",
            "teaser": "The archive still has an article-only placeholder.",
            "category_key": "crime",
            "first_published": "Fri, 31 Jul 2026 08:00:00 -0400",
            "image_url": (
                "https://treasurecoast.today/images/editorial/"
                "topics/crime-public-safety/police-lights.webp"
            ),
        }
    ]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "live-source-story.html").write_text(
        '''<html><head>
<meta property="og:image" content="https://treasurecoast.today/og-crime.png">
<meta name="twitter:image" content="https://treasurecoast.today/og-crime.png">
<script type="application/ld+json">{"@type":"NewsArticle","image":["https://treasurecoast.today/og-crime.png"]}</script>
</head><body><img src="https://treasurecoast.today/images/editorial/topics/crime-public-safety/police-lights.webp"></body></html>''',
        encoding="utf-8",
    )
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    categories = [
        {
            "category_key": "crime",
            "hero": {
                "slug": "live-source-story",
                "_archived_slug": "live-source-story",
                "headline": "Live source story",
                "category_key": "crime",
                "image_url": source,
            },
            "cards": [],
        }
    ]

    feed = generate.render_rss_feed(categories, {}, max_items=10)
    (tmp_path / "feed.xml").write_text(feed, encoding="utf-8")
    persisted = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))

    assert persisted[0]["image_url"].endswith("police-lights.webp")
    assert persisted[0]["source_image_url"] == source
    assert persisted[0]["social_image_source"] == "verified_live_article_source"
    assert source in feed

    page = (articles / "live-source-story.html").read_text(encoding="utf-8")
    assert f'<meta property="og:image" content="{source}">' in page
    assert f'<meta name="twitter:image" content="{source}">' in page
    assert 'police-lights.webp' in page  # visible article fallback remains untouched

    report = generate.validate_rss_social_image_contract(tmp_path)
    assert report["status"] == "passed"
    assert report["persisted_source_images"] == 1
    assert report["article_social_metadata_matches"] == 1


def test_category_og_sync_does_not_replace_visible_article_placeholder(tmp_path, monkeypatch):
    import json

    archive = [
        {
            "slug": "category-og-story",
            "headline": "Category OG story",
            "teaser": "No source image exists.",
            "category_key": "martin",
            "first_published": "Fri, 31 Jul 2026 08:00:00 -0400",
            "image_url": (
                "https://treasurecoast.today/images/editorial/"
                "cities/stuart/stuart.webp"
            ),
        }
    ]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "category-og-story.html").write_text(
        '''<html><head>
<meta property="og:image" content="https://treasurecoast.today/og-image.png">
<meta name="twitter:image" content="https://treasurecoast.today/og-image.png">
<script type="application/ld+json">{"@type":"NewsArticle","image":["https://treasurecoast.today/og-image.png"]}</script>
</head><body><img src="https://treasurecoast.today/images/editorial/cities/stuart/stuart.webp"></body></html>''',
        encoding="utf-8",
    )
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)

    feed = generate.render_rss_feed([], {}, max_items=10)
    (tmp_path / "feed.xml").write_text(feed, encoding="utf-8")
    page = (articles / "category-og-story.html").read_text(encoding="utf-8")

    assert "https://treasurecoast.today/og-martin.png" in feed
    assert '<meta property="og:image" content="https://treasurecoast.today/og-martin.png">' in page
    assert 'cities/stuart/stuart.webp' in page
    report = generate.validate_rss_social_image_contract(tmp_path)
    assert report["status"] == "passed"
