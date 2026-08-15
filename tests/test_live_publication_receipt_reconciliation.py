from __future__ import annotations

import importlib.util
import json
import sys
import types
from datetime import datetime, timezone
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
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_live_receipt_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _archive_row(slug: str, headline: str, story_id: str, category_key: str):
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "slug": slug,
        "headline": headline,
        "teaser": "Verified current-run article with enough source-backed detail.",
        "category_key": category_key,
        "category_label": category_key.replace("_", " ").title(),
        "category_keys": [category_key],
        "county_keys": [category_key] if category_key in {"martin", "st_lucie", "indian_river"} else [],
        "date": today,
        "lastmod": today,
        "editorial_story_id": story_id,
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "article_word_count": 180,
        "article_paragraph_count": 3,
    }


def test_same_run_skipped_variants_rebind_to_written_canonical_pages(tmp_path):
    g = _load_generate()
    g.OUTPUT_DIR = tmp_path
    articles = tmp_path / "articles"
    articles.mkdir()
    today = datetime.now(timezone.utc).date().isoformat()
    armed_slug = f"{today}-armed-robbery-at-fort-pierce-wells-fargo-atm-forces-victim-to-withdraw-cash"
    lang_slug = f"{today}-indian-river-county-firefighter-geoffrey-lang-dies-following-personal-tragedy"
    archive = [
        _archive_row(
            armed_slug,
            "Armed robbery at Fort Pierce Wells Fargo ATM forces victim to withdraw cash",
            "story-armed-canonical",
            "crime",
        ),
        _archive_row(
            lang_slug,
            "Indian River County firefighter Geoffrey Lang dies following personal tragedy at home",
            "story-lang-canonical",
            "indian_river",
        ),
    ]
    for row in archive:
        (articles / f"{row['slug']}.html").write_text("<article>published</article>", encoding="utf-8")
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")

    armed_a = {
        "headline": "Armed robbers force man to withdraw cash at Wells Fargo ATM in Fort Pierce",
        "category_key": "crime",
        "editorial_story_id": "fragmented-armed-a",
        "_publication_skip_reason": "thin_article_before_permalink",
        "link": "https://treasurecoast.today/articles/missing-armed-a.html",
        "enriched": True,
    }
    armed_b = {
        "headline": "Armed robbery at Fort Pierce Wells Fargo ATM forces victim to withdraw cash",
        "category_key": "st_lucie",
        "editorial_story_id": "fragmented-armed-b",
        "_publication_skip_reason": "cross_category_duplicate",
        "link": "https://treasurecoast.today/articles/missing-armed-b.html",
        "enriched": True,
    }
    lang_a = {
        "headline": "Indian River County Fire Rescue mourns death of off-duty firefighter Geoffrey Lang",
        "category_key": "indian_river",
        "editorial_story_id": "fragmented-lang-a",
        "_publication_skip_reason": "cross_category_duplicate",
        "link": "https://treasurecoast.today/articles/missing-lang-a.html",
        "enriched": True,
    }
    lang_b = {
        "headline": "Indian River County Fire Rescue Station 9 in mourning after firefighter death",
        "category_key": "local_gov",
        "editorial_story_id": "fragmented-lang-b",
        "link": "https://treasurecoast.today/articles/missing-lang-b.html",
        "enriched": True,
    }
    categories = [
        {"category_key": "crime", "category_label": "Crime & Safety", "hero": armed_a, "cards": []},
        {"category_key": "st_lucie", "category_label": "St. Lucie County", "hero": armed_b, "cards": []},
        {"category_key": "indian_river", "category_label": "Indian River County", "hero": lang_a, "cards": []},
        {"category_key": "local_gov", "category_label": "Local Government", "hero": lang_b, "cards": []},
    ]

    report = g._reconcile_live_publication_receipts(
        categories, categories[0], tmp_path, current_customs=[]
    )
    assert report["rebound_count"] == 4
    assert report["removed_card_count"] == 0
    assert report["removed_hero_count"] == 0
    assert armed_a["_archived_slug"] == armed_slug
    assert armed_b["_archived_slug"] == armed_slug
    assert lang_a["_archived_slug"] == lang_slug
    assert lang_b["_archived_slug"] == lang_slug
    assert armed_a["editorial_story_id"] == "story-armed-canonical"
    assert lang_a["editorial_story_id"] == "story-lang-canonical"
    assert g.validate_forward_live_identity(categories, categories[0], tmp_path)["passed"] is True


