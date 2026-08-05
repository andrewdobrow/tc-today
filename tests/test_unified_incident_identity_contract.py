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


def test_production_registry_consolidates_road_rage_and_detaches_spokane():
    registry = json.loads((ROOT / "data" / "editorial_story_registry.json").read_text())
    aliases = registry["story_aliases"]
    for fragmented in (
        "story_002014", "story_002017", "story_002116", "story_002164",
        "story_002168", "story_002169", "story_002170", "story_002263",
    ):
        assert aliases[fragmented] == "story_002076"
    lang_titles = " ".join(registry["stories"]["story_000793"].get("titles", ()))
    assert "Spokane" not in lang_titles
    assert any(
        "Spokane's largest wildfire" in " ".join(story.get("titles", ()))
        and story_id != "story_000793"
        for story_id, story in registry["stories"].items()
    )
    assert unified_incident_components(registry["stories"]) == []



def test_repaired_production_registry_is_idempotent():
    registry = json.loads((ROOT / "data" / "editorial_story_registry.json").read_text())
    report = repair_registry_payload(registry)
    assert report.changed is False
    assert report.quarantined_story_ids == ()
    assert report.remaining_unified_incident_groups == 0
    assert report.remaining_timeline_coherence_violations == 0
    assert all(
        registry["story_aliases"].get(story_id) == "story_002076"
        for story_id in (
            "story_002014", "story_002017", "story_002116", "story_002164",
            "story_002168", "story_002169", "story_002170", "story_002263",
        )
    )


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
