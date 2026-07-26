from __future__ import annotations

import importlib
import json
import os
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

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_incorrect_image_custom_article_is_removed_from_public_surfaces(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    bad_headline = "Mets’ Comeback Falls Short in 15-14 Loss to Mighty Mussels"
    bad_slug = "2026-07-25-st-lucie-mets-comeback-falls-short-15-14-mighty-mussels"
    old_slug = "2026-07-19-cardinals-homer-twice-defeat-st-lucie-mets-7-4"

    (tmp_path / "data").mkdir()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data" / "custom-retirements.json").write_text(
        json.dumps({
            "headlines": [{"headline": bad_headline, "action": "purge"}],
            "slugs": [{"slug": bad_slug, "action": "purge"}],
        }),
        encoding="utf-8",
    )
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([{
            "headline": bad_headline,
            "body": "Bad-image recap should never republish.",
            "category": "sports",
            "slug": bad_slug,
            "expires": "2099-01-01",
        }]),
        encoding="utf-8",
    )
    archive = [
        {
            "slug": old_slug,
            "headline": "Cardinals Homer Twice, Defeat St. Lucie Mets 7-4",
            "category_key": "sports",
            "category_label": "Sports",
            "date": "2026-07-19",
            "first_published": "Sun, 19 Jul 2026 20:00:00 -0400",
            "is_custom": True,
            "authoritative_custom": True,
        },
        {
            "slug": bad_slug,
            "headline": bad_headline,
            "category_key": "sports",
            "category_label": "Sports",
            "date": "2026-07-25",
            "first_published": "Sat, 25 Jul 2026 22:00:00 -0400",
            "is_custom": True,
            "authoritative_custom": True,
        },
    ]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (tmp_path / "articles" / f"{old_slug}.html").write_text("OLD CARDINALS ARTICLE", encoding="utf-8")
    (tmp_path / "articles" / f"{bad_slug}.html").write_text("BAD IMAGE ARTICLE BODY", encoding="utf-8")

    assert g.load_custom_articles() == []
    assert g.apply_custom_retirements_to_archive(tmp_path) == 1

    remaining = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert [row["slug"] for row in remaining] == [old_slug]
    assert (tmp_path / "articles" / f"{old_slug}.html").read_text(encoding="utf-8") == "OLD CARDINALS ARTICLE"

    removed_page = (tmp_path / "articles" / f"{bad_slug}.html").read_text(encoding="utf-8")
    assert "BAD IMAGE ARTICLE BODY" not in removed_page
    assert 'name="robots" content="noindex,nofollow"' in removed_page
    assert "/sports.html" in removed_page

    for public_file in ("archive.html", "sitemap.xml", "news-sitemap.xml"):
        assert bad_slug not in (tmp_path / public_file).read_text(encoding="utf-8")
    assert old_slug in (tmp_path / "archive.html").read_text(encoding="utf-8")
    assert old_slug in (tmp_path / "sitemap.xml").read_text(encoding="utf-8")

    report = json.loads((tmp_path / "data" / "custom-retirement-report.json").read_text(encoding="utf-8"))
    assert report["purged_count"] == 1
    assert report["purged"][0]["slug"] == bad_slug


def test_public_purge_is_slug_scoped_not_fuzzy_custom_identity(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    bad_headline = "Mets’ Comeback Falls Short in 15-14 Loss to Mighty Mussels"
    intended_bad_slug = "2026-07-25-st-lucie-mets-comeback-falls-short-15-14-mighty-mussels"
    prior_custom_slug = "2026-07-19-cardinals-homer-twice-defeat-st-lucie-mets-7-4"

    (tmp_path / "data").mkdir()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data" / "custom-retirements.json").write_text(
        json.dumps({
            "headlines": [{"headline": bad_headline, "action": "purge"}],
            "slugs": [{"slug": intended_bad_slug, "action": "purge"}],
        }),
        encoding="utf-8",
    )
    # A prior custom URL must never be hard-deleted merely because a bad live copy
    # temporarily carried the new headline during a historical identity collision.
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": prior_custom_slug,
        "headline": bad_headline,
        "category_key": "sports",
        "category_label": "Sports",
        "date": "2026-07-19",
        "is_custom": True,
        "authoritative_custom": True,
    }]), encoding="utf-8")
    prior_page = tmp_path / "articles" / f"{prior_custom_slug}.html"
    prior_page.write_text("PRIOR CUSTOM URL", encoding="utf-8")

    assert g.apply_custom_retirements_to_archive(tmp_path) == 1
    remaining = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert len(remaining) == 1
    assert remaining[0]["slug"] == prior_custom_slug
    assert remaining[0]["exclude_from_live_recovery"] is True
    assert prior_page.read_text(encoding="utf-8") == "PRIOR CUSTOM URL"