def test_unpublished_noncustom_card_is_removed_after_archive_writer_skips_it(tmp_path):
    g = _load_generate()
    g.OUTPUT_DIR = tmp_path
    articles = tmp_path / "articles"
    articles.mkdir()
    slug = f"{datetime.now(timezone.utc).date().isoformat()}-valid-crime-story"
    row = _archive_row(slug, "Valid crime story remains published", "story-valid", "crime")
    (articles / f"{slug}.html").write_text("<article>published</article>", encoding="utf-8")
    (tmp_path / "archive.json").write_text(json.dumps([row]), encoding="utf-8")
    hero = {
        "headline": row["headline"],
        "_archived_slug": slug,
        "editorial_story_id": "story-valid",
        "category_key": "crime",
        "enriched": True,
    }
    orphan = {
        "headline": "Unpublished thin card without a canonical equivalent",
        "link": "https://treasurecoast.today/articles/missing-thin-card.html",
        "category_key": "crime",
        "enriched": True,
        "_publication_skip_reason": "thin_article_before_permalink",
    }
    categories = [
        {"category_key": "crime", "category_label": "Crime & Safety", "hero": hero, "cards": [orphan]}
    ]
    report = g._reconcile_live_publication_receipts(
        categories, categories[0], tmp_path, current_customs=[]
    )
    assert report["removed_card_count"] == 1
    assert all(card.get("headline") != orphan["headline"] for card in categories[0]["cards"])


def test_existing_archive_row_without_story_id_is_removed_from_forward_live_surface(tmp_path):
    g = _load_generate()
    g.OUTPUT_DIR = tmp_path
    articles = tmp_path / "articles"
    articles.mkdir()
    today = datetime.now(timezone.utc).date().isoformat()

    valid_slug = f"{today}-verified-martin-county-story"
    held_slug = f"{today}-17-arrested-in-martin-county-cocaine-trafficking-ring"
    valid = _archive_row(
        valid_slug,
        "Verified Martin County story remains live",
        "story-verified-martin",
        "martin",
    )
    held = _archive_row(
        held_slug,
        "17 arrested in Martin County cocaine trafficking ring",
        "",
        "martin",
    )
    archive = [valid, held]
    for row in archive:
        (articles / f"{row['slug']}.html").write_text(
            "<article>published</article>", encoding="utf-8"
        )
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")

    hero = {
        "headline": valid["headline"],
        "_archived_slug": valid_slug,
        "editorial_story_id": valid["editorial_story_id"],
        "category_key": "martin",
        "enriched": True,
    }
    held_card = {
        "headline": held["headline"],
        "_archived_slug": held_slug,
        "link": f"https://treasurecoast.today/articles/{held_slug}.html",
        "category_key": "martin",
        "enriched": True,
        "_publication_skip_reason": "missing_current_run_persistent_story_id",
    }
    categories = [
        {
            "category_key": "martin",
            "category_label": "Martin County",
            "hero": hero,
            "cards": [held_card],
        }
    ]

    # The archive page existing is not enough for a current forward placement:
    # without an archive story ID it must be removed before the final identity gate.
    assert g._live_archive_entry(held_card, {held_slug: held}, articles) is None
    report = g._reconcile_live_publication_receipts(
        categories, categories[0], tmp_path, current_customs=[]
    )
    assert report["removed_card_count"] == 1
    assert report["removed_cards"][0]["publication_skip_reason"] == (
        "missing_current_run_persistent_story_id"
    )
    assert all(card.get("headline") != held_card["headline"] for card in categories[0]["cards"])
    assert g.validate_forward_live_identity(categories, categories[0], tmp_path)["passed"] is True
