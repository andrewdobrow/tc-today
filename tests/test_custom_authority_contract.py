from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path


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


def _long_body(word: str, count: int = 500) -> str:
    return " ".join([word] * count)


def test_custom_copy_outranks_generated_hero_and_image():
    generate = _load_generate_module()
    custom = (
        "florida",
        "Florida",
        {
            "headline": "Treasure Coast Traffic Report",
            "body": _long_body("custom"),
            "is_custom": True,
            "image_url": "",
            "_is_hero_copy": False,
        },
    )
    generated = (
        "florida",
        "Florida",
        {
            "headline": "Generated traffic rewrite",
            "body": _long_body("generated", 200),
            "image_url": "https://www.wptv.com/image.jpg",
            "_is_hero_copy": True,
        },
    )

    assert generate._publication_copy_rank(custom) > generate._publication_copy_rank(generated)


def test_new_custom_article_does_not_fuzzy_merge_into_old_permalink():
    generate = _load_generate_module()
    old = {
        "slug": "2026-07-10-old-traffic-report",
        "headline": "Treasure Coast Traffic Report: July 12-17",
        "editorial_story_id": "story_traffic",
        "is_custom": True,
    }
    new = {
        "headline": "Treasure Coast Traffic Report: July 26-Aug. 1",
        "body": _long_body("closure"),
        "is_custom": True,
        "custom_body_hash": generate._custom_body_hash(_long_body("closure")),
    }

    existing, forced_slug, story_id = generate._resolve_custom_publication_target(
        new, [old], old, new["headline"]
    )

    assert existing is None
    assert forced_slug is None
    assert story_id.startswith("custom:")
    assert story_id != old["editorial_story_id"]


def test_explicit_replace_slug_updates_exact_custom_permalink():
    generate = _load_generate_module()
    old = {"slug": "existing-custom", "is_custom": True}
    custom = {
        "headline": "Corrected custom report",
        "body": _long_body("corrected"),
        "is_custom": True,
        "replace_slug": "existing-custom",
    }

    existing, forced_slug, story_id = generate._resolve_custom_publication_target(
        custom, [old], None, custom["headline"]
    )

    assert existing is old
    assert forced_slug is None
    assert story_id is None


def test_changed_custom_payload_is_reloaded_and_repairs_exact_headline(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    headline = "Treasure Coast Traffic Report: Major Closures"
    old_body = _long_body("old", 80)
    new_body = _long_body("new", 600)
    (tmp_path / "archive.json").write_text(
        json.dumps([
            {
                "slug": "2026-07-10-traffic-report",
                "headline": headline,
                "teaser": old_body[:180],
                "is_custom": True,
                "article_word_count": 80,
                "custom_fingerprint": generate._custom_story_fingerprint(headline, old_body[:180]),
            }
        ]),
        encoding="utf-8",
    )
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([
            {
                "headline": headline,
                "body": new_body,
                "category": "florida",
                "expires": "2099-01-01",
            }
        ]),
        encoding="utf-8",
    )

    loaded = generate.load_custom_articles()

    assert len(loaded) == 1
    assert loaded[0]["body"] == new_body
    assert loaded[0]["replace_slug"] == "2026-07-10-traffic-report"
    assert loaded[0]["custom_body_hash"] == generate._custom_body_hash(new_body)


def test_exact_custom_payload_is_not_republished(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    headline = "Custom city budget article"
    body = _long_body("budget", 300)
    body_hash = generate._custom_body_hash(body)
    (tmp_path / "archive.json").write_text(
        json.dumps([
            {
                "slug": "custom-city-budget",
                "headline": headline,
                "is_custom": True,
                "article_word_count": 300,
                "custom_body_hash": body_hash,
                "custom_fingerprint": generate._custom_story_fingerprint(headline, body[:180]),
            }
        ]),
        encoding="utf-8",
    )
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([
            {
                "headline": headline,
                "body": body,
                "category": "local_gov",
                "expires": "2099-01-01",
            }
        ]),
        encoding="utf-8",
    )

    assert generate.load_custom_articles() == []


