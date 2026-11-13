"""Regression checks: editorial image corrections also reach the native app.

The app uses archive.json.image_url. Correcting only the article HTML and RSS
does not update the image visible in its native story cards.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.sync_editorial_image_archive import sync_archive

ROOT = Path(__file__).resolve().parents[1]
BURGLARY_SLUG = "2026-11-13-sheriff-seeks-help-identifying-suspect-in-fort-pierce-store-burglary"
APPROVED = "https://treasurecoast.today/images/fort-pierce-mlk.jpg"


def _fixture(root: Path) -> Path:
    (root / "data").mkdir()
    (root / "data" / "article-image-overrides.json").write_text(json.dumps({
        "overrides": {
            BURGLARY_SLUG: {"image_url": APPROVED},
            "another": {"image_url": "https://treasurecoast.today/images/other.jpg"},
        },
    }), encoding="utf-8")
    archive = root / "archive.json"
    archive.write_text(json.dumps([
        {"slug": BURGLARY_SLUG, "canonical_slug": BURGLARY_SLUG,
         "image_url": "https://example.com/old.jpg",
         "source_image_url": "https://example.com/original-source.jpg",
         "rss_social_image_url": "https://example.com/old.jpg"},
        {"slug": "another", "canonical_slug": "another",
         "image_url": "https://treasurecoast.today/images/other.jpg",
         "rss_social_image_url": "https://example.com/outdated-social.jpg"},
        {"slug": "unrelated", "image_url": "https://example.com/untouched.jpg"},
    ]), encoding="utf-8")
    return archive


def test_iOS_archive_sync_changes_photo_without_changing_original_source(tmp_path):
    archive = _fixture(tmp_path)
    found, changed = sync_archive(tmp_path)
    assert (found, changed) == (2, 1)
    rows = json.loads(archive.read_text(encoding="utf-8"))
    assert rows[0]["image_url"] == APPROVED
    assert rows[0]["rss_social_image_url"] == APPROVED
    assert rows[0]["source_image_url"] == "https://example.com/original-source.jpg"
    assert rows[0]["article_image_override"] is True
    assert rows[1]["rss_social_image_url"] == "https://treasurecoast.today/images/other.jpg"
    assert rows[2]["image_url"] == "https://example.com/untouched.jpg"
    after = archive.read_bytes()
    assert sync_archive(tmp_path) == (2, 0)
    assert archive.read_bytes() == after


def test_image_sync_updates_stale_social_data_even_if_primary_image_matches(tmp_path):
    archive = _fixture(tmp_path)
    rows = json.loads(archive.read_text(encoding="utf-8"))
    rows[0]["image_url"] = APPROVED
    archive.write_text(json.dumps(rows), encoding="utf-8")
    assert sync_archive(tmp_path) == (2, 0)
    updated = json.loads(archive.read_text(encoding="utf-8"))
    assert updated[0]["rss_social_image_url"] == APPROVED
    assert updated[0]["article_image_override"] is True


def test_burglary_override_exists_and_deploy_only_updates_ios_archive():
    ledger = json.loads((ROOT / "data/article-image-overrides.json").read_text(encoding="utf-8"))
    assert ledger["overrides"][BURGLARY_SLUG]["image_url"] == APPROVED

    workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    assert workflow.count("python scripts/sync_editorial_image_archive.py") == 2
    assert workflow.index("Sync editor-approved photos into iOS archive (including deploy-only)") > workflow.index("  deploy:")
