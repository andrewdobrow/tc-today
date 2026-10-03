import importlib.util
import os
import sys
import types
from pathlib import Path

if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser
if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")
    anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda *a, **k: None))
    sys.modules["anthropic"] = anthropic
os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tct_generate_image_mirror", ROOT / "scripts" / "generate.py")
generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate)


class FakeMirror:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []
    def mirror(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.decision)


def test_render_hook_preserves_publisher_provenance_in_mirror_mode(monkeypatch):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    monkeypatch.setenv("BUNNY_CDN_BASE_URL", "https://images.treasurecoast.today")
    fake = FakeMirror({
        "status": "mirrored",
        "action": "uploaded",
        "public_url": "https://images.treasurecoast.today/articles/aa/hash.jpg",
        "storage_key": "articles/aa/hash.jpg",
        "sha256": "hash",
    })
    monkeypatch.setattr(generate, "get_article_image_mirror", lambda root: fake)
    item = {
        "headline": "Test story",
        "image_url": "https://publisher.test/photo.jpg",
        "source_image_url": "https://publisher.test/photo.jpg",
        "source_url": "https://publisher.test/story",
    }
    assert generate._mirror_article_image_for_render(item, slug="2026-10-02-test") is True
    assert item["source_image_url"] == "https://publisher.test/photo.jpg"
    assert item["hosted_image_url"] == "https://images.treasurecoast.today/articles/aa/hash.jpg"
    assert item["image_url"] == item["hosted_image_url"]
    assert fake.calls[0]["slug"] == "2026-10-02-test"


def test_social_resolver_uses_hosted_only_in_mirror_mode(monkeypatch):
    item = {
        "source_image_url": "https://publisher.test/photo.jpg",
        "hosted_image_url": "https://images.treasurecoast.today/articles/aa/hash.jpg",
        "image_url": "https://publisher.test/photo.jpg",
    }
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "shadow")
    assert generate._social_syndication_image_url(item, "local_gov") == item["source_image_url"]
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    assert generate._social_syndication_image_url(item, "local_gov") == item["hosted_image_url"]


def test_rendered_article_hero_and_social_metadata_share_bunny_url(monkeypatch):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    monkeypatch.setenv("BUNNY_CDN_BASE_URL", "https://images.treasurecoast.today")
    hosted = "https://images.treasurecoast.today/articles/aa/hash.jpg"
    fake = FakeMirror({
        "status": "mirrored",
        "action": "registry_hit",
        "public_url": hosted,
        "storage_key": "articles/aa/hash.jpg",
        "sha256": "hash",
    })
    monkeypatch.setattr(generate, "get_article_image_mirror", lambda root: fake)
    monkeypatch.setattr(generate, "_article_banner_html_for_context", lambda *a, **k: "")
    hero = {
        "headline": "Mirrored test story",
        "teaser": "A test.",
        "body": "A complete test paragraph for article rendering.",
        "image_url": "https://publisher.test/photo.jpg",
        "source_image_url": "https://publisher.test/photo.jpg",
        "source_url": "https://publisher.test/story",
        "first_published": "Thu, 02 Oct 2026 12:00:00 -0400",
    }
    html = generate.render_article_page(hero, "Local Government", "local_gov", "2026-10-02", "2026-10-02-test", related=[])
    assert f'<img src="{hosted}"' in html
    assert f'<meta property="og:image" content="{hosted}"' in html
    assert f'<meta name="twitter:image" content="{hosted}"' in html
    assert hero["source_image_url"] == "https://publisher.test/photo.jpg"


def test_rss_source_authority_keeps_publisher_url_when_delivery_is_mirrored(monkeypatch):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    monkeypatch.setenv("BUNNY_CDN_BASE_URL", "https://images.treasurecoast.today")
    original = "https://publisher.test/photo.jpg"
    hosted = "https://images.treasurecoast.today/articles/aa/hash.jpg"
    row = {"source_image_url": original, "hosted_image_url": hosted}
    changed = generate._persist_rss_source_image_authority(row, hosted, origin="tct_bunny_source_mirror")
    assert row["source_image_url"] == original
    assert row["hosted_image_url"] == hosted
    assert row["social_image_is_source"] is True
    assert changed is True


def test_rss_contract_accepts_mirrored_delivery_with_original_source_provenance(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    monkeypatch.setenv("BUNNY_CDN_BASE_URL", "https://images.treasurecoast.today")
    slug = "2026-10-02-mirrored-story"
    original = "https://publisher.test/photo.jpg"
    hosted = "https://images.treasurecoast.today/articles/aa/hash.jpg"
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    archive = [{
        "slug": slug,
        "headline": "Mirrored story",
        "category_key": "local_gov",
        "source_image_url": original,
        "hosted_image_url": hosted,
        "rss_social_image_url": hosted,
        "rss_social_image_kind": "source",
        "rss_social_image_category_key": "local_gov",
    }]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (tmp_path / "feed.xml").write_text(
        f'<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>'
        f'<guid>https://treasurecoast.today/articles/{slug}.html</guid>'
        f'<media:content url="{hosted}" medium="image" />'
        f'</item></channel></rss>',
        encoding="utf-8",
    )
    (tmp_path / "data" / "rss-social-image-authority.json").write_text(json.dumps({
        "items": [{
            "slug": slug,
            "image_url": hosted,
            "image_kind": "source",
            "category_key": "local_gov",
        }]
    }), encoding="utf-8")
    (tmp_path / "articles" / f"{slug}.html").write_text(
        f'<html><head><meta property="og:image" content="{hosted}">'
        f'<meta name="twitter:image" content="{hosted}"></head></html>',
        encoding="utf-8",
    )
    report = generate.validate_rss_social_image_contract(tmp_path)
    assert report["status"] == "passed"
    assert report["persisted_source_images"] == 1


def test_render_hook_derives_known_publisher_name_from_source_url(monkeypatch):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "shadow")
    monkeypatch.setenv("BUNNY_CDN_BASE_URL", "https://images.treasurecoast.today")
    fake = FakeMirror({
        "status": "mirrored",
        "action": "registry_hit",
        "public_url": "https://images.treasurecoast.today/articles/aa/hash.jpg",
        "storage_key": "articles/aa/hash.jpg",
        "sha256": "hash",
    })
    monkeypatch.setattr(generate, "get_article_image_mirror", lambda root: fake)
    item = {
        "headline": "Known publisher story",
        "image_url": "https://ewscripps.brightspotcdn.com/photo.jpg",
        "source_image_url": "https://ewscripps.brightspotcdn.com/photo.jpg",
        "source_url": "https://www.wptv.com/news/region-martin-county/example",
    }

    generate._mirror_article_image_for_render(item, slug="2026-10-02-known-publisher")

    assert fake.calls[0]["source_name"] == "WPTV"