def test_unique_slug_never_reuses_exact_headline_permalink(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    headline = "Treasure Coast Traffic Report: Major Closures"
    old_body = _long_body("old", 80)
    new_body = _long_body("new", 600)
    (tmp_path / "archive.json").write_text(
        json.dumps([
            {
                "slug": "2026-07-10-traffic-report",
                "headline": headline,
                "teaser": old_body[:180],
                "is_custom": True,
                "custom_fingerprint": generate._custom_story_fingerprint(headline, old_body[:180]),
            }
        ]),
        encoding="utf-8",
    )
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([
            {
                "headline": headline,
                "body": new_body,
                "category": "florida",
                "expires": "2099-01-01",
                "unique_slug": True,
            }
        ]),
        encoding="utf-8",
    )

    loaded = generate.load_custom_articles()

    assert len(loaded) == 1
    assert "replace_slug" not in loaded[0]
    existing, forced_slug, story_id = generate._resolve_custom_publication_target(
        loaded[0], json.loads((tmp_path / "archive.json").read_text()), None, headline
    )
    assert existing is None
    assert forced_slug is None
    assert story_id.startswith("custom:")


def test_custom_category_repair_moves_florida_article_out_of_sports():
    generate = _load_generate_module()
    custom = {
        "headline": "Treasure Coast Traffic Report",
        "body": _long_body("closure"),
        "category": "florida",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_body_hash": "payload-one",
        "force_hero": False,
    }
    categories = [
        {"category_key": "sports", "category_label": "Sports", "hero": custom, "cards": []},
        {
            "category_key": "florida",
            "category_label": "Florida",
            "hero": {"headline": "Florida news", "body": _long_body("news")},
            "cards": [],
        },
    ]

    report = generate.enforce_custom_category_placement(categories)

    assert report["moved"] == 1
    assert categories[0]["hero"] is None
    assert custom in categories[1]["cards"]
    assert generate.validate_custom_category_placement(categories)["passed"] is True


def test_noncustom_sports_item_is_never_rebound_to_custom_archive(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "old-traffic.html").write_text("published", encoding="utf-8")
    archive = [{
        "slug": "old-traffic",
        "headline": "Treasure Coast Traffic Report",
        "is_custom": True,
        "authoritative_custom": True,
    }]
    sports = {
        "category_key": "sports",
        "category_label": "Sports",
        "hero": {"headline": "St. Lucie Mets win", "body": _long_body("baseball")},
        "cards": [],
    }
    monkeypatch.setattr(generate, "_matches_archived_custom", lambda item, entry: True)

    rebound = generate._rebind_live_items_to_published_archive(
        [sports], archive, current_customs=[], articles_dir=articles
    )

    assert rebound == 0
    assert sports["hero"]["headline"] == "St. Lucie Mets win"
    assert "_archived_slug" not in sports["hero"]


def test_custom_body_fidelity_requires_complete_submitted_copy():
    generate = _load_generate_module()
    body = "**Lead paragraph.**\n\n## Major closures\n\n- Martin Highway\n- Midway Road\n\nFinal safety paragraph."
    hero = {
        "headline": "Treasure Coast Traffic Report",
        "body": body,
        "is_custom": True,
        "authoritative_custom": True,
    }
    full_page = (
        '<div class="article-body">' + generate.make_paragraphs(body, preserve_all=True)
        + '</div><div class="article-share">share</div>'
    )
    assert generate.validate_custom_body_fidelity(hero, full_page) is True

    truncated_page = (
        '<div class="article-body"><p>Lead paragraph.</p></div>'
        '<div class="article-share">share</div>'
    )
    try:
        generate.validate_custom_body_fidelity(hero, truncated_page)
    except RuntimeError as exc:
        assert "Custom body fidelity FAILED" in str(exc)
    else:
        raise AssertionError("expected truncated custom body to fail")
