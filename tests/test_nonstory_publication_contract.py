from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected Claude call"))
                )

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _bad_item(**updates):
    item = {
        "headline": "No Indian River County stories available in today's feed",
        "teaser": "No Indian River County stories are available in today's feed.",
        "body": "Indian River County " * 300,
        "source_quality": "full",
        "source_word_count": 300,
        "enriched": True,
        "category_key": "indian_river",
    }
    item.update(updates)
    return item


def test_exact_live_placeholder_is_nonstory_even_with_long_body():
    generate = _load_generate_module()
    item = _bad_item()

    assert generate._is_nonstory_placeholder(item) is True
    assert generate._publishable_article(item, hero=True) is False


def test_custom_authority_is_not_overridden_by_headline_pattern():
    generate = _load_generate_module()
    item = _bad_item(is_custom=True)

    assert generate._is_nonstory_placeholder(item) is False
    assert generate._publishable_article(item, hero=True) is True


def test_category_sanitizer_promotes_real_card():
    generate = _load_generate_module()
    real = {
        "headline": "Vero Beach approves shoreline restoration project",
        "body": "Vero Beach approved a shoreline restoration project. " * 20,
        "source_quality": "full",
    }
    category = {"hero": _bad_item(), "cards": [real], "category_key": "indian_river"}

    cleaned = generate._sanitize_nonstory_category(category, "Indian River County")

    assert cleaned["hero"]["headline"] == real["headline"]
    assert cleaned["cards"] == []
    assert cleaned.get("_drop_category") is not True


def test_category_sanitizer_drops_empty_nonstory_category():
    generate = _load_generate_module()
    category = {"hero": _bad_item(), "cards": [], "category_key": "indian_river"}

    cleaned = generate._sanitize_nonstory_category(category, "Indian River County")

    assert cleaned["hero"] == {}
    assert cleaned["_drop_category"] is True


