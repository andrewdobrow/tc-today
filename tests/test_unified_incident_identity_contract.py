from __future__ import annotations

import importlib
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

from tct_engine import EditorialAction, EditorialEngine
from tct_engine.fact_extraction import RawArticle, extract_article_facts
from tct_engine.registry_repair import repair_registry_payload
from tct_engine.story_registry import StoryRegistry
from tct_engine.story_relationship import StoryRelationshipEngine, StoryRelationshipType
from tct_engine.timeline_coherence import analyze_story_timeline_coherence
from tct_engine.unified_incident_identity import (
    build_unified_incident_evidence,
    compare_unified_incident_evidence,
    unified_incident_components,
)

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "2026-08-04-fort-myers-man-arrested-after-road-rage-pit-maneuver-crashes-familys-suv-into-fe"
DUPLICATE = "2026-08-05-florida-man-used-police-maneuver-to-run-north-carolina-family-off-road-near-stua"


def _evidence(title: str, *, body: str = "", published="2026-08-04T12:00:00+00:00"):
    return build_unified_incident_evidence(
        title=title,
        body=body,
        published_at=published,
    )


def _load_generate_module():
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


def test_road_rage_headline_drift_has_verified_identity():
    original = _evidence(
        "Fort Myers man arrested after road rage PIT maneuver crashes family's SUV into fence on I-95 in Martin County"
    )
    rewrite = _evidence(
        "Florida man used police maneuver to run North Carolina family off road near Stuart",
        published="2026-08-05T12:00:00+00:00",
    )
    confidence, trace = compare_unified_incident_evidence(original, rewrite)
    assert confidence >= 0.94
    assert "Identity anchors qualified: True" in trace


def test_generic_road_rage_wording_does_not_merge_unrelated_incident():
    martin = _evidence(
        "Fort Myers man arrested after road rage PIT maneuver crashes family's SUV into fence on I-95 in Martin County"
    )
    unrelated = _evidence(
        "Miami driver arrested after road rage confrontation with motorcyclist on Biscayne Boulevard",
        published="2026-08-05T12:00:00+00:00",
    )
    confidence, _ = compare_unified_incident_evidence(martin, unrelated)
    assert confidence == 0.0



def test_general_source_framing_drift_matches_on_location_and_distinctive_facts():
    first = build_unified_incident_evidence(
        title="Dirt bike rider killed in crash with FedEx truck on East Midway Road",
        locations=("East Midway Road",),
        published_at="2026-08-01T12:00:00+00:00",
    )
    update = build_unified_incident_evidence(
        title="Rider identified after East Midway Road collision involving FedEx truck",
        locations=("East Midway Road",),
        published_at="2026-08-02T12:00:00+00:00",
    )
    confidence, trace = compare_unified_incident_evidence(first, update)
    assert confidence >= 0.89
    assert "Identity anchors qualified: True" in trace


def test_same_city_and_event_family_without_distinctive_continuity_stays_separate():
    first = build_unified_incident_evidence(
        title="Motorcyclist injured in crash on U.S. 1 in Stuart",
        locations=("Stuart",),
        published_at="2026-08-01T12:00:00+00:00",
    )
    unrelated = build_unified_incident_evidence(
        title="Driver killed in crash on Kanner Highway in Stuart",
        locations=("Stuart",),
        published_at="2026-08-02T12:00:00+00:00",
    )
    confidence, _ = compare_unified_incident_evidence(first, unrelated)
    assert confidence == 0.0


