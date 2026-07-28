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


def test_specific_topics_beat_exact_city_while_broad_topics_do_not(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "cities/port-st-lucie/city.png")
    _image(tmp_path, "cities/fort-pierce/city.png")
    _image(tmp_path, "cities/vero-beach/city.png")
    _image(tmp_path, "cities/stuart/city.png")
    _image(tmp_path, "topics/schools/school.png")
    _image(tmp_path, "topics/roads-transportation/road.png")
    _image(tmp_path, "topics/health/health.png")
    _image(tmp_path, "topics/weather-environment/weather.png")
    _image(tmp_path, "topics/crime-public-safety/crime.png")
    _image(tmp_path, "topics/business-development/business.png")

    cases = [
        ("st_lucie", "Port St. Lucie school opens new campus", "topics/schools"),
        ("st_lucie", "Fort Pierce bridge closure begins Monday", "topics/roads-transportation"),
        ("indian_river", "Vero Beach hospital expands emergency room", "topics/health"),
        ("martin", "Hurricane shelter opens in Stuart", "topics/weather-environment"),
        ("crime", "Police investigate theft in Stuart", "cities/stuart"),
        ("business", "New restaurant opens in Vero Beach", "cities/vero-beach"),
    ]
    for category, headline, expected_pool in cases:
        pool_id, _images, basis = generate._editorial_pool_for_story(
            category, headline, item={"headline": headline}
        )
        assert pool_id == expected_pool
        if expected_pool.startswith("topics/") and expected_pool in {
            "topics/schools", "topics/roads-transportation",
            "topics/health", "topics/weather-environment",
        }:
            assert basis == "specific-topic-before-city"
        else:
            assert basis == "exact-city"


def test_vero_beach_name_alone_does_not_trigger_weather_pool(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "cities/vero-beach/city.png")
    _image(tmp_path, "topics/weather-environment/weather.png")

    pool_id, _images, basis = generate._editorial_pool_for_story(
        "business", "Vero Beach business celebrates grand opening", item={}
    )

    assert pool_id == "cities/vero-beach"
    assert basis == "exact-city"


