from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POKEMON_SLUG = (
    "2026-08-06-martin-county-investigators-warn-of-counterfeit-"
    "pokemon-card-scams-after-collect"
)
POKEMON_OLD_HYPHEN = POKEMON_SLUG.replace("pokemon", "pok-mon")
POKEMON_UNICODE = POKEMON_SLUG.replace("pokemon", "pokémon")
FIANCEE_SLUG = (
    "2026-07-03-hobe-sound-community-raises-funds-for-man-whose-"
    "fiancee-died-in-monday-house-fir"
)


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda **kwargs: None)
        )
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_generated_and_custom_slugs_share_ascii_transliteration():
    generate = _load_generate()
    assert generate.slugify("Pokémon fiancée café") == "pokemon-fiancee-cafe"
    assert generate._normalize_custom_slug("Pokémon fiancée café") == "pokemon-fiancee-cafe"
    assert generate._normalize_existing_article_slug(POKEMON_UNICODE) == POKEMON_SLUG


def test_unicode_slug_migration_is_atomic_and_idempotent(tmp_path):
    generate = _load_generate()
    articles = tmp_path / "articles"
    data = tmp_path / "data"
    articles.mkdir()
    data.mkdir()
    escaped = POKEMON_UNICODE.replace("é", "#U00e9")
    (articles / f"{escaped}.html").write_text(
        f'<link rel="canonical" href="https://treasurecoast.today/articles/{POKEMON_UNICODE}.html">',
        encoding="utf-8",
    )
    (tmp_path / "archive.json").write_text(
        json.dumps([
            {
                "slug": POKEMON_UNICODE,
                "headline": "Martin County investigators warn of counterfeit Pokémon card scams",
                "link": f"https://treasurecoast.today/articles/{POKEMON_UNICODE}.html",
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    (data / "canonical-redirects.json").write_text(
        json.dumps({"redirects": []}), encoding="utf-8"
    )

    report = generate._migrate_unsafe_article_slugs(tmp_path)
    assert report["status"] == "passed"
    assert report["migrated"] == 1
    assert report["ascii_only"] is True

    archive = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert archive[0]["slug"] == POKEMON_SLUG
    assert POKEMON_SLUG in archive[0]["link"]
    canonical = articles / f"{POKEMON_SLUG}.html"
    assert canonical.is_file()
    assert POKEMON_SLUG in canonical.read_text(encoding="utf-8")
    assert "window.location.replace" in (
        articles / f"{POKEMON_OLD_HYPHEN}.html"
    ).read_text(encoding="utf-8")

    second = generate._migrate_unsafe_article_slugs(tmp_path)
    assert second["migrated"] == 0
    assert second["ascii_only"] is True


def test_production_archive_and_article_files_use_ascii_canonicals():
    archive = json.loads((ROOT / "archive.json").read_text(encoding="utf-8"))
    slugs = {row.get("slug") for row in archive}
    assert POKEMON_SLUG in slugs
    assert FIANCEE_SLUG in slugs
    assert POKEMON_UNICODE not in slugs
    assert all(slug == slug.encode("ascii").decode("ascii") for slug in slugs if slug)

    pokemon_page = ROOT / "articles" / f"{POKEMON_SLUG}.html"
    assert pokemon_page.is_file()
    page = pokemon_page.read_text(encoding="utf-8")
    assert f"/articles/{POKEMON_SLUG}.html" in page
    assert "Martin County investigators warn of counterfeit Pokémon" in page

    old_page = ROOT / "articles" / f"{POKEMON_OLD_HYPHEN}.html"
    assert old_page.is_file()
    old_html = old_page.read_text(encoding="utf-8")
    assert "noindex,follow" in old_html
    assert f"/articles/{POKEMON_SLUG}.html" in old_html


def test_exact_failed_martin_hero_resolves_after_migration():
    generate = _load_generate()
    archive = json.loads((ROOT / "archive.json").read_text(encoding="utf-8"))
    hero = {
        "headline": (
            "Martin County investigators warn of counterfeit Pokémon card scams "
            "after collectors lose $1,200"
        ),
        "_archived_slug": POKEMON_SLUG,
        "link": f"https://treasurecoast.today/articles/{POKEMON_SLUG}.html",
    }
    assert generate._resolve_published_slug(hero, archive, ROOT / "articles") == POKEMON_SLUG
    report = generate.validate_live_permalink_integrity(
        [{"category_key": "martin", "hero": hero, "cards": []}], ROOT
    )
    assert report["passed"] is True
