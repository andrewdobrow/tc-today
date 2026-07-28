import os
import sys
import types


if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser

if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _Anthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(
                create=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline test"))
            )

    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic

os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")

from scripts import generate


HOMETOWN_LOGO = (
    "https://bloximages.chicago2.vip.townnews.com/hometownnewstc.com/"
    "content/tncms/custom/image/12345678-site-logo.png"
)
ARTICLE_PHOTO = (
    "https://bloximages.chicago2.vip.townnews.com/hometownnewstc.com/"
    "content/tncms/assets/v3/editorial/8/aa/8aa-story-photo.jpg"
)


def _sports_item(headline: str, body: str = "") -> dict:
    return {
        "title": headline,
        "headline": headline,
        "source_title": headline,
        "body": body,
        "summary": body,
        "source_quality": "full",
        "feed_url": "https://www.wptv.com/sports.rss",
    }


def test_hometown_townnews_custom_asset_is_rejected_as_publisher_logo():
    assert (
        generate._source_image_rejection_reason(HOMETOWN_LOGO)
        == "publisher_logo_or_placeholder_url"
    )
    assert generate._is_real_source_image_url(HOMETOWN_LOGO) is False


def test_townnews_editorial_photo_is_not_blocked_by_domain_alone():
    assert generate._source_image_rejection_reason(ARTICLE_PHOTO) == ""
    assert generate._is_real_source_image_url(ARTICLE_PHOTO) is True


def test_og_fetch_skips_logo_and_uses_story_specific_twitter_image(monkeypatch):
    html = f"""
    <html><head>
      <meta property="og:image" content="{HOMETOWN_LOGO}">
      <meta property="og:image:alt" content="Hometown News Treasure Coast logo">
      <meta property="og:image:width" content="1200">
      <meta property="og:image:height" content="250">
      <meta name="twitter:image" content="{ARTICLE_PHOTO}">
    </head></html>
    """

    class Response:
        status_code = 200
        text = html

    monkeypatch.setattr(generate.requests, "get", lambda *a, **k: Response())
    image = generate.fetch_og_image(
        "https://www.hometownnewstc.com/news/martin/data-center-story.html",
        "Indiantown council rejects pause on data center applications",
    )
    assert image == ARTICLE_PHOTO


def test_cached_category_logo_is_cleared_before_reuse():
    category = {
        "hero": {
            "headline": "Indiantown council rejects pause on data center applications",
            "image_url": HOMETOWN_LOGO,
            "link": "https://www.hometownnewstc.com/news/martin/data-center-story.html",
        },
        "cards": [],
    }
    assert generate._sanitize_category_source_images(
        category, stage="category_cache_reuse"
    ) == 1
    assert category["hero"]["image_url"] == ""
    assert category["hero"]["image_rejection_reason"]


def test_archive_restore_never_restores_rejected_publisher_logo():
    item = {
        "headline": "Indiantown council rejects pause on data center applications",
        "_archived_slug": "2026-07-28-indiantown-data-center",
        "image_url": "",
    }
    archive = [
        {
            "slug": "2026-07-28-indiantown-data-center",
            "headline": item["headline"],
            "image_url": HOMETOWN_LOGO,
        }
    ]
    assert generate._restore_archive_source_image(item, archive) is False
    assert item["image_url"] == ""


def test_sports_zero_candidate_fast_recovery_skips_non_sports_pool():
    candidates = [
        _sports_item(
            "Vero Beach Museum of Art opens new exhibition",
            "The museum will welcome visitors to a new art exhibition.",
        ),
        _sports_item(
            "Sebastian Police host back-to-school fun day",
            "The community event will distribute school supplies.",
        ),
    ]
    assert generate._sports_zero_candidate_fast_recovery("sports", candidates) is True


def test_sports_fast_recovery_does_not_skip_real_mets_story():
    candidates = [
        _sports_item(
            "St. Lucie Mets pitcher Conner Ware named FSL Pitcher of the Week",
            "The pitcher struck out 12 batters over seven scoreless innings.",
        )
    ]
    assert generate._sports_zero_candidate_fast_recovery("sports", candidates) is False


def test_non_sports_categories_never_use_sports_fast_recovery():
    assert generate._sports_zero_candidate_fast_recovery("martin", []) is False


def test_archive_migration_rewrites_existing_logo_page(tmp_path, monkeypatch):
    slug = "2026-07-28-indiantown-data-center"
    replacement = "https://treasurecoast.today/images/editorial/martin/indiantown.webp"
    archive = [
        {
            "slug": slug,
            "headline": "Indiantown council rejects second attempt to pause data center applications",
            "category_key": "martin",
            "image_url": HOMETOWN_LOGO,
            "source_url": "https://www.hometownnewstc.com/news/martin/data-center-story.html",
        }
    ]
    (tmp_path / "archive.json").write_text(
        __import__("json").dumps(archive), encoding="utf-8"
    )
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / f"{slug}.html"
    page.write_text(
        f'<meta property="og:image" content="{HOMETOWN_LOGO}"><img src="{HOMETOWN_LOGO}">',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generate,
        "get_fallback_image",
        lambda *args, **kwargs: (replacement, ""),
    )

    report = generate.repair_archive_publisher_logo_images(tmp_path)
    assert report == {"updated": 1, "article_pages_updated": 1}
    repaired_archive = __import__("json").loads(
        (tmp_path / "archive.json").read_text(encoding="utf-8")
    )
    assert repaired_archive[0]["image_url"] == replacement
    repaired_page = page.read_text(encoding="utf-8")
    assert HOMETOWN_LOGO not in repaired_page
    assert replacement in repaired_page
