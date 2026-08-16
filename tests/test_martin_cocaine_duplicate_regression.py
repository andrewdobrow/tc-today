from __future__ import annotations

import importlib.util
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

from tct_engine import RawArticle, extract_article_facts
from tct_engine.incident_identity import incident_anchor_key
from tct_engine.semantic_publication_gate import retrieve_recent_candidates

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_SLUG = (
    "2026-08-14-17-arrested-in-indiantown-cocaine-trafficking-ring-three-remain-wanted-after-mon"
)
DUPLICATE_SLUG = (
    "2026-08-15-17-arrested-in-martin-county-cocaine-trafficking-bust-4-kilos-seized-in-indianto"
)
AUG16_DUPLICATE_SLUG = (
    "2026-08-16-17-arrested-in-major-martin-county-cocaine-bust-4-kilos-seized-in-indiantown-ope"
)
OPERATION_ANCHOR = "law-enforcement-operation:beneath-the-surface"


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
    path = ROOT / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_martin_cocaine_regression", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_firearm_does_not_create_false_fire_event():
    article = RawArticle(
        article_id="drug-bust-1",
        title="17 arrested in Martin County cocaine trafficking bust",
        body=(
            "Martin County Sheriff's Office investigators seized four kilograms "
            "of cocaine and eight firearms during Operation Beneath the Surface."
        ),
        source="WPTV",
        url="https://example.com/drug-bust",
        published_at=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
        county="Martin",
        is_custom=False,
    )

    facts = extract_article_facts(article)

    assert "fire reported" not in facts.facts
    assert "fire" not in facts.event_types
    assert "arrest made" in facts.facts


def test_named_law_enforcement_operation_is_durable_incident_anchor():
    left = incident_anchor_key(
        titles=[
            "Operation 'Beneath the Surface': 17 arrested, 4 kilos of cocaine seized"
        ],
        body="Martin County Sheriff's Office announced the narcotics arrests.",
    )
    right = incident_anchor_key(
        titles=["17 arrested in Indiantown cocaine trafficking ring"],
        body=(
            "The months-long Martin County Sheriff's Office investigation was dubbed "
            "Operation Beneath the Surface and resulted in 17 arrests."
        ),
    )

    assert left == OPERATION_ANCHOR
    assert right == OPERATION_ANCHOR


def test_drug_seizure_is_drug_case_not_animal_case():
    generate = _load_generate()
    families = generate._cross_source_event_families({
        "headline": "17 arrested in Martin County drug bust",
        "body": (
            "Deputies seized four kilograms of cocaine, marijuana and eight firearms "
            "during a months-long narcotics investigation."
        ),
    })

    assert "drug-case" in families
    assert "animal-case" not in families
    assert "fire" not in families


def test_exact_production_pair_reaches_semantic_candidate_gate():
    canonical = {
        "slug": CANONICAL_SLUG,
        "headline": (
            "17 arrested in Indiantown cocaine trafficking ring, three remain wanted "
            "after months-long investigation"
        ),
        "source_headline": "Martin County Sheriff holding news conference to announce major drug investigation - WPEC",
        "published_at": "2026-08-14T15:09:40+00:00",
        "locality": ["martin-county", "indiantown"],
        "event_families": ["drug-case"],
        "agencies": ["martin-county-sheriff"],
        "incident_anchor": OPERATION_ANCHOR,
        "known_event_key": "",
    }
    incoming = {
        "slug": DUPLICATE_SLUG,
        "headline": (
            "17 arrested in Martin County cocaine trafficking bust, 4 kilos seized "
            "in Indiantown operation"
        ),
        "source_headline": (
            "Operation 'Beneath the Surface': 17 arrested, 4 kilos of cocaine seized "
            "in Martin County drug bust - WPTV"
        ),
        "published_at": "2026-08-15T01:26:01+00:00",
        "locality": ["martin-county", "indiantown"],
        "event_families": ["drug-case"],
        "agencies": ["martin-county-sheriff"],
        "incident_anchor": OPERATION_ANCHOR,
        "known_event_key": "",
    }

    candidates = retrieve_recent_candidates(incoming, [canonical], window_days=7, max_candidates=4)

    assert len(candidates) == 1
    assert candidates[0]["slug"] == CANONICAL_SLUG
    reasons = set(candidates[0]["evidence"]["reasons"])
    assert "exact_named_law_enforcement_operation" in reasons
    assert "law_enforcement_drug_operation_continuity" in reasons




def test_aug16_third_rewrite_reaches_gate_despite_conflicting_structured_identity():
    canonical = {
        "slug": CANONICAL_SLUG,
        "headline": (
            "17 arrested in Indiantown cocaine trafficking ring, three remain wanted "
            "after months-long investigation"
        ),
        "source_headline": "Martin County Sheriff holding news conference to announce major drug investigation - WPEC",
        "published_at": "2026-08-14T15:09:40+00:00",
        "locality": ["martin-county", "indiantown"],
        "event_families": ["drug-case"],
        "agencies": ["martin-county-sheriff"],
        "incident_anchor": OPERATION_ANCHOR,
        # Deliberately reproduce the kind of contaminated legacy key seen in production.
        "known_event_key": "fire-stuart-legacy-contamination",
    }
    incoming = {
        "slug": AUG16_DUPLICATE_SLUG,
        "headline": (
            "17 arrested in major Martin County cocaine bust, 4 kilos seized "
            "in Indiantown operation"
        ),
        "source_headline": (
            "Operation 'Beneath the Surface': 17 arrested, 4 kilos of cocaine seized "
            "in Martin County drug bust - WPTV"
        ),
        "published_at": "2026-08-16T01:00:00+00:00",
        "locality": ["martin-county", "indiantown"],
        "event_families": ["drug-case"],
        "agencies": ["martin-county-sheriff"],
        "incident_anchor": OPERATION_ANCHOR,
        "known_event_key": "traffic-crash-fragmented-identity",
    }

    candidates = retrieve_recent_candidates(incoming, [canonical], window_days=7, max_candidates=4)

    assert len(candidates) == 1
    evidence = candidates[0]["evidence"]
    assert candidates[0]["slug"] == CANONICAL_SLUG
    assert evidence["structured_conflict_override"] is True
    assert evidence["structured_conflict_override_tier"] == "exact_named_law_enforcement_operation"
    assert evidence["shared_arrest_counts"] == ["17"]
    assert evidence["shared_drug_terms"] == ["cocaine"]