def test_rss_excludes_nonstory_even_when_archive_record_exists(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    bad = _bad_item()
    good = {
        "headline": "Vero Beach council approves new drainage work",
        "teaser": "The council approved drainage improvements.",
        "body": "The council approved drainage improvements.",
        "category_key": "indian_river",
    }
    (tmp_path / "archive.json").write_text(json.dumps([
        {"slug": "bad-placeholder", "headline": bad["headline"], "date": "2026-07-25"},
        {"slug": "good-story", "headline": good["headline"], "date": "2026-07-25"},
    ]), encoding="utf-8")
    category = {
        "category_key": "indian_river",
        "category_label": "Indian River County",
        "hero": good,
        "cards": [bad],
    }

    rss = generate.render_rss_feed([category], category)

    assert "good-story.html" in rss
    assert bad["headline"] not in rss
    assert "bad-placeholder.html" not in rss


def test_archive_purge_removes_record_and_replaces_page_with_noindex_redirect(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "bad-placeholder.html").write_text("<html>bad article</html>", encoding="utf-8")
    archive = [
        {"slug": "bad-placeholder", "headline": _bad_item()["headline"], "category_key": "indian_river"},
        {"slug": "real-story", "headline": "Sebastian council approves budget", "category_key": "indian_river"},
    ]

    kept, report = generate._purge_nonstory_archive_entries(archive, articles, tmp_path)

    assert [entry["slug"] for entry in kept] == ["real-story"]
    assert report["removed_count"] == 1
    redirect = (articles / "bad-placeholder.html").read_text(encoding="utf-8")
    assert "noindex,follow" in redirect
    assert "/archive.html" in redirect
    saved = json.loads((tmp_path / "data" / "nonstory-purge.json").read_text(encoding="utf-8"))
    assert saved["removed"][0]["slug"] == "bad-placeholder"


def test_final_contract_blocks_nonstory_on_live_surface(tmp_path: Path):
    generate = _load_generate_module()
    (tmp_path / "archive.json").write_text("[]", encoding="utf-8")
    (tmp_path / "feed.xml").write_text("<rss><channel><title>Treasure Coast Today</title></channel></rss>", encoding="utf-8")
    category = {
        "category_key": "indian_river",
        "category_label": "Indian River County",
        "hero": _bad_item(),
        "cards": [],
    }

    with pytest.raises(RuntimeError, match="Nonstory publication contract FAILED"):
        generate.validate_nonstory_publication_contract([category], category, tmp_path)

    report = json.loads((tmp_path / "data" / "nonstory-publication-contract.json").read_text())
    assert report["status"] == "failed"
    assert report["violation_count"] >= 1


def test_final_contract_passes_for_real_story_and_custom_exception(tmp_path: Path):
    generate = _load_generate_module()
    custom = _bad_item(is_custom=True)
    real = {"headline": "Fellsmere opens new public safety facility"}
    (tmp_path / "archive.json").write_text(json.dumps([
        {"slug": "real", "headline": real["headline"]},
        {"slug": "custom", "headline": custom["headline"], "is_custom": True},
    ]), encoding="utf-8")
    (tmp_path / "feed.xml").write_text(
        "<rss><channel><title>Treasure Coast Today</title>"
        f"<item><title><![CDATA[{real['headline']}]]></title></item>"
        f"<item><title><![CDATA[{custom['headline']}]]></title></item>"
        "</channel></rss>", encoding="utf-8"
    )
    category = {
        "category_key": "indian_river",
        "category_label": "Indian River County",
        "hero": real,
        "cards": [custom],
    }

    report = generate.validate_nonstory_publication_contract([category], category, tmp_path)

    assert report["passed"] is True
    assert report["violation_count"] == 0


def test_legacy_exact_source_duplicates_are_consolidated(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    source = "https://www.wptv.com/money/consumer/fort-pierce-mom-among-thousands-struggling?utm_source=rss"
    archive = [
        {
            "slug": "first-childcare",
            "headline": "Fort Pierce mother leaves nursing career as childcare costs rise",
            "source_url": source,
            "date": "2026-07-22",
            "article_word_count": 300,
        },
        {
            "slug": "second-childcare",
            "headline": "Fort Pierce child care crisis forces mother to leave nursing job",
            "source_url": "https://www.wptv.com/money/consumer/fort-pierce-mom-among-thousands-struggling",
            "date": "2026-07-22",
            "article_word_count": 280,
        },
        {
            "slug": "third-childcare",
            "headline": "85% of Florida families exceed childcare affordability benchmark",
            "source_url": "https://www.wptv.com/money/consumer/fort-pierce-mom-among-thousands-struggling?utm_medium=referral",
            "date": "2026-07-22",
            "article_word_count": 250,
        },
    ]
    for entry in archive:
        (articles / f"{entry['slug']}.html").write_text("<html>article</html>", encoding="utf-8")

    cleaned, redirects = generate.apply_canonical_story_cleanup(archive, articles, tmp_path)

    assert [entry["slug"] for entry in cleaned] == ["first-childcare"]
    assert {record["source_slug"] for record in redirects} == {"second-childcare", "third-childcare"}
    assert all(record["match_confidence"] == 100 for record in redirects)
    assert all(record["story_stage"] == "legacy-exact-source-identity" for record in redirects)
    assert "first-childcare.html" in (articles / "second-childcare.html").read_text(encoding="utf-8")


def test_legacy_exact_source_cleanup_keeps_different_article_urls_separate(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    archive = [
        {
            "slug": "story-a",
            "headline": "Vero Beach approves drainage project",
            "source_url": "https://example.com/news/story-a",
            "date": "2026-07-22",
        },
        {
            "slug": "story-b",
            "headline": "Vero Beach approves park project",
            "source_url": "https://example.com/news/story-b",
            "date": "2026-07-22",
        },
    ]

    cleaned, redirects = generate.apply_canonical_story_cleanup(archive, articles, tmp_path)

    assert {entry["slug"] for entry in cleaned} == {"story-a", "story-b"}
    assert redirects == []


def test_final_contract_independently_blocks_placeholder_in_first_rss_item(tmp_path: Path):
    generate = _load_generate_module()
    real = {"headline": "Vero Beach approves drainage work"}
    (tmp_path / "archive.json").write_text(json.dumps([
        {"slug": "real", "headline": real["headline"]},
    ]), encoding="utf-8")
    bad_title = _bad_item()["headline"]
    (tmp_path / "feed.xml").write_text(
        "<rss><channel><title>Treasure Coast Today</title>"
        f"<item><title><![CDATA[{bad_title}]]></title></item>"
        "</channel></rss>", encoding="utf-8"
    )
    category = {
        "category_key": "indian_river",
        "category_label": "Indian River County",
        "hero": real,
        "cards": [],
    }

    with pytest.raises(RuntimeError, match="Nonstory publication contract FAILED"):
        generate.validate_nonstory_publication_contract([category], category, tmp_path)

    report = json.loads((tmp_path / "data" / "nonstory-publication-contract.json").read_text())
    assert report["checked_rss_items"] == 1
    assert any(v["surface"] == "rss" for v in report["violations"])
