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
    os.environ.setdefault("ANTHROPIC_API_KEY", "")
    return importlib.import_module("scripts.generate")


def _configure(generate, tmp_path: Path):
    generate.OUTPUT_DIR = tmp_path
    generate.EDITORIAL_IMAGE_ROOT = tmp_path / "images" / "editorial"
    generate.EDITORIAL_IMAGE_ROTATION_PATH = tmp_path / "data" / "editorial-image-rotation.json"
    generate.EDITORIAL_IMAGE_REPORT_PATH = tmp_path / "data" / "editorial-image-rotation-report.json"
    generate._EDITORIAL_IMAGE_INVENTORY_CACHE = None
    generate._EDITORIAL_IMAGE_ROTATION_STATE = None
    generate._EDITORIAL_IMAGE_ROTATION_DIRTY = False
    generate._EDITORIAL_IMAGE_RUN_ASSIGNMENTS.clear()
    generate._EDITORIAL_IMAGE_LAST_SELECTION.clear()
    return generate


def _image(root: Path, rel: str):
    path = root / "images" / "editorial" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"image")
    return path


def test_inventory_includes_topic_og_and_prefers_webp_over_duplicate_formats(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "cities/fort-pierce/fort-pierce-marina.jpg")
    _image(tmp_path, "cities/fort-pierce/fort-pierce-marina.png")
    _image(tmp_path, "topics/business-development/business-development.png")
    _image(tmp_path, "topics/business-development/og-business.png")
    _image(tmp_path, "topics/business-development/og-business.webp")
    placeholder = tmp_path / "images" / "editorial" / "topics" / "place"
    placeholder.parent.mkdir(parents=True, exist_ok=True)
    placeholder.write_text("x", encoding="utf-8")

    inventory = generate._editorial_image_inventory(refresh=True)

    assert inventory["image_count"] == 3
    assert inventory["pools"]["cities/fort-pierce"] == [
        "/images/editorial/cities/fort-pierce/fort-pierce-marina.jpg"
    ]
    assert inventory["pools"]["topics/business-development"] == [
        "/images/editorial/topics/business-development/business-development.png",
        "/images/editorial/topics/business-development/og-business.webp",
    ]
    reasons = {row["path"]: row["reason"] for row in inventory["excluded"]}
    assert reasons["cities/fort-pierce/fort-pierce-marina.png"] == "duplicate-stem-alternate-format"
    assert reasons["topics/business-development/og-business.png"] == "duplicate-stem-alternate-format"
    assert reasons["topics/place"] == "non-image-or-placeholder"


def test_exact_city_beats_topic_and_assignments_rotate_sequentially(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    for name in ("a.png", "b.png", "c.png"):
        _image(tmp_path, f"cities/stuart/{name}")
    _image(tmp_path, "topics/crime-public-safety/crime.png")

    urls = []
    for index in range(4):
        url, credit = generate.get_fallback_image(
            "crime",
            f"Police investigate incident in Stuart number {index}",
            item={"headline": f"Police investigate incident in Stuart number {index}"},
        )
        urls.append(url)
        assert credit == ""

    assert urls == [
        "https://treasurecoast.today/images/editorial/cities/stuart/a.png",
        "https://treasurecoast.today/images/editorial/cities/stuart/b.png",
        "https://treasurecoast.today/images/editorial/cities/stuart/c.png",
        "https://treasurecoast.today/images/editorial/cities/stuart/a.png",
    ]
    same_url, _ = generate.get_fallback_image(
        "crime",
        "Police investigate incident in Stuart number 0",
        item={"headline": "Police investigate incident in Stuart number 0"},
    )
    assert same_url == urls[0]


def test_county_pool_round_robins_city_folders_and_preserves_folder_sequence(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "cities/port-st-lucie/psl-1.png")
    _image(tmp_path, "cities/port-st-lucie/psl-2.png")
    _image(tmp_path, "cities/fort-pierce/fp-1.png")
    _image(tmp_path, "cities/fort-pierce/fp-2.png")

    pool_id, images, basis = generate._editorial_pool_for_story(
        "st_lucie", "St. Lucie County approves annual plan", item={}
    )

    assert pool_id == "county/st_lucie"
    assert basis == "county-city-round-robin"
    assert images == [
        "/images/editorial/cities/port-st-lucie/psl-1.png",
        "/images/editorial/cities/fort-pierce/fp-1.png",
        "/images/editorial/cities/port-st-lucie/psl-2.png",
        "/images/editorial/cities/fort-pierce/fp-2.png",
    ]


def test_rotation_state_persists_and_continues_without_immediate_repeat(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "topics/sports/one.png")
    _image(tmp_path, "topics/sports/two.png")

    first, _ = generate.get_fallback_image("sports", "Mets win first game", item={})
    generate._save_editorial_image_rotation_state()
    assert generate.EDITORIAL_IMAGE_ROTATION_PATH.exists()

    generate._EDITORIAL_IMAGE_ROTATION_STATE = None
    generate._EDITORIAL_IMAGE_INVENTORY_CACHE = None
    generate._EDITORIAL_IMAGE_RUN_ASSIGNMENTS.clear()
    generate._EDITORIAL_IMAGE_LAST_SELECTION.clear()
    second, _ = generate.get_fallback_image("sports", "Mets win second game", item={})

    assert first.endswith("/one.png")
    assert second.endswith("/two.png")


def test_archive_migration_updates_old_fallback_but_preserves_custom(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "topics/crime-public-safety/crime-tape.png")
    (tmp_path / "articles").mkdir()
    old_url = "https://treasurecoast.today/images/fallback/crime-1.jpg"
    archive = [
        {
            "slug": "generated-story",
            "headline": "Deputies make arrest in county case",
            "category_key": "crime",
            "image_url": old_url,
        },
        {
            "slug": "custom-story",
            "headline": "Custom investigation",
            "category_key": "crime",
            "image_url": old_url,
            "is_custom": True,
        },
    ]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (tmp_path / "articles" / "generated-story.html").write_text(
        f'<meta property="og:image" content="{old_url}"><img src="{old_url}">',
        encoding="utf-8",
    )

    report = generate.refresh_archive_editorial_fallbacks(tmp_path)
    updated = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))

    assert report["updated"] == 1
    assert report["article_pages_updated"] == 1
    assert updated[0]["image_url"].endswith("/topics/crime-public-safety/crime-tape.png")
    assert updated[0]["image_source"] == "editorial_fallback"
    assert updated[1]["image_url"] == old_url
    html = (tmp_path / "articles" / "generated-story.html").read_text(encoding="utf-8")
    assert old_url not in html
    assert "crime-tape.png" in html


def test_supplied_library_manifest_matches_optimized_assets():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "data" / "editorial-image-library.json").read_text(encoding="utf-8")
    )
    assert manifest["image_count"] == 55
    assert manifest["pool_count"] == 20
    assert manifest["total_optimized_bytes"] < 10 * 1024 * 1024
    for row in manifest["images"]:
        assert row["path"].endswith(".webp")
        assert (root / row["path"].lstrip("/")).is_file()
    og_paths = {row["path"] for row in manifest["images"] if Path(row["path"]).name.lower().startswith("og-")}
    assert og_paths == {
        "/images/editorial/topics/business-development/og-business.webp",
        "/images/editorial/topics/crime-public-safety/og-crime.webp",
        "/images/editorial/topics/local-government/og-local_gov.webp",
        "/images/editorial/topics/sports/og-sports.webp",
        "/images/editorial/topics/things-to-do/og-things_to_do.webp",
    }