def test_editorial_engine_passes_source_evidence_into_registry(tmp_path: Path):
    engine = EditorialEngine(
        default_published_at=datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
        registry_path=tmp_path / "registry.json",
    )
    original = engine.process(
        {
            "id": "road-rage-original",
            "title": (
                "Fort Myers man arrested after road rage PIT maneuver crashes "
                "family's SUV into fence on I-95 in Martin County"
            ),
            "link": "https://example.com/original",
            "summary": (
                "A North Carolina family was run off Interstate 95 near Kanner "
                "Highway when another driver used a PIT maneuver, sending their "
                "SUV into a barbed-wire fence in Martin County."
            ),
        },
        source="WPTV",
        county="Martin",
    )
    rewrite = engine.process(
        {
            "id": "road-rage-rewrite",
            "title": (
                "Florida man used police maneuver to run North Carolina family "
                "off road near Stuart"
            ),
            "link": "https://example.com/rewrite",
            "summary": (
                "Deputies said the driver forced the family's SUV off I-95 near "
                "Kanner Highway and into a fence during the same road-rage incident."
            ),
        },
        source="WPBF",
        county="Martin",
    )
    assert rewrite.story_id == original.story_id
    assert rewrite.action in {EditorialAction.IGNORE, EditorialAction.UPDATE_EXISTING}


def test_sparse_event_keys_can_reuse_verified_incident_identity(tmp_path: Path):
    registry = StoryRegistry(tmp_path / "registry.json")
    first_title = (
        "Fort Myers man arrested after road rage PIT maneuver crashes family's SUV "
        "into fence on I-95 in Martin County"
    )
    second_title = (
        "Florida man used police maneuver to run North Carolina family off road near Stuart"
    )
    first = registry.resolve_article(
        event_key="unknown-event-aaaaaaaaaa",
        title=first_title,
        facts=(),
        published_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        source="https://example.com/first",
        unified_incident_evidence=_evidence(first_title).to_dict(),
    )
    second = registry.resolve_article(
        event_key="unknown-event-bbbbbbbbbb",
        title=second_title,
        facts=(),
        published_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        source="https://example.com/second",
        unified_incident_evidence=_evidence(
            second_title, published="2026-08-05T12:00:00+00:00"
        ).to_dict(),
    )
    assert second == first
    assert registry.last_decision["identity_contract"] == "unified_incident_v1"
    assert registry.last_decision["relationship"] == "same_event"


def test_empty_or_generic_fact_overlap_cannot_authorize_follow_up():
    engine = StoryRelationshipEngine()
    story = {
        "story_id": "story_000001",
        "status": "developing",
        "canonical_title": "Indian River County firefighter Geoffrey Lang dies following off-duty tragedy",
        "titles": ["Indian River County firefighter Geoffrey Lang dies following off-duty tragedy"],
        "events": ["named-person-death:geoffrey-lang"],
        "facts": ["fire reported"],
        "locations": ["Vero Beach"],
        "agencies": ["Indian River County Fire Rescue"],
        "event_types": ["death", "fire"],
        "entities": ["Geoffrey Lang"],
        "timeline": [],
    }
    result = engine.classify(
        event_key="named-person-death:weather-man",
        title="Man charged with setting Spokane's largest wildfire went to prison for manslaughter in dad's death",
        facts=("fire reported", "arrest made"),
        event_types=("fire",),
        entities=("Weather Man",),
        stories=(story,),
    )
    assert result.relationship is StoryRelationshipType.NEW_STORY
    assert result.story_id is None


def test_spokane_wildfire_is_hard_conflict_with_geoffrey_lang_timeline():
    story = {
        "story_id": "story_000793",
        "timeline": [
            {
                "event_key": "named-person-death:geoffrey-lang",
                "article_id": "lang",
                "title": "Indian River County firefighter Geoffrey Lang dies following off-duty tragedy",
                "url": "https://example.com/lang",
            },
            {
                "event_key": "named-person-death:weather-man",
                "article_id": "spokane",
                "title": "Man charged with setting Spokane's largest wildfire went to prison for manslaughter in dad's death",
                "url": "https://example.com/spokane",
            },
        ],
    }
    analysis = analyze_story_timeline_coherence(story, story_id="story_000793")
    assert analysis.coherent is False
    assert any(
        {row["left_family"], row["right_family"]} == {"death", "wildfire_arson"}
        for row in analysis.conflict_pairs
    )