def test_fragmented_unknown_event_ids_cannot_veto_strict_drug_operation_bundle():
    canonical = {
        "slug": CANONICAL_SLUG,
        "headline": "17 arrested in Indiantown cocaine trafficking ring",
        "published_at": "2026-08-14T15:09:40+00:00",
        "locality": ["martin-county", "indiantown"],
        "event_families": ["drug-case"],
        "agencies": ["martin-county-sheriff"],
        "known_event_key": "unknown-event-left",
    }
    incoming = {
        "slug": AUG16_DUPLICATE_SLUG,
        "headline": "17 arrested in major Martin County cocaine bust in Indiantown",
        "published_at": "2026-08-16T01:00:00+00:00",
        "locality": ["martin-county", "indiantown"],
        "event_families": ["drug-case"],
        "agencies": ["martin-county-sheriff"],
        "known_event_key": "unknown-event-right",
    }

    candidates = retrieve_recent_candidates(incoming, [canonical], window_days=7, max_candidates=4)
    assert len(candidates) == 1
    evidence = candidates[0]["evidence"]
    assert evidence["known_event_key_conflict"] is True
    assert evidence["structured_conflict_override"] is True
    assert evidence["structured_conflict_override_tier"] == "law_enforcement_drug_operation_continuity"
    assert evidence["shared_arrest_counts"] == ["17"]

def test_verified_existing_duplicate_fallback_preserves_older_url_and_redirects_newer():
    generate = _load_generate()
    archive = [
        {
            "slug": CANONICAL_SLUG,
            "headline": (
                "17 arrested in Indiantown cocaine trafficking ring, three remain wanted "
                "after months-long investigation"
            ),
            "source_url": "https://cbs12.com/news/local/martin-county-drug-investigation",
            "editorial_story_id": "story_003960",
            "category_key": "martin",
            "category_keys": ["martin", "crime"],
            "county_keys": ["martin"],
        },
        {
            "slug": DUPLICATE_SLUG,
            "headline": (
                "17 arrested in Martin County cocaine trafficking bust, 4 kilos seized "
                "in Indiantown operation"
            ),
            "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/drug-bust",
            "editorial_story_id": "story_003912",
            "category_key": "crime",
            "category_keys": ["crime", "martin"],
            "county_keys": ["martin"],
        },
        {
            "slug": AUG16_DUPLICATE_SLUG,
            "headline": (
                "17 arrested in major Martin County cocaine bust, 4 kilos seized "
                "in Indiantown operation"
            ),
            "source_url": "https://example.com/third-rewrite",
            "editorial_story_id": "story_004001",
            "category_key": "crime",
            "category_keys": ["crime", "martin"],
            "county_keys": ["martin"],
        },
    ]
    report = generate._new_semantic_publication_gate_report()

    cleaned, redirects, repair = generate._repair_verified_martin_cocaine_operation_duplicate(
        archive, report
    )

    assert repair["status"] == "repaired"
    assert {row["slug"] for row in cleaned} == {CANONICAL_SLUG}
    assert len(redirects) == 2
    assert {row["source_slug"] for row in redirects} == {DUPLICATE_SLUG, AUG16_DUPLICATE_SLUG}
    assert all(row["target_slug"] == CANONICAL_SLUG for row in redirects)
    assert {row["incoming_story_id"] for row in report["decisions"][-2:]} == {"story_003912", "story_004001"}
    assert all(row["decision"]["selected_candidate_slug"] == CANONICAL_SLUG for row in report["decisions"][-2:])
    assert all(row["decision"]["same_real_world_event"] is True for row in report["decisions"][-2:])


def test_strict_drug_operation_continuity_does_not_merge_different_arrest_count():
    canonical = {
        "slug": CANONICAL_SLUG,
        "headline": "17 arrested in Indiantown cocaine trafficking ring",
        "published_at": "2026-08-14T15:09:40+00:00",
        "locality": ["martin-county", "indiantown"],
        "event_families": ["drug-case"],
        "agencies": ["martin-county-sheriff"],
        "known_event_key": "unknown-event-left",
    }
    unrelated = {
        "slug": "2026-08-16-two-arrested-in-separate-indiantown-cocaine-case",
        "headline": "2 arrested in separate Indiantown cocaine case",
        "published_at": "2026-08-16T03:00:00+00:00",
        "locality": ["martin-county", "indiantown"],
        "event_families": ["drug-case"],
        "agencies": ["martin-county-sheriff"],
        "known_event_key": "unknown-event-right",
    }

    assert retrieve_recent_candidates(unrelated, [canonical], window_days=7, max_candidates=4) == []
