import json
from pathlib import Path

import pytest

from tct_engine.article_image_mirror import (
    ArticleImageMirror,
    finalize_article_image_mirror,
    reset_article_image_mirror_for_tests,
)


@pytest.fixture
def bunny_env(monkeypatch):
    monkeypatch.setenv("BUNNY_STORAGE_ZONE_NAME", "tct-article-images")
    monkeypatch.setenv("BUNNY_STORAGE_ZONE_PASSWORD", "secret")
    monkeypatch.setenv("BUNNY_STORAGE_REGION", "ny")
    monkeypatch.setenv("BUNNY_CDN_BASE_URL", "https://images.treasurecoast.today")


def _stub_download(monkeypatch, mirror, *, body=b"jpeg-bytes", content_type="image/jpeg"):
    digest = __import__("hashlib").sha256(body).hexdigest()
    monkeypatch.setattr(
        mirror,
        "_download",
        lambda url: (body, digest, content_type, url, {"etag": '"abc"', "last_modified": ""}),
    )
    return digest


def test_external_mode_does_no_storage_work(tmp_path, monkeypatch):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "external")
    mirror = ArticleImageMirror(tmp_path)
    result = mirror.mirror(slug="story", original_url="https://publisher.test/a.jpg")
    assert result["resolved_url"] == "https://publisher.test/a.jpg"
    assert result["status"] == "external"
    assert not (tmp_path / "data" / "article-image-registry.json").exists()


def test_shadow_uploads_and_records_but_returns_publisher_url(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "shadow")
    mirror = ArticleImageMirror(tmp_path)
    digest = _stub_download(monkeypatch, mirror)
    uploads = []
    monkeypatch.setattr(mirror, "_upload", lambda key, content, ctype: uploads.append((key, content, ctype)))
    monkeypatch.setattr(mirror, "_verify_public", lambda url, size: None)

    original = "https://publisher.test/a.jpg"
    result = mirror.mirror(slug="story", original_url=original, source_article_url="https://publisher.test/story")

    assert result["resolved_url"] == original
    assert result["public_url"].startswith("https://images.treasurecoast.today/articles/")
    assert result["sha256"] == digest
    assert len(uploads) == 1
    registry = json.loads((tmp_path / "data" / "article-image-registry.json").read_text())
    current = registry["articles"]["story"]["current_image"]
    assert current["original_url"] == original
    assert current["public_url"] == result["public_url"]
    assert current["status"] == "mirrored"