def test_arrest_count_is_material_structured_fact():
    third = extract_article_facts(
        RawArticle(
            article_id="third",
            title="3 arrested in death of 3-month-old child in St. Lucie County",
            body="",
            source="test",
            url="https://example.com/third",
            published_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            county="St. Lucie",
        )
    )
    fourth = extract_article_facts(
        RawArticle(
            article_id="fourth",
            title="4th arrest made in death of 3-month-old child in St. Lucie County",
            body="",
            source="test",
            url="https://example.com/fourth",
            published_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            county="St. Lucie",
        )
    )
    assert "arrest count: 3" in third.facts
    assert "arrest count: 4" in fourth.facts
    assert set(fourth.facts) - set(third.facts) == {"arrest count: 4"}



def test_existing_road_rage_duplicate_redirects_to_august_4_canonical(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    archive = [
        {
            "slug": CANONICAL,
            "headline": "Fort Myers man arrested after road rage PIT maneuver crashes family's SUV into fence on I-95 in Martin County",
            "date": "2026-08-04",
        },
        {
            "slug": DUPLICATE,
            "headline": "Florida man used police maneuver to run North Carolina family off road near Stuart",
            "date": "2026-08-05",
        },
    ]
    cleaned, redirects = generate.apply_canonical_story_cleanup(archive, articles, tmp_path)
    assert [row["slug"] for row in cleaned] == [CANONICAL]
    redirect = next(row for row in redirects if row["source_slug"] == DUPLICATE)
    assert redirect["target_slug"] == CANONICAL
    assert (articles / f"{DUPLICATE}.html").exists()


def test_psl_animal_cruelty_headline_drift_has_verified_identity_despite_name_typo():
    cbs = build_unified_incident_evidence(
        title="Port St. Lucie man arrested after video shows him allegedly abusing small dog",
        body=(
            "Ricky Lee Shieferstein, 68, was arrested after the St. Lucie County "
            "Sheriff's Office investigated a social media video that appeared to "
            "show him kicking a small dog near a pool. He was held on a $7,500 bond."
        ),
        locations=("Port St. Lucie",),
        agencies=("St. Lucie County Sheriff's Office",),
        published_at="2026-08-08T01:02:00+00:00",
    )
    hometown = build_unified_incident_evidence(
        title="Port St. Lucie man charged with animal cruelty",
        body=(
            "Ricky Lee Schieferstein, 68, was arrested Aug. 6 on an animal cruelty "
            "charge after a social media video circulated showing him kicking a small "
            "dog near a swimming pool, according to the St. Lucie County Sheriff's "
            "Office. His bond was set at $7,500."
        ),
        locations=("Port St. Lucie",),
        agencies=("St. Lucie County Sheriff's Office",),
        published_at="2026-08-08T01:46:00+00:00",
    )

    assert cbs.family == hometown.family == "animal_cruelty"
    confidence, trace = compare_unified_incident_evidence(cbs, hometown)
    assert confidence >= 0.97
    assert "Shared concepts:" in " ".join(trace)
    assert "Identity anchors qualified: True" in trace


def test_psl_animal_cruelty_contract_does_not_merge_unrelated_same_city_case():
    first = build_unified_incident_evidence(
        title="Port St. Lucie man charged with animal cruelty",
        body=(
            "A 68-year-old man was arrested after a social media video showed him "
            "kicking a small dog. His bond was $7,500."
        ),
        locations=("Port St. Lucie",),
        agencies=("St. Lucie County Sheriff's Office",),
        published_at="2026-08-08T01:46:00+00:00",
    )
    unrelated = build_unified_incident_evidence(
        title="Port St. Lucie resident faces animal cruelty charge in separate case",
        body=(
            "A 42-year-old resident was arrested after investigators found an injured "
            "cat. Bond was set at $2,500."
        ),
        locations=("Port St. Lucie",),
        agencies=("St. Lucie County Sheriff's Office",),
        published_at="2026-08-09T01:46:00+00:00",
    )

    confidence, _ = compare_unified_incident_evidence(first, unrelated)
    assert confidence == 0.0


def test_editorial_engine_uses_enriched_source_text_to_join_psl_animal_cruelty_sources(tmp_path: Path):
    engine = EditorialEngine(
        default_published_at=datetime(2026, 8, 8, 1, tzinfo=timezone.utc),
        registry_path=tmp_path / "registry.json",
    )
    first = engine.process(
        {
            "id": "cbs-animal-cruelty",
            "title": "Port St. Lucie man arrested after video shows him allegedly abusing small dog",
            "link": "https://cbs12.com/example-animal-cruelty",
            "summary": "Port St. Lucie man arrested after video shows him allegedly abusing small dog",
            "article_text": (
                "Ricky Lee Shieferstein, 68, was arrested after the St. Lucie County "
                "Sheriff's Office investigated a social media video that showed him "
                "kicking a small dog near a pool. He was held on a $7,500 bond."
            ),
        },
        source="CBS12",
        county="St. Lucie",
    )
    second = engine.process(
        {
            "id": "hometown-animal-cruelty",
            "title": "Port St. Lucie man charged with animal cruelty",
            "link": "https://www.hometownnewstc.com/example-animal-cruelty",
            "summary": "Port St. Lucie man charged with animal cruelty",
            "article_text": (
                "Ricky Lee Schieferstein, 68, was arrested on an animal cruelty charge "
                "after a social media video showed him kicking a small dog near a "
                "swimming pool, the St. Lucie County Sheriff's Office said. His bond "
                "was set at $7,500."
            ),
        },
        source="Hometown News Treasure Coast",
        county="St. Lucie",
    )

    assert second.story_id == first.story_id
    assert second.action in {EditorialAction.IGNORE, EditorialAction.UPDATE_EXISTING}


def test_existing_psl_animal_cruelty_duplicate_redirects_to_oldest_canonical_and_merges_categories(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    canonical = generate.PSL_ANIMAL_CRUELTY_CANONICAL_SLUG
    duplicate = next(iter(generate.PSL_ANIMAL_CRUELTY_REDIRECT_SOURCE_SLUGS))
    archive = [
        {
            "slug": canonical,
            "headline": "Port St. Lucie man arrested after video shows him kicking small dog",
            "date": "2026-08-08",
            "first_published": "2026-08-08T01:02:00+00:00",
            "category_key": "st_lucie",
            "category_keys": ["st_lucie"],
            "county_key": "st_lucie",
            "editorial_story_id": "story_002576",
            "source_headline": "Port St. Lucie man arrested after video shows him allegedly abusing small dog - cbs12.com",
            "source_url": "https://cbs12.com/news/crime/port-st-lucie-man-arrested-after-video-shows-him-allegedly-abusing-small-dog-florida-news-florida-crime-st-lucie-county-sheriffs-office",
        },
        {
            "slug": duplicate,
            "headline": "Port St. Lucie man arrested on animal cruelty charge after video circulates on social media",
            "date": "2026-08-08",
            "first_published": "2026-08-08T01:46:00+00:00",
            "category_key": "crime",
            "category_keys": ["crime", "st_lucie"],
            "county_key": "st_lucie",
            "editorial_story_id": "story_002573",
            "source_headline": "Port St. Lucie man charged with animal cruelty - Hometown News Treasure Coast",
            "source_url": "https://www.hometownnewstc.com/multimedia/photo_galleries/st_lucie/port-st-lucie-man-charged-with-animal-cruelty/article_12646c96-5d70-5527-844c-6561ae54674c.html",
        },
    ]

    cleaned, redirects = generate.apply_canonical_story_cleanup(archive, articles, tmp_path)

    assert [row["slug"] for row in cleaned] == [canonical]
    assert set(cleaned[0]["category_keys"]) >= {"crime", "st_lucie"}
    redirect = next(row for row in redirects if row["source_slug"] == duplicate)
    assert redirect["target_slug"] == canonical
    rendered = (articles / f"{duplicate}.html").read_text()
    assert f"/articles/{canonical}.html" in rendered