def test_city_pool_still_rotates_sequentially_for_broad_topic_story(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    for name in ("a.png", "b.png", "c.png"):
        _image(tmp_path, f"cities/stuart/{name}")
    _image(tmp_path, "topics/crime-public-safety/crime.png")

    urls = []
    for index in range(4):
        url, credit = generate.get_fallback_image(
            "crime",
            f"Police investigate theft in Stuart number {index}",
            item={"headline": f"Police investigate theft in Stuart number {index}"},
        )
        urls.append(url)
        assert credit == ""

    assert urls == [
        "https://treasurecoast.today/images/editorial/cities/stuart/a.png",
        "https://treasurecoast.today/images/editorial/cities/stuart/b.png",
        "https://treasurecoast.today/images/editorial/cities/stuart/c.png",
        "https://treasurecoast.today/images/editorial/cities/stuart/a.png",
    ]


def test_existing_assignment_reclassifies_when_policy_selects_new_pool(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    city = _image(tmp_path, "cities/port-st-lucie/city.png")
    school = _image(tmp_path, "topics/schools/school.png")
    headline = "Port St. Lucie school opens new campus"
    item = {"headline": headline, "slug": "school-campus"}
    story_key = generate._fallback_story_key("st_lucie", headline, item)
    generate._EDITORIAL_IMAGE_ROTATION_STATE = {
        "schema_version": 1,
        "pool_cursors": {},
        "pool_last_image": {},
        "global_last_image": "",
        "story_assignments": {
            story_key: {
                "image_url": f"https://treasurecoast.today/images/editorial/cities/port-st-lucie/{city.name}",
                "pool_id": "cities/port-st-lucie",
                "assigned_at": "2026-07-26T00:00:00+00:00",
            }
        },
    }

    selection = generate._select_editorial_fallback("st_lucie", headline, item=item)

    assert selection["pool_id"] == "topics/schools"
    assert selection["image_url"].endswith(f"/topics/schools/{school.name}")
    assert selection["reused"] is False


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


def test_archive_migration_reclassifies_existing_editorial_city_fallback(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    city = _image(tmp_path, "cities/port-st-lucie/city.png")
    school = _image(tmp_path, "topics/schools/school.png")
    (tmp_path / "articles").mkdir()
    old_url = f"https://treasurecoast.today/images/editorial/cities/port-st-lucie/{city.name}"
    archive = [{
        "slug": "psl-school-campus",
        "headline": "Port St. Lucie school opens new campus",
        "category_key": "st_lucie",
        "image_url": old_url,
        "image_source": "editorial_fallback",
        "is_fallback_image": True,
    }]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (tmp_path / "articles" / "psl-school-campus.html").write_text(
        f'<meta property="og:image" content="{old_url}"><img src="{old_url}">',
        encoding="utf-8",
    )

    report = generate.refresh_archive_editorial_fallbacks(tmp_path)
    updated = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))

    assert report["updated"] == 1
    assert updated[0]["image_url"].endswith(f"/topics/schools/{school.name}")
    html = (tmp_path / "articles" / "psl-school-campus.html").read_text(encoding="utf-8")
    assert old_url not in html
    assert f"/topics/schools/{school.name}" in html


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


def test_airline_route_and_incidental_body_terms_do_not_use_roads_pool(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "cities/vero-beach/city.png")
    _image(tmp_path, "topics/business-development/business.png")
    _image(tmp_path, "topics/roads-transportation/road.png")

    jetblue = {
        "headline": "JetBlue cancels Vero Beach to JFK route in September, citing low demand",
        "teaser": "The airline said passenger demand did not support the nonstop service.",
        "body": "The flight used Vero Beach Regional Airport and connected travelers to New York.",
    }
    pool_id, _images, basis = generate._editorial_pool_for_story(
        "business", jetblue["headline"], item=jetblue
    )
    assert pool_id == "cities/vero-beach"
    assert basis == "exact-city"

    racetrack = {
        "headline": "Private racetrack resort community breaks ground in St. Lucie County on 650 acres",
        "teaser": "The private membership development is building homes, garages and racing circuits.",
        "body": (
            "The project is off Okeechobee Road and will include street cars, "
            "internal transportation routes and multiple tracks."
        ),
    }
    pool_id, _images, basis = generate._editorial_pool_for_story(
        "business", racetrack["headline"], item=racetrack
    )
    assert pool_id == "topics/business-development"
    assert basis == "category-topic"


def test_fatal_crash_public_safety_story_does_not_default_to_roads_pool(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "topics/crime-public-safety/crime.png")
    _image(tmp_path, "topics/roads-transportation/road.png")

    headline = (
        "Community gathers to honor 9-year-old boy killed in dirt bike crash "
        "with FedEx truck in St. Lucie County"
    )
    pool_id, _images, basis = generate._editorial_pool_for_story(
        "crime",
        headline,
        item={
            "headline": headline,
            "teaser": "Family and neighbors gathered for a memorial after the child's death.",
        },
    )

    assert pool_id == "topics/crime-public-safety"
    assert basis == "category-topic"


def test_exact_archive_source_image_restores_over_editorial_fallback(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "topics/roads-transportation/road.png")
    headline = "Private racetrack resort community breaks ground in St. Lucie County on 650 acres"
    source_url = "https://ewscripps.brightspotcdn.com/example-racetrack.jpg"
    item = {
        "headline": headline,
        "slug": "racetrack-story",
        "category_key": "business",
        "image_url": "https://treasurecoast.today/images/editorial/topics/roads-transportation/road.png",
        "image_source": "editorial_fallback",
        "is_fallback_image": True,
    }
    archive = [{
        "slug": "racetrack-story",
        "headline": headline,
        "category_key": "business",
        "image_url": source_url,
        "image_credit": "WPTV",
        "image_source": "source_og",
    }]

    assert generate._restore_archive_source_image(item, archive) is True
    assert item["image_url"] == source_url
    assert item["image_credit"] == "WPTV"
    assert item["is_fallback_image"] is False


def test_archive_fallback_migration_runs_once_per_policy_version(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "topics/business-development/business.png")
    (tmp_path / "articles").mkdir()
    old_url = "https://treasurecoast.today/og-business.png"
    archive = [{
        "slug": "business-story",
        "headline": "County business opens new facility",
        "category_key": "business",
        "image_url": old_url,
    }]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (tmp_path / "articles" / "business-story.html").write_text(
        f'<meta property="og:image" content="{old_url}"><img src="{old_url}">',
        encoding="utf-8",
    )

    first = generate.refresh_archive_editorial_fallbacks(tmp_path)
    second = generate.refresh_archive_editorial_fallbacks(tmp_path)

    assert first["skipped"] is False
    assert first["updated"] == 1
    assert second["skipped"] is True
    assert second["reason"] == "policy-version-already-migrated"


def test_first_responder_memorial_outranks_incidental_health_language(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "topics/crime-public-safety/public-safety.png")
    _image(tmp_path, "topics/health/doctor.png")
    _image(tmp_path, "topics/local-government/city-hall.png")

    headlines = [
        "Indian River County Board of Commissioners mourns loss of firefighter Geoffrey Lang",
        "Indian River County government mourns firefighter who dedicated career to serving residents",
    ]
    for headline in headlines:
        item = {
            "headline": headline,
            "teaser": (
                "County commissioners extended condolences and emphasized the county's "
                "commitment to supporting the mental health and well-being of first "
                "responders and their families."
            ),
        }
        pool_id, _images, basis = generate._editorial_pool_for_story(
            "indian_river", headline, item=item
        )

        assert pool_id == "topics/crime-public-safety"
        assert basis == "specific-topic-before-city"


def test_incidental_health_and_well_being_phrase_does_not_trigger_medical_pool(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "topics/health/doctor.png")
    _image(tmp_path, "topics/local-government/city-hall.png")

    headline = "County commission expands employee support program"
    item = {
        "headline": headline,
        "teaser": (
            "Commissioners said the program supports the mental health and well-being "
            "of county employees and their families."
        ),
    }
    pool_id, _images, basis = generate._editorial_pool_for_story(
        "indian_river", headline, item=item
    )

    assert pool_id == "topics/local-government"
    assert basis == "detected-topic"


def test_genuine_healthcare_language_still_selects_health_pool(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    _image(tmp_path, "topics/health/doctor.png")
    _image(tmp_path, "topics/local-government/city-hall.png")

    headline = "Indian River County Health Department opens new public health clinic"
    pool_id, _images, basis = generate._editorial_pool_for_story(
        "indian_river", headline, item={"headline": headline}
    )

    assert pool_id == "topics/health"
    assert basis == "specific-topic-before-city"


def test_policy_change_reclassifies_stored_health_image_for_first_responder_story(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    public_safety = _image(tmp_path, "topics/crime-public-safety/public-safety.png")
    doctor = _image(tmp_path, "topics/health/doctor.png")
    headline = "Indian River County Board of Commissioners mourns loss of firefighter Geoffrey Lang"
    item = {
        "headline": headline,
        "slug": "indian-river-commissioners-mourn-geoffrey-lang",
        "teaser": (
            "The board emphasized support for the mental health and well-being of "
            "first responders and their families."
        ),
    }
    story_key = generate._fallback_story_key("indian_river", headline, item)
    generate._EDITORIAL_IMAGE_ROTATION_STATE = {
        "schema_version": 2,
        "selection_policy_version": 3,
        "pool_cursors": {},
        "pool_last_image": {},
        "global_last_image": "",
        "archive_migration_policy_version": 3,
        "story_assignments": {
            story_key: {
                "story_key": story_key,
                "headline": headline,
                "category_key": "indian_river",
                "selection_policy_version": 3,
                "pool_id": "topics/health",
                "selection_basis": "specific-topic-before-city",
                "image_url": (
                    "https://treasurecoast.today/images/editorial/topics/health/"
                    f"{doctor.name}"
                ),
                "assigned_at": "2026-07-28T00:00:00+00:00",
            }
        },
    }

    selection = generate._select_editorial_fallback(
        "indian_river", headline, item=item
    )

    assert selection["pool_id"] == "topics/crime-public-safety"
    assert selection["image_url"].endswith(
        f"/topics/crime-public-safety/{public_safety.name}"
    )
    assert selection["selection_policy_version"] == 4
    assert selection["reused"] is False


def test_policy_v4_migration_repairs_geoffrey_lang_medical_fallback(tmp_path):
    generate = _configure(_load_generate(), tmp_path)
    public_safety = _image(tmp_path, "topics/crime-public-safety/public-safety.png")
    doctor = _image(tmp_path, "topics/health/doctor.png")
    (tmp_path / "articles").mkdir()
    old_url = (
        "https://treasurecoast.today/images/editorial/topics/health/"
        f"{doctor.name}"
    )
    headline = "Indian River County Board of Commissioners mourns loss of firefighter Geoffrey Lang"
    archive = [{
        "slug": "indian-river-commissioners-mourn-geoffrey-lang",
        "headline": headline,
        "teaser": (
            "Commissioners emphasized support for the mental health and well-being "
            "of first responders and their families."
        ),
        "category_key": "indian_river",
        "image_url": old_url,
        "image_source": "editorial_fallback",
        "is_fallback_image": True,
    }]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    article_path = tmp_path / "articles" / "indian-river-commissioners-mourn-geoffrey-lang.html"
    article_path.write_text(
        f'<meta property="og:image" content="{old_url}"><img src="{old_url}">',
        encoding="utf-8",
    )

    report = generate.refresh_archive_editorial_fallbacks(tmp_path)
    updated = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    html = article_path.read_text(encoding="utf-8")

    assert report["selection_policy_version"] == 4
    assert report["updated"] == 1
    assert report["article_pages_updated"] == 1
    assert updated[0]["image_url"].endswith(
        f"/topics/crime-public-safety/{public_safety.name}"
    )
    assert old_url not in html
    assert f"/topics/crime-public-safety/{public_safety.name}" in html