def test_mirror_mode_switches_only_after_registry_write(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    mirror = ArticleImageMirror(tmp_path)
    _stub_download(monkeypatch, mirror)
    monkeypatch.setattr(mirror, "_upload", lambda key, content, ctype: None)
    monkeypatch.setattr(mirror, "_verify_public", lambda url, size: None)

    original = "https://publisher.test/a.jpg"
    result = mirror.mirror(slug="story", original_url=original)
    assert result["resolved_url"] == result["public_url"]
    assert (tmp_path / "data" / "article-image-registry.json").exists()
    registry = json.loads((tmp_path / "data" / "article-image-registry.json").read_text())
    assert registry["articles"]["story"]["current_image"]["original_url"] == original


def test_registry_hit_has_zero_downloads_and_zero_uploads(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    mirror = ArticleImageMirror(tmp_path)
    _stub_download(monkeypatch, mirror)
    monkeypatch.setattr(mirror, "_upload", lambda key, content, ctype: None)
    monkeypatch.setattr(mirror, "_verify_public", lambda url, size: None)
    original = "https://publisher.test/a.jpg"
    first = mirror.mirror(slug="story", original_url=original)
    monkeypatch.setattr(mirror, "_source_changed_since", lambda url, current: False)

    def explode(*args, **kwargs):
        raise AssertionError("network/storage work should not run on registry hit")

    monkeypatch.setattr(mirror, "_download", explode)
    monkeypatch.setattr(mirror, "_upload", explode)
    second = mirror.mirror(slug="story", original_url=original)
    assert second["public_url"] == first["public_url"]
    assert second["action"] == "registry_hit"
    assert mirror.stats["registry_hits"] == 1


def test_hash_dedupe_reuses_object_without_second_upload(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "shadow")
    mirror = ArticleImageMirror(tmp_path)
    _stub_download(monkeypatch, mirror, body=b"same-image")
    uploads = []
    monkeypatch.setattr(mirror, "_upload", lambda key, content, ctype: uploads.append(key))
    monkeypatch.setattr(mirror, "_verify_public", lambda url, size: None)

    one = mirror.mirror(slug="story-one", original_url="https://publisher-a.test/a.jpg")
    two = mirror.mirror(slug="story-two", original_url="https://publisher-b.test/b.jpg")
    assert one["public_url"] == two["public_url"]
    assert len(uploads) == 1
    assert two["action"] == "hash_dedupe_hit"


def test_failure_falls_back_and_is_durably_logged(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    mirror = ArticleImageMirror(tmp_path)
    monkeypatch.setattr(mirror, "_download", lambda url: (_ for _ in ()).throw(RuntimeError("boom")))
    original = "https://publisher.test/a.jpg"
    result = mirror.mirror(slug="story", original_url=original)
    assert result["resolved_url"] == original
    assert result["status"] == "external"
    registry = json.loads((tmp_path / "data" / "article-image-registry.json").read_text())
    current = registry["articles"]["story"]["current_image"]
    assert current["original_url"] == original
    assert current["public_url"] == ""
    assert current["status"] == "external"
    assert "boom" in current["error"]


def test_same_source_url_re_downloads_when_validator_reports_change(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "mirror")
    mirror = ArticleImageMirror(tmp_path)
    original = "https://publisher.test/a.jpg"
    first_body = b"first-image"
    second_body = b"second-image"
    first_digest = __import__("hashlib").sha256(first_body).hexdigest()
    second_digest = __import__("hashlib").sha256(second_body).hexdigest()
    calls = {"download": 0, "upload": 0}

    def first_download(url):
        calls["download"] += 1
        return first_body, first_digest, "image/jpeg", url, {"etag": '"v1"', "last_modified": ""}

    monkeypatch.setattr(mirror, "_download", first_download)
    monkeypatch.setattr(mirror, "_upload", lambda *args: calls.__setitem__("upload", calls["upload"] + 1))
    monkeypatch.setattr(mirror, "_verify_public", lambda url, size: None)
    first = mirror.mirror(slug="story", original_url=original)

    monkeypatch.setattr(mirror, "_source_changed_since", lambda url, current: True)

    def second_download(url):
        calls["download"] += 1
        return second_body, second_digest, "image/jpeg", url, {"etag": '"v2"', "last_modified": ""}

    monkeypatch.setattr(mirror, "_download", second_download)
    second = mirror.mirror(slug="story", original_url=original)
    assert calls["download"] == 2
    assert calls["upload"] == 2
    assert first["sha256"] != second["sha256"]
    registry = json.loads((tmp_path / "data" / "article-image-registry.json").read_text())
    row = registry["articles"]["story"]
    assert row["current_image"]["sha256"] == second_digest
    assert row["history"][0]["sha256"] == first_digest


def test_registry_source_names_backfill_without_new_candidates(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "shadow")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    registry = {
        "schema_version": 1,
        "storage_provider": "bunny",
        "updated_at": "",
        "articles": {
            "cbs-story": {
                "canonical_slug": "cbs-story",
                "history": [],
                "source_name": "",
                "source_article_url": "https://cbs12.com/news/local/example",
                "current_image": {"status": "mirrored"},
            },
            "wptv-story": {
                "canonical_slug": "wptv-story",
                "history": [],
                "source_name": "",
                "source_article_url": "https://www.wptv.com/news/region-martin-county/example",
                "current_image": {"status": "mirrored"},
            },
            "wpbf-story": {
                "canonical_slug": "wpbf-story",
                "history": [],
                "source_name": "",
                "source_article_url": "https://www.wpbf.com/article/example/123",
                "current_image": {"status": "mirrored"},
            },
        },
        "objects": {},
    }
    path = data_dir / "article-image-registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")

    mirror = ArticleImageMirror(tmp_path)
    repaired = json.loads(path.read_text(encoding="utf-8"))

    assert repaired["articles"]["cbs-story"]["source_name"] == "CBS12"
    assert repaired["articles"]["wptv-story"]["source_name"] == "WPTV"
    assert repaired["articles"]["wpbf-story"]["source_name"] == "WPBF"
    assert mirror.stats["metadata_repairs"] == 3
    assert mirror.stats["candidates"] == 0


def test_report_elapsed_measures_image_work_not_manager_lifetime(tmp_path, monkeypatch, bunny_env):
    import time

    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "shadow")
    mirror = ArticleImageMirror(tmp_path)
    mirror.started = time.perf_counter() - 100
    _stub_download(monkeypatch, mirror)
    monkeypatch.setattr(mirror, "_upload", lambda key, content, ctype: None)
    monkeypatch.setattr(mirror, "_verify_public", lambda url, size: None)

    mirror.mirror(slug="story", original_url="https://publisher.test/a.jpg")
    report = mirror.write_report()

    assert report["manager_lifetime_seconds"] >= 99
    assert report["image_work_elapsed_seconds"] < 2
    assert report["elapsed_seconds"] == report["image_work_elapsed_seconds"]
    assert set(report["timing_seconds"]) >= {
        "candidate_seconds",
        "download_seconds",
        "upload_seconds",
        "verification_seconds",
        "revalidation_seconds",
        "registry_write_seconds",
        "metadata_repair_seconds",
    }
    assert "timing_seconds" in report["events"][0]


def test_blank_source_name_is_inferred_on_new_mirror(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "shadow")
    mirror = ArticleImageMirror(tmp_path)
    _stub_download(monkeypatch, mirror)
    monkeypatch.setattr(mirror, "_upload", lambda key, content, ctype: None)
    monkeypatch.setattr(mirror, "_verify_public", lambda url, size: None)

    mirror.mirror(
        slug="story",
        original_url="https://cdn.example/photo.jpg",
        source_article_url="https://www.wptv.com/news/region-martin-county/story",
        source_name="",
    )
    registry = json.loads((tmp_path / "data" / "article-image-registry.json").read_text())
    assert registry["articles"]["story"]["source_name"] == "WPTV"


def test_finalize_writes_zero_candidate_shadow_report(tmp_path, monkeypatch, bunny_env):
    monkeypatch.setenv("TCT_ARTICLE_IMAGE_MODE", "shadow")
    reset_article_image_mirror_for_tests()
    try:
        report = finalize_article_image_mirror(tmp_path)
    finally:
        reset_article_image_mirror_for_tests()

    assert report is not None
    assert report["mode"] == "shadow"
    assert report["summary"]["candidates"] == 0
    assert report["summary"]["downloads"] == 0
    assert report["summary"]["uploads"] == 0
    assert report["image_work_elapsed_seconds"] >= 0
    assert (tmp_path / "data" / "article-image-mirror-report.json").is_file()
