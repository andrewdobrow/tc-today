from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORBIN_SLUG = (
    "2026-08-25-ronald-corbin-martin-county-high-school-choral-teacher-for-34-years-dies"
)
DUI_SLUG = (
    "2026-07-29-man-crashes-suv-into-port-st-lucie-liquor-store-charged-with-dui"
)


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_production_corbin_permalink_is_restored_as_substantive_article():
    archive = json.loads((ROOT / "archive.json").read_text(encoding="utf-8"))
    row = next((item for item in archive if item.get("slug") == CORBIN_SLUG), None)
    assert row is not None
    assert row["headline"].startswith("Ronald Corbin")
    assert row.get("canonical_slug") == CORBIN_SLUG
    assert row.get("incident_anchor_key") == "named-person-death:ronald-corbin"
    assert row.get("source_url", "").startswith("https://www.wpbf.com/article/ronald-l-corbin")

    manifest = json.loads(
        (ROOT / "data" / "canonical-redirects.json").read_text(encoding="utf-8")
    )
    assert not any(
        item.get("source_slug") == CORBIN_SLUG
        for item in manifest.get("redirects", [])
    )

    redirects_text = (ROOT / "_redirects").read_text(encoding="utf-8")
    assert not any(
        line.startswith(f"/articles/{CORBIN_SLUG}.html ")
        for line in redirects_text.splitlines()
    )

    article = (ROOT / "articles" / f"{CORBIN_SLUG}.html").read_text(
        encoding="utf-8"
    )
    assert "Ronald Corbin" in article
    assert "Martin County High School" in article
    assert "window.location.replace" not in article
    assert f"/articles/{DUI_SLUG}.html" not in article


def test_corbin_redirect_regression_fails_before_article_is_overwritten(tmp_path):
    generate = _load_generate()
    articles = tmp_path / "articles"
    data_dir = tmp_path / "data"
    articles.mkdir()
    data_dir.mkdir()

    article_path = articles / f"{CORBIN_SLUG}.html"
    original = "<html><body><h1>Ronald Corbin</h1></body></html>"
    article_path.write_text(original, encoding="utf-8")
    (data_dir / "canonical-redirects.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "redirects": [
                    {
                        "source_slug": CORBIN_SLUG,
                        "source_headline": "Ronald Corbin, Martin County High School choral teacher for 34 years, dies",
                        "target_slug": DUI_SLUG,
                        "target_headline": "Man accused of DUI after crashing SUV into Port St. Lucie liquor store",
                        "story_stage": "canonical-publication-ledger",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Ronald Corbin"):
        generate.enforce_canonical_redirects([], articles, tmp_path)

    assert article_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / "_redirects").exists()


def test_shared_persistent_story_id_cannot_merge_unrelated_corbin_and_dui(tmp_path):
    generate = _load_generate()
    identity_index = types.SimpleNamespace(safe_story_ids={"story_contaminated"})
    archive = [
        {
            "slug": CORBIN_SLUG,
            "headline": "Ronald Corbin, Martin County High School choral teacher for 34 years, dies",
            "source_url": "https://www.wpbf.com/article/ronald-l-corbin-beloved-choral-teacher-at-martin-high-school-for-34-years-dies/73506173",
            "date": "2026-08-25",
            "first_published": "Tue, 25 Aug 2026 16:50:11 -0400",
            "category_key": "martin",
            "editorial_story_id": "story_contaminated",
            "incident_anchor_key": "named-person-death:ronald-corbin",
        },
        {
            "slug": DUI_SLUG,
            "headline": "Man accused of DUI after crashing SUV into Port St. Lucie liquor store",
            "source_url": "https://cbs12.com/news/local/man-accused-driving-under-influence-crashes-suv-3rd-base-liquor-store-fled-scene-on-foot-driving-under-influence-st-lucie-county-jail-port-st-lucie-police-department-florida-news",
            "date": "2026-07-29",
            "first_published": "Wed, 29 Jul 2026 12:00:00 -0400",
            "category_key": "st_lucie",
            "editorial_story_id": "story_contaminated",
        },
    ]

    cleaned, redirects, report = generate._reconcile_archive_publication_identity(
        [dict(row) for row in archive], identity_index
    )
    assert {row["slug"] for row in cleaned} == {CORBIN_SLUG, DUI_SLUG}
    assert redirects == []
    assert report["records_removed"] == 0

    cleaned, redirects, _ledger, ledger_report = generate._reconcile_canonical_publication_ledger(
        [dict(row) for row in archive], identity_index, tmp_path
    )
    assert {row["slug"] for row in cleaned} == {CORBIN_SLUG, DUI_SLUG}
    assert redirects == []
    assert ledger_report["records_redirected"] == 0
