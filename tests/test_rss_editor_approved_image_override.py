"""Regression: editor-approved Bunny photo must not block production RSS."""
import importlib.util
import json
import os
from pathlib import Path

import pytest


SLUG = "2026-11-11-jensen-beach-family-seeks-housing-and-repair-funding-after-flooding-destroys-hom"
PHOTO = ("https://images.treasurecoast.today/articles/f9/"
         "f93c5c9afd15b72f0dc2cac4c3154fbd9f32ef756ac9e507591079dfa0a3ee46.png")


def _generate():
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("rss_editor_override_regression", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("case,expected_pass", [
    ("approved", True),
    ("missing_editor_flag", False),
    ("wrong_origin", False),
    ("wrong_ledger_url", False),
    ("mismatched_archive_image", False),
])
def test_manual_first_party_cdn_photo_is_valid_only_with_exact_editor_authority(
    tmp_path, monkeypatch, case, expected_pass
):
    generate = _generate()
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    override_path = tmp_path / "article-image-overrides.json"
    monkeypatch.setattr(generate, "ARTICLE_IMAGE_OVERRIDES_PATH", override_path)

    approved_url = PHOTO
    if case == "wrong_ledger_url":
        approved_url = ("https://images.treasurecoast.today/articles/aa/"
                        + "a" * 64 + ".png")
    override_path.write_text(json.dumps({
        "overrides": {SLUG: {"image_url": approved_url}}
    }), encoding="utf-8")

    row = {
        "slug": SLUG,
        "headline": "Jensen Beach family seeks housing after flooding",
        "teaser": "A flood-affected family seeks help.",
        "category_key": "martin",
        "first_published": "Wed, 11 Nov 2026 14:17:22 -0500",
        "image_url": PHOTO,
        "source_image_url": PHOTO,
        "hosted_image_url": PHOTO,
        "image_source": "manual_article_image_override",
        "article_image_override": True,
        "is_custom": False,
    }
    if case == "missing_editor_flag":
        row["article_image_override"] = False
    elif case == "wrong_origin":
        row["image_source"] = "source_image"
    elif case == "mismatched_archive_image":
        row["image_url"] = "https://images.treasurecoast.today/articles/zz/other.png"

    (tmp_path / "archive.json").write_text(json.dumps([row]), encoding="utf-8")
    feed = generate.render_rss_feed([], {}, max_items=10)
    (tmp_path / "feed.xml").write_text(feed, encoding="utf-8")
    if expected_pass:
        report = generate.validate_rss_social_image_contract(tmp_path)
        assert report["status"] == "passed", report["issues"]
        assert report["persisted_source_images"] == 1
        assert PHOTO in feed
    else:
        with pytest.raises(RuntimeError, match="RSS social image contract FAILED"):
            generate.validate_rss_social_image_contract(tmp_path)
        report = json.loads(
            (tmp_path / "data/rss-social-image-contract.json").read_text(encoding="utf-8")
        )
        assert any(
            item["reason"] == "mirrored_source_authority_not_persisted_to_archive"
            for item in report["issues"]
        )
